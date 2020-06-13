import asyncio
import logging
from asyncio.tasks import Task
from typing import Dict, Union, Optional, List

from wsmonitor.process.process import Process
from wsmonitor.process.data import ProcessData, OutputEvent, StateChangedEvent

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ProcessMonitor:

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

        process = Process(ProcessData(name, command, as_process_group))
        self._processes[name] = process
        logger.info("Registered new process %s", name)
        return process

    def start_process(self, uid: str) -> Union[str, Process]:

        if uid not in self._processes:
            return "No process with name '%s'" % uid

        process = self._processes[uid]
        if process.is_running():
            return "Process '%s' is already running" % uid

        process.set_state_listener(
            lambda process: self._state_event_queue.put_nowait(
                StateChangedEvent(process.uid(), process.state(), process.exit_code())))
        process.set_output_listener(
            lambda proc, output: self._output_event_queue.put_nowait(OutputEvent(proc.uid(), output.decode())))

        return process.start_as_task()

    async def stop_process(self, uid: str) -> Union[int, str]:
        if uid not in self._processes:
            return "No process with name '%s'" % uid

        process = self._processes[uid]
        return await process.stop()

    async def restart_process(self, uid: str):
        result = await self.stop_process(uid)
        if isinstance(result, str):
            return f"Failed to stop process, cannot restart: {result}"

        process = self._processes[uid]
        return process.restart_ended_process()

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
            logger.info("Stopping process: %s", process.uid())
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

    def get_processes(self) -> List[ProcessData]:
        return [proc.get_data() for proc in self._processes.values()]
