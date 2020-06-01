import json
import logging
import signal
from typing import Union, Dict, Set, List

from websockets import WebSocketException

import asyncio
import websockets

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class ClientConnection():

    def __init__(self, websocket):
        self.websocket = websocket
        self.is_active = True

    def loop(self):
        pass


class ClientAction(object):

    def __init__(self, name, keys: List[str], func):
        self.name = name
        self.keys = keys
        self.func = func

    def keys_match(self, keys: Set[str]):
        return all(map(lambda key: key in keys, self.keys))


class WebsocketControl:

    def __init__(self):
        super().__init__()
        self.periodic_update_sleep_duration = 10
        self.known_actions = {}  # type: Dict[str, ClientAction]

        self.clients = set()
        self._shutdown_future = asyncio.get_event_loop().create_future()

    async def listen(self, host="127.0.0.1", port=8766):
        listen_while_future = self.get_server_loop_task()

        # run as long as future is not finished. If the with statement is done
        # all connections will be automatically closed
        async with websockets.serve(self.__client_connected, host, port):
            try:
                await listen_while_future
            except asyncio.CancelledError:
                logger.info("State monitor task cancelled, stopping websocket server")

        logger.info("Websocket server stopped")

    async def __client_connected(self, websocket, path):
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

            result = await self._process_client_input(data)
            if result is not None:
                logger.info("res: %s", result)
                await websocket.send(result)

    async def broadcast(self, line):
        # TODO: this blocks the process processing application!
        # we should probaly put state change events in a queue and consume
        # the events!
        clients = self.clients.copy()
        for client in clients:
            try:
                await client.send(line)
            except WebSocketException as e:
                logger.info("WS write failed: %s", e)
                # TODO(mark): I assume that handle_client will remove the failed websocket

    async def _process_client_input(self, data):
        try:
            jdata = json.loads(data)
        except:
            return self.error_response("invalid", "Received invalid input: %s" % data)

        action_name = jdata.get("action", None)
        if action_name not in self.known_actions:
            return self.error_response(action_name, "Invalid action: %s" % action_name)

        action = self.known_actions[action_name]

        if not action.keys_match(jdata.keys()):
            return self.error_response(action_name, "Not all required keys are set: %s" % action.keys)

        return await action.func(*(jdata[key] for key in action.keys))

    def format_response(self, success: bool, action: str, data: Union[Dict, str]):
        logger.warning(data)
        return json.dumps({"type": "response", "data": {"action": action, "success": success, "data": data}})

    def error_response(self, action: str, msg: str):
        return self.format_response(False, action, msg)

    def state_response(self, data: str):
        logger.warning(data)
        return json.dumps({"type": "event", "data": {"type": "state", "data": data}})

    def get_server_loop_task(self):
        raise NotImplementedError()


def main():
    loop = asyncio.get_event_loop()
    wpm = WebsocketProcessMonitor()
    loop.set_debug(True)

    loop.create_task(wpm.register("test", "ping 8.8.8.8", False))

    def shutdown_handler(_1, _2):
        loop.create_task(wpm.shutdown())

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        loop.run_until_complete(wpm.listen())

    finally:
        loop.stop()
        loop.close()


if __name__ == '__main__':
    main()
