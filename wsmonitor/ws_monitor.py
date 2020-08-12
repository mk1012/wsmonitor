import json
import logging
from typing import Dict, List, Any, Callable, Awaitable, Optional

import websockets
from websockets import WebSocketException, ConnectionClosedOK

from wsmonitor.process.data import ActionResponse, ActionFailure

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ClientAction:

    def __init__(self, action_id):
        self.action_id = action_id

    async def call_with_data(self, json_data: Dict[str, Any]):
        raise NotImplementedError()

    def __str__(self):
        return f"{self.__class__.__name__}({self.action_id})"


class CallbackClientAction(ClientAction):

    def __init__(self, action_id, keys: List[str],
                 func: Callable[[Any], Awaitable[ActionResponse]],
                 defaults=None):
        ClientAction.__init__(self, action_id)
        self.keys = keys
        self.func = func
        self.defaults: Dict = {} if defaults is None else defaults

    async def call_with_data(self, json_data: Dict[str, str]) -> ActionResponse:

        missing = set(self.keys) - set(json_data.keys())
        if len(missing) > 0:
            # check if all of the missing keys are set in the defaults
            missing_defaults = missing - set(self.defaults.keys())
            if len(missing_defaults) == 0:
                json_data.update({key: self.defaults[key] for key in missing})
            else:
                return ActionFailure(None, self.action_id,
                                     f"Missing keys: {missing}")

        response = await self.func(*(json_data[key] for key in self.keys))
        logger.info("Action '%s' result: %s", self.action_id, response)
        return response


class WebsocketActionServer:

    def __init__(self):
        super().__init__()
        self.known_actions = {}  # type: Dict[str, ClientAction]
        self.server: Optional[websockets.server.WebSocketServer] = None
        self.clients = set()

    def add_action(self, name: str, action: ClientAction):
        if name in self.known_actions:
            return False

        self.known_actions[name] = action
        return True

    async def stop_server(self):
        logger.info("Server shutdown triggered")
        if self.server is None:
            logger.info("Server is None (not running)")
            return
        self.server.close()
        await self.server.wait_closed()
        logger.info("Server closed")

    async def start_server(self, host="127.0.0.1", port=8766):
        logger.info("Starting server on %s:%d", host, port)
        try:
            self.server = await websockets.serve(self.__on_client_connected,
                                                 host, port)
        except Exception as excpt:
            logger.error("Failed to start webserver: %s", excpt)
            return False

        logger.info("Webserver started")
        return True

    async def __on_client_connected(self, websocket, _):
        # TODO(mark) is every listen()-invocation, run in its own task?
        self.clients.add(websocket)
        logger.debug("Client added: %s", websocket)

        try:
            await self.__client_loop_may_throw(websocket)
        except ConnectionClosedOK:
            pass
        except WebSocketException as excpt:
            logger.info("WebSocket connection error: %s", excpt)

        finally:
            self.clients.remove(websocket)
            logger.debug("Client removed: %s", websocket)

    async def welcome_client(self, websocket):
        pass

    async def __client_loop_may_throw(self,
                                      websocket: websockets.WebSocketServerProtocol):
        # Send initial information
        await self.welcome_client(websocket)

        while True:
            data = await websocket.recv()  # raises on close/error

            result = await self.__handle_input_from_client(data)
            await websocket.send(result.to_json_str())

    async def broadcast(self, line: str):
        # TODO(mark): this blocks the process processing application!
        clients = self.clients.copy()
        for client in clients:
            try:
                await client.send(line)
            except WebSocketException as excpt:
                logger.warning("WS write failed: %s", excpt)
                # TODO(mark): assumption: __on_client_connected will remove the failed websocket

    async def __handle_input_from_client(self, line: str) -> ActionResponse:
        try:
            json_data = json.loads(line)
        except json.JSONDecodeError:
            return ActionFailure(None, "invalid",
                                 "Received invalid input: %s" % line)

        action_name = json_data.get("action", None)
        payload = json_data.get("data", None)

        if action_name not in self.known_actions or payload is None:
            logger.warning("Invalid action %s", action_name)
            return ActionFailure(None, action_name,
                                 f"Invalid action '{action_name}' or missing data")

        action = self.known_actions[action_name]
        return await action.call_with_data(payload)
