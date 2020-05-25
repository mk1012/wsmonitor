import asyncio
import logging
import signal
from typing import Dict, Set, List

from process import Process

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProcessEvent(object):
    def __init__(self, process, data):
        self.process = process
        self.data = data

    def get_data(self):
        return {"__type__": self.__class__.__name__, "process": self.process.get_name(), "data": self.data}

    def __str__(self):
        return str(self.get_data())

class StateChangedEvent(ProcessEvent):

    def __init__(self, process, data):
        super().__init__(process, data)


class OutputEvent(ProcessEvent):

    def __init__(self, process, data):
        super().__init__(process, data)


class ProcessMonitor(object):

    def __init__(self):
        self._is_running = False
        self._processes = {}  # type: Dict[str, Process]
        self._state_event_queue = asyncio.Queue()
        self._output_event_queue = asyncio.Queue()

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

    async def start(self, name):
        if name not in self._processes:
            logger.warning("No process with name '%s'", name)
            return None

        process = self._processes[name]
        if process.is_running():
            logger.warning("Process '%s' is already running", name)

            return None

        process.set_state_listener(
            lambda proc, state: self._state_event_queue.put_nowait(StateChangedEvent(proc, state)))
        process.set_output_listener(
            lambda output: self._output_event_queue.put_nowait(OutputEvent(process, output.decode())))
        return process.start_as_task()

    async def stop(self, name):
        if name not in self._processes:
            logger.warning("No process with name '%s'", name)
            return

        process = self._processes[name]
        await process.stop()

    def start_monitor_tasks(self):
        # TODO: combine output events?
        self._output_event_task = asyncio.create_task(
            self._process_queue(self._output_event_queue, self.on_output_event))
        self._state_event_task = asyncio.create_task(self._process_queue(self._state_event_queue, self.on_state_event))
        self._monitor_tasks = asyncio.gather(self._output_event_task, self._state_event_task)
        return self._monitor_tasks

    async def on_state_event(self, event):
        print("State event", event)

    async def on_output_event(self, event):
        pass #print("Output event", event)

    async def _process_queue(self, queue: asyncio.Queue, handler):
        self._is_running = True
        while self._is_running:
            event = await queue.get()
            await handler(event)

    async def shutdown(self):
        running = list(filter(lambda proc: proc.is_running(), self._processes.values()))
        logger.info("Initiating shutdown, stopping %d running processes", len(running))

        for proc in running:
            logger.info("[ProcReg] Stopping process: %s", proc.get_name())
            await proc.stop()

        # stop or cancel the monitor task
        self._is_running = False
        await asyncio.sleep(.1)

        self._monitor_tasks.cancel()
        try:
            await self._monitor_tasks
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
        loop.run_until_complete(reg.start_monitor_tasks())
    finally:
        loop.stop()
        loop.close()
