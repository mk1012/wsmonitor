import asyncio
import logging
import os
import signal
from asyncio import CancelledError
from asyncio.subprocess import PIPE
from typing import Union, Callable, Optional

from wsmonitor.process.data import ProcessData

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProcessOutput:

    def __init__(self) -> None:
        self.stdout = []
        self.stderr = []
        self.exit_code = None

    def reset(self) -> None:
        self.stdout.clear()
        self.stderr.clear()
        self.exit_code = None


StateChangeCallback = Callable[['Process'], None]
OutputCallback = Callable[['Process', str], None]


class Process:
    def __init__(self, process_data: ProcessData) -> None:
        self._data = process_data
        self._asyncio_process: Optional[asyncio.subprocess.Process] = None  # pylint: disable=no-member
        self._process_task: Optional[asyncio.Task] = None
        self._state_change_listener: Optional[StateChangeCallback] = None
        self._output_listener: Optional[OutputCallback] = None

    def set_state_listener(self, listener: StateChangeCallback) -> None:
        self._state_change_listener = listener

    def set_output_listener(self, listener: OutputCallback) -> None:
        self._output_listener = listener

    async def _run_process(self) -> int:
        preexec_fn = None
        if self._data.as_process_group:
            # Run process in a new process group
            # https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
            preexec_fn = os.setsid

        logger.debug("Process[%s]: starting", self._data.uid)
        self._asyncio_process = await asyncio.create_subprocess_shell(
            self._data.command, stdout=PIPE, stderr=PIPE, preexec_fn=preexec_fn)

        self._state_changed(ProcessData.STARTED)

        # start the read tasks and wait for them to complete
        try:
            await asyncio.wait([
                self._read_stream(self._asyncio_process.stdout, self._output_listener),
                self._read_stream(self._asyncio_process.stderr, self._output_listener)
            ])
            self._data.exit_code = await self._asyncio_process.wait()

        except CancelledError:
            logger.warning("Process[%s]: Caught task CancelledError! Stopping process instead", self.uid())
            await self.stop()
            self._data.ensure_exit_code(-1)

        logger.debug("Process[%s]: has exited with: %d", self.uid(), self._data.exit_code)
        self._state_changed(ProcessData.ENDED)

        return self._data.exit_code

    async def stop(self, int_timeout: float = 2, term_timeout: float = 2) -> Union[int, str]:

        if not self.is_running():
            return "'%s' is not running, cannot stop it" % self.uid()

        logger.debug("Process[%s](%d): stopping...", self.uid(), self._asyncio_process.pid)
        self._state_changed(ProcessData.STOPPING)

        try:
            # deal with process or process group
            kill_fn = os.kill
            pid = self._asyncio_process.pid

            if self._data.as_process_group:
                pid = os.getpgid(pid)
                kill_fn = os.killpg

            return await self._ensure_killed_may_raise(kill_fn, pid, int_timeout, term_timeout)

        except ProcessLookupError:
            msg = f"Failed to find process with pid: '{self.uid()}' it is no longer running."
            logger.warning(msg)
            return msg

        except OSError as excpt:
            logger.warning("Exception stopping process", exc_info=excpt)
            return "Exception while stopping process %s" % excpt.__class__.__name__

    def restart_ended_process(self):
        if self._data.state != ProcessData.ENDED:
            msg = f"Process {self.uid()} cannot be re-started in state: {self._data.state}"
            logger.warning(msg)
            return msg

        # reset process state
        self._data.reset()
        self._asyncio_process = None
        self._process_task = None

        return self.start_as_task()

    async def _read_stream(self, stream: asyncio.StreamReader, handler: Callable) -> None:
        while True:
            line = await stream.readline()
            if not line:
                break

            if handler is not None:
                handler(self, line)

    def start_as_task(self) -> Union[asyncio.Task, str]:
        if self._data.is_in_state(ProcessData.ENDED):
            logger.info("Restarting ended task: %s", self.uid())
            # reset process state
            self._data.reset()
            self._asyncio_process = None
            self._process_task = None

        if not self._data.is_in_state(ProcessData.INITIALIZED):
            msg = "Process cannot be started in state: %s" % self._data.state
            logger.warning(msg)
            return msg

        # change state to ensure single start, without an event
        self._data.state = ProcessData.STARTING
        self._process_task = asyncio.create_task(self._run_process())
        return self._process_task

    def get_start_task(self) -> asyncio.Task:
        return self._process_task

    def has_exit_code(self) -> bool:
        return self._data.exit_code is not None

    def exit_code(self) -> int:
        return self._data.exit_code

    def _state_changed(self, state: str) -> None:
        self._data.state = state
        # TODO: should it be run in separate task?
        # By not awaiting this function users can only call blocking code
        # What happens if I receive a RUNNING event and request stop?
        if self._state_change_listener is not None:
            self._state_change_listener(self)

    def __hash__(self):
        return self._data.uid.__hash__()

    def is_running(self) -> bool:
        return self._data.state == ProcessData.STARTED

    def has_completed(self) -> bool:
        return self._data.state == ProcessData.ENDED

    def uid(self) -> str:
        return self._data.uid

    def state(self) -> str:
        return self._data.state

    def get_data(self) -> ProcessData:
        return self._data

    async def _ensure_killed_may_raise(self, kill_fn, pid, int_timeout: float = 2, term_timeout: float = 2):
        # politely ask to interrupt the process
        kill_fn(pid, signal.SIGINT)
        # wait shortly to see if already stopped
        await asyncio.sleep(.01)
        # NOTE: we check for the exit code, which is only set at the end of start
        # _run_process and should indicate that the process has truly exited
        if self.has_exit_code():
            return self.exit_code()

        # sleep in chunks and test if process has stopped
        sleep_interval = .5
        while int_timeout > 0:
            await asyncio.sleep(min(sleep_interval, int_timeout))
            int_timeout -= sleep_interval

            if self.has_exit_code():
                return self.exit_code()

        logger.debug("Process[%s]: Stopping, escalating to SIGTERM", self.uid())
        kill_fn(pid, signal.SIGTERM)
        while term_timeout > 0:
            await asyncio.sleep(min(sleep_interval, term_timeout))
            term_timeout -= sleep_interval

            if self.has_exit_code():
                return self.exit_code()

        logger.debug("Process[%s]: Stopping, escalating to SIGKILL", self.uid())
        kill_fn(pid, signal.SIGKILL)

        # SIGKILL cannot be avoided the exit code will be set
        while not self.has_exit_code():
            await asyncio.sleep(.01)
