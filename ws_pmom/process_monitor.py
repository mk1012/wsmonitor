import asyncio
import logging
from asyncio.tasks import Task
from typing import Dict, Union, Optional, List

from ws_pmom.format import JsonFormattable
from ws_pmom.process import Process
from ws_pmom.process_data import ProcessData

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProcessEvent(JsonFormattable):
    def __init__(self, process, data):
        super().__init__({"uid": process.get_uid(), "data": data})


class StateChangedEvent(ProcessEvent):

    def __init__(self, process, data):
        super().__init__(process, data)


class OutputEvent(ProcessEvent):

    def __init__(self, process, data):
        super().__init__(process, data)


class ProcessMonitor(object):

    def __init__(self) -> None:
        self._is_monitor_running = False
        self._processes: Dict[str, Process] = {}
        self._state_event_queue = asyncio.Queue()
        self._output_event_queue = asyncio.Queue()
        self._gather_monitoring_tasks_future: Optional[Task] = None

    def register_process(self, name, command, as_process_group=True) -> Union[str, Process]:
        if name in self._processes:
            msg = f"Process with name '{name}' already known"
            logger.error(msg)
            return msg

        p = Process(ProcessData(name, command, as_process_group))
        self._processes[name] = p
        logger.info("Registered new process %s", name)
        return p

    def as_json_data(self) -> List[Dict]:
        return [self._processes[key]._data.as_dict() for key in self._processes]

    def start_process(self, uid: str) -> Union[str, Process]:

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

    async def stop_process(self, name: str) -> Union[int, str]:
        if name not in self._processes:
            return "No process with name '%s'" % name

        process = self._processes[name]
        return await process.stop()

    def _get_monitor_tasks(self) -> List[asyncio.Task]:
        # TODO: combine output events?
        state_task = asyncio.create_task(self._process_queue(self._state_event_queue, self.on_state_event))
        output_task = asyncio.create_task(self._process_queue(self._output_event_queue, self.on_output_event))
        return [state_task, output_task]

    def start_monitor(self) -> asyncio.Future:
        self._is_monitor_running = True
        tasks = self._get_monitor_tasks()
        self._gather_monitoring_tasks_future = asyncio.gather(*tasks)
        return self._gather_monitoring_tasks_future

    async def on_state_event(self, event):
        pass  # print("State event", event)

    async def on_output_event(self, event):
        pass  # print("Output event", event)

    async def _process_queue(self, queue: asyncio.Queue, handler):
        while self._is_monitor_running:
            event = await queue.get()
            await handler(event)

    async def shutdown_monitor(self) -> None:
        running = list(filter(lambda proc: proc.is_running(), self._processes.values()))
        logger.info("Initiating monitor shutdown, stopping %d running processes", len(running))

        for process in running:
            logger.info("Stopping process: %s", process.get_uid())
            await process.stop()  # will cancel all process tasks as well

        # stop or cancel the monitor tasks
        self._is_monitor_running = False
        await asyncio.sleep(.1)

        self._gather_monitoring_tasks_future.cancel()
        try:
            await self._gather_monitoring_tasks_future
        except asyncio.CancelledError:
            pass

        logger.info("Monitor shutdown complete, all processes stopped")