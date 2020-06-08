import asyncio
import json
import logging

from ws_pmom.format import JsonFormattable
from ws_pmom.process_monitor import ProcessMonitor
from ws_pmom.ws_monitor import WebsocketActionServer, CallbackClientAction, ActionResponse, ActionFailure

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ProcessSummaryEvent(JsonFormattable):

    def __init__(self, data):
        super().__init__(data)


class WebsocketProcessMonitor(ProcessMonitor, WebsocketActionServer):

    def __init__(self):
        ProcessMonitor.__init__(self)
        WebsocketActionServer.__init__(self)

        self.periodic_update_sleep_duration = 10
        self.known_actions.update({
            "register": CallbackClientAction("register", ["uid", "cmd", "group"], self.__register_action),
            "start": CallbackClientAction("start", ["uid"], self.__start_action),
            "stop": CallbackClientAction("stop", ["uid"], self.__stop_action),
        })

    async def run(self):
        asyncio.create_task(self.listen())
        self.start_monitor()


    async def __register_action(self, uid: str, cmd: str, group=True) -> ActionResponse:
        result = self.register_process(uid, cmd, group)
        if isinstance(result, str):
            return ActionFailure("registered", {"uid": uid, "data": result})

        return ActionResponse("registered", True, {"uid": uid})

    async def __start_action(self, uid: str) -> ActionResponse:
        result = self.start_process(uid)
        print("Result", result)
        if isinstance(result, str):
            return ActionFailure("start", {"uid": uid, "data": result})

        return ActionResponse("start", True, {"uid": uid})

    async def __stop_action(self, uid: str) -> ActionResponse:
        result = await self.stop_process(uid)
        if isinstance(result, str):
            return ActionFailure("stop", {"uid": uid, "data": result})

        return ActionResponse("stop", True, {"uid": uid, "data": result})

    async def _periodic_update_func(self) -> None:
        self._is_running = True
        while self._is_running:
            await asyncio.sleep(self.periodic_update_sleep_duration)
            print("Periodic update")
            data = ProcessSummaryEvent(self.as_json_data())
            await self.broadcast(str(data))

    def _get_monitor_tasks(self):
        tasks = ProcessMonitor._get_monitor_tasks(self)
        periodic_state_update_task = asyncio.create_task(self._periodic_update_func())
        tasks.append(periodic_state_update_task)
        return tasks

    async def on_state_event(self, event):
        logger.info("Received state event: %s", event)
        await self.broadcast(json.dumps(event.get_data()))

    async def on_output_event(self, event):
        await self.broadcast(json.dumps(event.get_data()))

    async def shutdown(self):
        logger.debug("Shutdown initiated")
        # First stop all processes
        await self.shutdown_monitor()
        await self.trigger_server_shutdown()
        #asyncio.get_event_loop().stop()
