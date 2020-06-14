import asyncio
import logging

import websockets

from wsmonitor.process.data import ProcessSummaryEvent, StateChangedEvent, OutputEvent, ActionResponse, ActionFailure
from wsmonitor.process.process_monitor import ProcessMonitor
from wsmonitor.ws_monitor import WebsocketActionServer, CallbackClientAction

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class WebsocketProcessMonitor(ProcessMonitor, WebsocketActionServer):

    def __init__(self):
        ProcessMonitor.__init__(self)
        WebsocketActionServer.__init__(self)

        self.periodic_update_timeout = 30
        self.trigger_periodic_event = asyncio.Event()
        self._is_running = False

        self.known_actions.update({
            "register": CallbackClientAction("register", ["uid", "cmd", "group"], self.__register_action),
            "start": CallbackClientAction("start", ["uid"], self.__start_action),
            "restart": CallbackClientAction("start", ["uid"], self.__restart_action),
            "stop": CallbackClientAction("stop", ["uid"], self.__stop_action),
        })

    async def welcome_client(self, websocket: websockets.WebSocketClientProtocol):
        await websocket.send(str(ProcessSummaryEvent(self.get_processes())))

    async def run(self, host="127.0.0.1", port=8766):
        # TODO(mark): the server seems to cause problems with other task (they are not scheduled?)
        # therefore start in another task
        asyncio.create_task(self.start_server(host, port))
        self.start_monitor()

    async def shutdown(self):
        logger.info("Shutdown initiated")

        # stop process monitor and websocket server
        await ProcessMonitor.shutdown(self)
        await self.stop_server()

    async def __register_action(self, uid: str, cmd: str, group=True) -> ActionResponse:
        result = self.register_process(uid, cmd, group)
        if isinstance(result, str):
            return ActionFailure(uid, "registered", result)

        self.trigger_periodic_event.set()
        return ActionResponse(uid, "registered", True)

    async def __start_action(self, uid: str) -> ActionResponse:
        result = self.start_process(uid)
        if isinstance(result, str):
            return ActionFailure(uid, "start", result)

        self.trigger_periodic_event.set()
        return ActionResponse(uid, "start", True)

    async def __restart_action(self, uid: str) -> ActionResponse:
        result = await self.restart_process(uid)
        if isinstance(result, str):
            return ActionFailure(uid, "restart", result)

        self.trigger_periodic_event.set()
        return ActionResponse(uid, "restart", True)

    async def __stop_action(self, uid: str) -> ActionResponse:
        result = await self.stop_process(uid)
        success = isinstance(result, str)
        if success:
            self.trigger_periodic_event.set()

        return ActionResponse(uid, "stop", success, result)

    async def _periodic_update_func(self) -> None:
        while True:

            try:
                await asyncio.wait_for(self.trigger_periodic_event.wait(), self.periodic_update_timeout)
            except asyncio.TimeoutError:
                pass

            logger.info("Triggered periodic update. Via event: %s", self.trigger_periodic_event.is_set())
            self.trigger_periodic_event.clear()
            data = ProcessSummaryEvent(self.get_processes())
            await self.broadcast(str(data))

    def _get_monitor_tasks(self):
        tasks = ProcessMonitor._get_monitor_tasks(self)
        periodic_state_update_task = asyncio.create_task(self._periodic_update_func())
        tasks.append(periodic_state_update_task)
        return tasks

    async def on_state_event(self, event: StateChangedEvent):
        logger.debug("Received state event: %s", str(event))
        await self.broadcast(str(event))

    async def on_output_event(self, event: OutputEvent):
        logger.debug("Received output event: %s", str(event))
        await self.broadcast(str(event))
