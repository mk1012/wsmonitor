import asyncio
import logging

import websockets

from wsmonitor.process.data import ProcessSummaryEvent, StateChangedEvent, \
    OutputEvent, ActionResponse, ActionFailure
from wsmonitor.process.process_monitor import ProcessMonitor
from wsmonitor.ws_monitor import WebsocketActionServer, CallbackClientAction

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class WebsocketProcessMonitor(ProcessMonitor, WebsocketActionServer):

    def __init__(self, output_broadcast_timeout=.5):
        ProcessMonitor.__init__(self)
        WebsocketActionServer.__init__(self)

        self._output_queue = {}
        self.periodic_update_timeout = 30
        self.periodic_output_broadcast = output_broadcast_timeout
        self.trigger_periodic_event = asyncio.Event()
        self._is_running = False

        self.known_actions.update({
            "add": CallbackClientAction("add", ["uid", "cmd", "group",
                                                "command_kwargs"],
                                        self.__add_action,
                                        defaults={"command_kwargs": None}),
            "remove": CallbackClientAction("remove", ["uid"],
                                           self.__remove_action),
            "start": CallbackClientAction("start", ["uid", "command_kwargs"],
                                          self.__start_action,
                                          defaults={"command_kwargs": {}}),
            "restart": CallbackClientAction("restart", ["uid"],
                                            self.__restart_action),
            "stop": CallbackClientAction("stop", ["uid"], self.__stop_action),
            "list": CallbackClientAction("list", [], self.__list_action),
        })

    async def welcome_client(self,
                             websocket: websockets.WebSocketClientProtocol):
        await websocket.send(str(ProcessSummaryEvent(self.get_processes())))

    async def run(self, host="127.0.0.1", port=8766):
        # TODO(mark): the server seems to cause problems with other task (they are not scheduled?)
        # therefore start in another task
        server_task = asyncio.ensure_future(self.start_server(host, port))
        self.start_monitor()
        return await server_task

    async def shutdown(self):
        logger.info("Shutdown initiated")

        # stop process monitor and websocket server
        await ProcessMonitor.shutdown(self)
        await self.stop_server()

    async def __add_action(self, uid: str, cmd: str,
                           group=True, command_kwargs=None) -> ActionResponse:
        result = self.add_process(uid, cmd, group,command_kwargs)
        if isinstance(result, str):
            return ActionFailure(uid, "add", result)

        self.trigger_periodic_event.set()
        return ActionResponse(uid, "add", True, True)

    async def __remove_action(self, uid: str) -> ActionResponse:
        result = self.remove_process(uid)
        if isinstance(result, str):
            return ActionFailure(uid, "remove", result)

        self.trigger_periodic_event.set()
        return ActionResponse(uid, "remove", True)

    async def __list_action(self) -> ActionResponse:
        payload = [proc.to_json() for proc in self.get_processes()]
        return ActionResponse(None, "list", True, payload)

    async def __start_action(self, uid: str, command_kwargs) -> ActionResponse:
        result = self.start_process(uid, **command_kwargs)
        if isinstance(result, str):
            return ActionFailure(uid, "start", result)

        self.trigger_periodic_event.set()
        return ActionResponse(uid, "start", True)

    async def __restart_action(self, uid: str) -> ActionResponse:
        result = await self.restart_process(uid, ignore_stop_failure=True)
        if isinstance(result, str):
            return ActionFailure(uid, "restart", result)

        self.trigger_periodic_event.set()
        return ActionResponse(uid, "restart", True)

    async def __stop_action(self, uid: str) -> ActionResponse:
        result = await self.stop_process(uid)
        success = isinstance(result, int)
        if success:
            self.trigger_periodic_event.set()

        return ActionResponse(uid, "stop", success, result)

    async def _periodic_update_func(self) -> None:
        while True:

            try:
                await asyncio.wait_for(self.trigger_periodic_event.wait(),
                                       self.periodic_update_timeout)
            except asyncio.TimeoutError:
                pass

            logger.debug("Triggered periodic update. Via event: %s",
                         self.trigger_periodic_event.is_set())
            self.trigger_periodic_event.clear()
            event = ProcessSummaryEvent(self.get_processes())
            await self.broadcast(event.to_json_str())

    async def _periodic_output_broadcast(self) -> None:
        logger.info("Periodic output started")
        while self._is_monitor_running:
            await asyncio.sleep(self.periodic_output_broadcast)
            for event in self._output_queue.values():
                await self.broadcast(event.to_json_str())
            self._output_queue.clear()

    def _get_monitor_tasks(self):
        tasks = ProcessMonitor._get_monitor_tasks(self)
        periodic_output_task = asyncio.ensure_future(
            self._periodic_output_broadcast())
        periodic_state_update_task = asyncio.ensure_future(
            self._periodic_update_func())
        tasks.append(periodic_output_task)
        tasks.append(periodic_state_update_task)
        return tasks

    async def on_state_event(self, event: StateChangedEvent):
        logger.debug("Received state event: %s", event.to_json_str())
        await self.broadcast(event.to_json_str())

    async def on_output_event(self, event: OutputEvent):
        logger.debug("Received output event: %s", event.to_json_str())
        output = self._output_queue.get(event.uid, None)
        if output is None:
            self._output_queue[event.uid] = event
        else:
            self._output_queue[event.uid].output += event.output
