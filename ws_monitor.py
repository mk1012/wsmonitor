import json
import logging
import signal

from websockets import WebSocketException

from process_monitor import ProcessMonitor

import asyncio
import websockets

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class WebsocketProcessMonitor(ProcessMonitor):

    def __init__(self):
        super().__init__()
        self.known_actions = {
            "register": {"keys": ["name", "cmd"], "fn": self.register},
            "start": {"keys": ["name"], "fn": self.start},
            "stop": {"keys": ["name"], "fn": self.stop}

        }
        self.clients = set()
        self._shutdown_future = asyncio.get_event_loop().create_future()

    async def __client_connected(self, websocket, path):
        self.clients.add(websocket)
        logger.info("Client added: %s", websocket)

        try:
            await self.handle_client(websocket)
        finally:
            self.clients.remove(websocket)
            logger.info("Client removed: %s", websocket)

    async def listen(self, host="127.0.0.1", port=8766):
        self.start_monitor_tasks()

        # run as long as the state monitor is running
        async with websockets.serve(self.__client_connected, host, port):
            try:
                await self._monitor_tasks
            except asyncio.CancelledError:
                logger.info("State monitor task cancelled, stopping websocket server")

        logger.info("Websocket server stopped")

    async def handle_client(self, websocket: websockets.WebSocketServerProtocol):
        while self._is_running:
            try:
                data = await websocket.recv()
            except WebSocketException as e:
                logger.info("WS read failed: %s", e)
                break

            await self._process_client_input(data)
            # await asyncio.sleep(.1)

    async def _on_output(self, line):
        await self._write_all_clients(line)

    async def _write_all_clients(self, line):
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

    async def on_state_event(self, event):
        print("ev", event)
        #await ProcessMonitor._handle_on_state_changed(self, process, state)
        await self._write_all_clients(json.dumps(event.get_data()))

    async def _process_client_input(self, data):
        try:
            jdata = json.loads(data)
        except:
            logger.warning("Received invalid input: %s", data)
            return

        action_name = jdata.get("action", None)
        if action_name not in self.known_actions:
            logger.warning("Invalid action: %s", action_name)
            return

        action = self.known_actions[action_name]
        has_keys = all(map(lambda key: key in jdata, action["keys"]))
        if not has_keys:
            logger.warning("Not all required keys are set: %s", action["keys"])

        return await action["fn"](*(jdata[key] for key in action["keys"]))


def main():
    loop = asyncio.get_event_loop()
    wpm = WebsocketProcessMonitor()
    loop.set_debug(True)

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
