import logging
import asyncio
import os
import signal
import sys
import time
from asyncio import CancelledError
from asyncio.subprocess import STDOUT, PIPE
from typing import Union, Callable, Coroutine

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(lineno)d -  %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProcessOutput(object):

    def __init__(self):
        self.stdout = []
        self.stderr = []
        self.exit_code = None

    def reset(self):
        self.stdout.clear()
        self.stderr.clear()
        self.exit_code = None


class Process(object):
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    BEING_KILLED = "being_killed"
    ENDED = "ended"

    def __init__(self, uid: str, command, as_process_group=False):
        self._uid = uid
        self._command = command
        self._exit_code = None
        self._asyncio_process = None  # type: Union[asyncio.subprocess.Process, None]
        self._as_process_group = as_process_group
        self._process_task = None  # type: Union[asyncio.Task, None]
        self._state = Process.INITIALIZED
        self._state_change_listener = None
        self._output_listener = None

    def __hash__(self):
        return self._uid.__hash__()

    def set_state_listener(self, listener):
        self._state_change_listener = listener

    def set_output_listener(self, listener):
        self._output_listener = listener

    async def _run_process(self):
        preexec_fn = None
        if self._as_process_group:
            # Run process in a new process group
            # https://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true
            preexec_fn = os.setsid

        logger.debug("Process[%s]: starting", self._uid)
        self._asyncio_process = await asyncio.create_subprocess_shell(
            self._command, stdout=PIPE, stderr=PIPE, preexec_fn=preexec_fn)

        self._state_changed(Process.RUNNING)

        # start the read tasks and wait for them to complete
        try:
            await asyncio.wait([
                self._read_stream(self._asyncio_process.stdout, self._output_listener),
                self._read_stream(self._asyncio_process.stderr, self._output_listener)
            ])
            self._exit_code = await self._asyncio_process.wait()

        except CancelledError:
            logger.warning("Process[%s]: Caught task CancelledError! Stopping process instead", self._uid)
            await self.stop()

            if self._exit_code is None:  # ensure there is an exit code
                self._exit_code = -1

        logger.debug("Process[%s]: has exited with: %d", self._uid, self._exit_code)

        self._state_changed(Process.ENDED)
        return self._exit_code

    async def stop(self, int_timeout=2, term_timeout=2):
        if not self.is_running():
            logger.warning("Process[%s]: Is not running, cannot stop", self._uid)
            return

        logger.debug("Process[%s](%d): stopping...", self._uid, self._asyncio_process.pid)
        self._state_changed(Process.BEING_KILLED)
        try:

            # deal with process or process group
            kill_fn = os.kill
            pid = self._asyncio_process.pid
            if self._as_process_group:
                pid = os.getpgid(pid)
                kill_fn = os.killpg

            # politely ask to interrupt the process
            kill_fn(pid, signal.SIGINT)
            # wait shortly to see if already stopped
            await asyncio.sleep(.01)
            # NOTE: we check for the exit code, which is set at the end of start
            # _run_process and should indicate that the process has truly exited
            if self.has_exit_code():
                return

            # sleep in chunks and test if process has stopped
            sleep_interval = .5
            while int_timeout > 0:
                await asyncio.sleep(min(sleep_interval, int_timeout))
                int_timeout -= sleep_interval

                if self.has_exit_code():
                    return

            logger.debug("Process[%s]: Stopping, escalating to SIGTERM", self._uid)
            kill_fn(pid, signal.SIGTERM)
            while term_timeout > 0:
                await asyncio.sleep(min(sleep_interval, term_timeout))
                term_timeout -= sleep_interval

                if self.has_exit_code():
                    return

            logger.debug("Process[%s]: Stopping, escalating to SIGKILL", self._uid)
            kill_fn(pid, signal.SIGKILL)
            # SIGKILL cannot be avoided
            while not self.has_exit_code():
                await asyncio.sleep(.01)

        except ProcessLookupError as ple:
            logger.warning("Failed to find process %s", ple)
        except OSError as e:
            logger.debug("Exception stopping process: %s", e)

    async def restart(self):
        await self.stop()

        # TODO(mark): wait with a timeout and cancel if necessary
        # self._start_task.cancel() -> throws
        await self._process_task

        # reset process state
        self._exit_code = None
        self._asyncio_process = None
        self._state = Process.INITIALIZED
        self._process_task = None
        return self.start_as_task()

    @staticmethod
    async def _read_stream(stream: asyncio.StreamReader, handler: Callable):
        while True:
            line = await stream.readline()
            if not line:
                break

            if handler is not None:
                handler(line)

    def start_as_task(self):
        if self._state != Process.INITIALIZED:
            logger.warning("Process cannot be started in state: %s", self._state)
            return None

        self._state = self.STARTING  # change state to ensure single start
        self._process_task = asyncio.create_task(self._run_process())
        return self._process_task

    def get_start_task(self):
        return self._process_task

    def has_exit_code(self):
        return self._exit_code is not None

    def _state_changed(self, state):
        self._state = state
        # TODO: should it be run in separate task?
        # By not awaiting this function users can only call blocking code
        # What happens if I receive a RUNNING event and request stop?
        if self._state_change_listener is not None:
            self._state_change_listener(self, state)

    def is_running(self):
        return self._state == Process.RUNNING

    def has_completed(self):
        return self._state == Process.ENDED

    def get_name(self):
        return self._uid
