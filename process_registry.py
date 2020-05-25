import asyncio
import logging
import signal
from typing import Dict, Set

from process import Process

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProcessEvent(object):
    def __init__(self, process, data):
        self.process = process
        self.data = data

class StateChangedEvent(ProcessEvent):

    def __init__(self, process, data):
        super().__init__(process, data)

class ProcessMonitor(object):

    def __init__(self):
        self._is_running = False
        self._processes = {}  # type: Dict[str, Process]
        self._running_processes = set()  # type: Set[Process]
        self._state_changed_queue = asyncio.Queue()

    async def register(self, name, command, as_process_group=True):
        if name in self._processes:
            logger.warning("Process with name '%s' already known", name)
            p = self._processes[name]
            # TODO(mark): update command?
            return p
        logger.info("Registered new process %s", name)
        p = Process(name, command, as_process_group)
        self._processes[name] = p
        return p

    async def _handle_on_state_changed(self, process, state):
        print(state)
        if state == Process.RUNNING:
            self._running_processes.add(process)

        elif state == Process.ENDED and process in self._running_processes:
            self._running_processes.remove(process)

    def _on_output(self, line):
        logger.debug(line)

    async def start(self, name):
        if name not in self._processes:
            logger.warning("No process with name '%s'", name)
            return None

        process = self._processes[name]
        if process.is_running():
            logger.warning("Process '%s' is already running", name)

            return None

        process.set_state_listener(lambda proc, state: self._state_changed_queue.put_nowait((proc, state)))
        process.set_output_listener(self._on_output)
        return process.start_as_task()

    async def stop(self, name):
        if name not in self._processes:
            logger.warning("No process with name '%s'", name)
            return

        process = self._processes[name]
        await process.stop()

    def start_state_monitor_task(self):
        self._state_monitor_task = asyncio.create_task(self._monitor())
        return self._state_monitor_task

    async def _monitor(self):
        self._is_running = True
        while self._is_running:
            process, state = await self._state_changed_queue.get()
            await self._handle_on_state_changed(process, state)

    async def shutdown(self):
        logger.info("Initiating shutdown, stopping %d running processes", len(self._running_processes))
        running = self._running_processes.copy()
        for proc in running:
            logger.info("[ProcReg] Stopping process: %s", proc.get_name())
            await proc.stop()

        # stop or cancel the monitor task
        self._is_running = False
        await asyncio.sleep(.1)
        self._state_monitor_task.cancel()
        try:
            await self._state_monitor_task
        except asyncio.CancelledError:
            pass
        logger.info("All processes stopped")


if __name__ == '__main__':
    reg = ProcessMonitor()
    loop = asyncio.get_event_loop()


    async def populate():
        reg.register("py", "python3 signal_inhibit.py")
        reg.register("ls", "source ~/Arbeit_IPR/ws/devel/setup.bash && roslaunch rll_move move_iface.launch")
        reg.start("py")
        reg.start("ls")


    def shutdown_handler(_1, _2):
        loop.create_task(reg.shutdown())


    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    loop.set_debug(True)
    loop.create_task(populate())
    try:
        loop.run_until_complete(reg.start_state_monitor_task(loop))
    finally:
        loop.stop()
        loop.close()
