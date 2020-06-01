import asyncio
import logging
import signal
from asyncio.tasks import Task
from typing import Dict, Union

from process import Process
from process_data import ProcessData

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProcessEvent(object):
    def __init__(self, process, data):
        self.process = process
        self.data = data
        self.type = self.__class__.__name__.lower()

    def get_data(self):
        return {"type": self.type, "uid": self.process.get_uid(), "data": self.data}

    def __str__(self):
        return str(self.get_data())


class StateChangedEvent(ProcessEvent):

    def __init__(self, process, data):
        super().__init__(process, data)
        self.type = "process_state_changed"


class OutputEvent(ProcessEvent):

    def __init__(self, process, data):
        super().__init__(process, data)


class ProcessMonitor(object):

    def __init__(self):
        self._is_running = False
        self._processes = {}  # type: Dict[str, Process]
        self._state_event_queue = asyncio.Queue()
        self._output_event_queue = asyncio.Queue()

        self._monitoring_tasks_task = None  # type: Union[Task, None]

    async def register(self, name, command, as_process_group=True):
        if name in self._processes:
            logger.warning("Process with name '%s' already known", name)
            p = self._processes[name]
            # TODO(mark): update command?
            return p
        logger.info("Registered new process %s", name)

        p = Process(ProcessData(name, command, as_process_group))
        self._processes[name] = p
        return p

    def as_json_data(self):
        return [self._processes[key]._data.as_dict() for key in self._processes]

    def start(self, uid):
        # type: (str) -> Union[str, Process]

        if uid not in self._processes:
            return "No process with name '%s'" % uid

        process = self._processes[uid]
        if process.is_running():
            return "Process '%s' is already running" % uid

        process.set_state_listener(
            lambda proc, state: self._state_event_queue.put_nowait(StateChangedEvent(proc, state)))
        process.set_output_listener(
            lambda output: self._output_event_queue.put_nowait(OutputEvent(process, output.decode())))

        return process.start_as_task()

    async def stop(self, name):
        if name not in self._processes:
            return "No process with name '%s'" % name

        process = self._processes[name]
        return await process.stop()

    def _get_monitor_tasks(self):
        # TODO: combine output events?
        state_task = asyncio.create_task(self._process_queue(self._state_event_queue, self.on_state_event))
        output_task = asyncio.create_task(self._process_queue(self._output_event_queue, self.on_output_event))
        return [state_task, output_task]

    def start_monitor_tasks(self):
        tasks = self._get_monitor_tasks()
        self._monitoring_tasks_task = asyncio.gather(*tasks)
        return self._monitoring_tasks_task

    async def on_state_event(self, event):
        print("State event", event)

    async def on_output_event(self, event):
        pass  # print("Output event", event)

    async def _process_queue(self, queue: asyncio.Queue, handler):
        self._is_running = True
        while self._is_running:
            event = await queue.get()
            await handler(event)

    async def shutdown(self):
        running = list(filter(lambda proc: proc.is_running(), self._processes.values()))
        logger.info("Initiating shutdown, stopping %d running processes", len(running))

        for process in running:
            logger.info("[ProcReg] Stopping process: %s", process.get_uid())
            await process.stop()  # will cancel all process tasks as well

        # stop or cancel the monitor tasks
        self._is_running = False
        await asyncio.sleep(.1)

        self._monitoring_tasks_task.cancel()
        try:
            await self._monitoring_tasks_task
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
