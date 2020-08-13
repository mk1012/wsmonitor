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
OutputCallback = Callable[['Process', bytes], None]


class Process:
    def __init__(self, process_data: ProcessData) -> None:
        self._data = process_data
        self._asyncio_process: Optional[
            asyncio.subprocess.Process] = None  # pylint: disable=no-member
        self._process_task: Optional[asyncio.Task] = None
        self._state_change_listener: Optional[StateChangeCallback] = None
        self._output_listener: Optional[OutputCallback] = None

    def set_state_listener(self, listener: StateChangeCallback) -> None:
        self._state_change_listener = listener

    def set_output_listener(self, listener: OutputCallback) -> None:
        self._output_listener = listener

    async def _run_process(self, **kwargs) -> int:
        preexec_fn = None
        if self._data.as_process_group:
            # Run process in a new process group
            # https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
            preexec_fn = os.setsid

        command = self._data.get_command(**kwargs)
        logger.debug("Process[%s]: starting command: %s", self._data.uid, command)
        try:

            self._asyncio_process = await asyncio.create_subprocess_shell(
                command, stdout=PIPE, stderr=PIPE,
                preexec_fn=preexec_fn, bufsize=0)
        except Exception as excpt:
            logger.warning(f"Failed to start process[{self.uid()}: {excpt}")
            if self._output_listener is not None:
                self._output_listener(self, f"{excpt}\n".encode('ascii'))

            self._state_changed(ProcessData.ENDED)
            return -1

        logger.debug("Process[%s](%d): running", self._data.uid, self._asyncio_process.pid)

        # TODO(mark): we need to process the output to not deadlock
        # Schedule the read tasks and after that signal the state change
        self._stream_future = asyncio.gather(
            self._read_stream(self._asyncio_process.stdout,
                              self._output_listener),
            self._read_stream(self._asyncio_process.stderr,
                              self._output_listener)
        )
        self._state_changed(ProcessData.STARTED)

        try:
            # start the read tasks and wait for them to complete
            await self._stream_future
            self._data.exit_code = await self._asyncio_process.wait()
        except CancelledError:
            logger.warning("Process[%s]: Reading cancelled! Stopping process",
                           self.uid())
            await self.stop()

        self._data.ensure_exit_code(-1)
        logger.debug("Process[%s]: has exited with: %d", self.uid(),
                     self._data.exit_code)
        self._state_changed(ProcessData.ENDED)

        return self._data.exit_code

    async def stop(self, int_timeout: float = 2, term_timeout: float = 2) -> \
            Union[int, str]:

        if not self.is_running():
            return f"'{self.uid()}' is not running, cannot stop it"

        logger.debug("Process[%s](%d): stopping...", self.uid(),
                     self._asyncio_process.pid)
        self._state_changed(ProcessData.STOPPING)

        try:
            # deal with process or process group
            kill_fn = os.kill
            pid = self._asyncio_process.pid

            if self._data.as_process_group:
                pid = os.getpgid(pid)
                kill_fn = os.killpg

            return await self._ensure_killed_may_raise(
                kill_fn, pid, int_timeout, term_timeout)

        except ProcessLookupError:
            msg = f"Failed to find process with pid: '{self.uid()}' it is no longer running."
            logger.warning(msg)
            return msg

        except OSError as excpt:
            logger.warning("Exception stopping process", exc_info=excpt)
            return "Exception while stopping process %s" % excpt.__class__.__name__

    def restart_ended_process(self, **kwargs) -> Union[str, asyncio.Future]:
        if self._data.state != ProcessData.ENDED:
            msg = f"Process {self.uid()} cannot be re-started in state: {self._data.state}"
            logger.warning(msg)
            return msg

        # reset process state
        self._data.reset()
        self._asyncio_process = None
        self._process_task = None

        return self.start_as_task(**kwargs)

    async def _read_stream(self, stream: asyncio.StreamReader,
                           handler: Callable) -> None:
        while True:
            line = await stream.readline()
            if not line:
                break

            if handler is not None:
                handler(self, line)

    def start_as_task(self, **kwargs) -> Union[asyncio.Future, str]:
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
        self._process_task = asyncio.ensure_future(self._run_process(**kwargs))
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

    async def _ensure_killed_may_raise(self, kill_fn, pid,
                                       int_timeout: float = 2,
                                       term_timeout: float = 2):
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

        logger.debug("Process[%s]: Stopping, escalating to SIGTERM",
                     self.uid())
        kill_fn(pid, signal.SIGTERM)
        while term_timeout > 0:
            await asyncio.sleep(min(sleep_interval, term_timeout))
            term_timeout -= sleep_interval

            if self.has_exit_code():
                return self.exit_code()

        logger.debug("Process[%s]: Stopping, escalating to SIGKILL",
                     self.uid())

        # Kill regularly, also kill the asyncio process
        try:
            kill_fn(pid, signal.SIGKILL)
        except:
            pass
        finally:
            self._asyncio_process.kill()

        # Make sure we are no longer reading (maybe call this earlier?)
        if self._stream_future is not None:
            self._stream_future.cancel()

        logger.debug("Process[%s]: Waiting for exit code", self.uid())
        while not self.has_exit_code():
            await asyncio.sleep(.1)

        return self.exit_code()

    def update_data(self, command: str, as_process_group: bool) -> None:
        if not self._data.is_in_state(ProcessData.INITIALIZED,
                                      ProcessData.ENDED):
            logger.warning("Cannot change process data while it is active")
            return

        self._data.command = command
        self._data.as_process_group = as_process_group
