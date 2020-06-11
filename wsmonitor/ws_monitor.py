import json
import logging
from typing import Dict, List, Any, Callable, Awaitable, Optional

import websockets
from websockets import WebSocketException

from wsmonitor.process.data import ActionResponse, ActionFailure
from wsmonitor.process.process import Process

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ClientConnection():

    def __init__(self, websocket):
        self.websocket = websocket
        self.is_active = True

    def loop(self):
        pass


class ClientAction(object):

    def __init__(self, action_id):
        self.action_id = action_id

    def call_with_data(self, json_data: Dict[str, Any]):
        raise NotImplementedError()

    def __call__(self, *args, **kwargs):
        raise NotImplementedError()

    def __str__(self):
        return f"{self.__class__.__name__}({self.action_id})"


class CallbackClientAction(ClientAction):

    def __init__(self, action_id, keys: List[str], func: Callable[[Any], Awaitable[ActionResponse]]):
        ClientAction.__init__(self, action_id)
        self.keys = keys
        self.func = func

    async def call_with_data(self, json_data: Dict[str, str]) -> ActionResponse:
        if not all(map(lambda key: key in json_data.keys(), self.keys)):
            return ActionFailure(None, self.action_id, f"Not all required keys: {self.keys} set")

        response = await self.func(*(json_data[key] for key in self.keys))
        logger.info("Action '%s' result: %s", self.action_id, response)
        return response


class WebsocketActionServer:

    def __init__(self):
        super().__init__()
        self.periodic_update_timeout = 10
        self.known_actions = {}  # type: Dict[str, ClientAction]
        self.server: Optional[websockets.server.WebSocketServer] = None
        self.clients = set()

    def add_action(self, name: str, action: ClientAction):
        if name in self.known_actions:
            return False

        self.known_actions[name] = action
        return True

    async def shutdown_server(self):
        logger.info("Server shutdown triggered")
        self.server.close()
        await self.server.wait_closed()
        logger.info("Server closed")

    async def start_server(self, host="127.0.0.1", port=8766):
        self.server = await websockets.serve(self.__on_client_connected, host, port)

    async def __on_client_connected(self, websocket, path):
        # TODO(mark) is every listen()-invocation, run in its own task?
        self.clients.add(websocket)
        logger.info("Client added: %s", websocket)

        try:
            await self.__client_loop_may_throw(websocket)
        except WebSocketException as e:
            logger.info("WebSocket connection error: %s", e)

        finally:
            self.clients.remove(websocket)
            logger.info("Client removed: %s", websocket)

    async def welcome_client(self, websocket):
        pass

    async def __client_loop_may_throw(self, websocket: websockets.WebSocketServerProtocol):
        # Send initial information
        await self.welcome_client(websocket)

        while True:
            data = await websocket.recv()  # raises on close/error

            result = await self.__handle_input_from_client(data)
            await websocket.send(str(result))

    async def broadcast(self, line: str):
        # TODO(mark): this blocks the process processing application!
        clients = self.clients.copy()
        for client in clients:
            try:
                await client.send(line)
            except WebSocketException as e:
                logger.info("WS write failed: %s", e)
                # TODO(mark): assumption: __on_client_connected will remove the failed websocket

    async def __handle_input_from_client(self, line: str) -> ActionResponse:
        try:
            json_data = json.loads(line)
        except:
            return ActionFailure(None, "invalid", "Received invalid input: %s" % line)

        action_name = json_data.get("action", None)
        payload = json_data.get("data", None)
        print(action_name, payload)
        if action_name not in self.known_actions or payload is None:
            return ActionFailure(None, action_name, "Invalid action '%s' or missing data" % action_name)

        action = self.known_actions[action_name]
        return await action.call_with_data(payload)
