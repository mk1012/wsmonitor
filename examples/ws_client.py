import asyncio
import json
import logging
from asyncio import CancelledError
from typing import Optional

import websockets

from wsmonitor import util
from wsmonitor.process.data import ActionResponse, OutputEvent
from wsmonitor.util import from_json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class AwaitedResponse:

    def __init__(self, action):
        self.action = action
        self._future = asyncio.Future()

    def set_if_match(self, action, result):
        if self.action == action:
            self._future.set_result(result)
            return True
        return False

    def __await__(self):
        yield from self._future.__await__()
        return self._future.result()


class WSMonitorClient:

    def __init__(self):
        self.is_running = False
        self.is_connected = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

        self._awaited_response: Optional[AwaitedResponse] = None
        self._read_task: Optional[asyncio.Task] = None

    async def connect(self, host="127.0.0.1", port=8766):
        uri = f"ws://{host}:{port}"
        try:
            self.websocket = await websockets.connect(uri)
        except Exception as excpt:
            logger.warning("Failed to connect to server: %s", excpt)
            self.is_connected = False
            return False

        self.start_read_task()
        self.is_connected = True
        logger.info("Client connected")
        return True

    async def action(self, action_name: str, **kwargs):
        if not self.is_connected:
            logger.warning("Client is not connected, cannot send data!")
            return

        # TODO: block further actions if still waiting for result?

        data = json.dumps({"action": action_name, "data": kwargs})

        # we want to receive a response to our action
        self._awaited_response = AwaitedResponse(action_name)
        await self.websocket.send(data)

        logger.info("Waiting for Action '%s' to be fullfilled", action_name)
        response = await self._awaited_response
        logger.info("Action '%s' is fullfilled", action_name)

        return response

    async def _on_action_response(self, response: ActionResponse):
        logger.info("Response: %s", response)
        # assert response.action == action_name, f"{event.action} != {action_name}"
        if not self._awaited_response.set_if_match(response.action, response.data):
            logger.warning("Received response '%s' while expecting '%s'",
                           response.action, self._awaited_response.action)

    def start_read_task(self):
        if self._read_task is not None:
            return

        self._read_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        logger.debug("Read task started")
        while True:
            try:
                data = await self.websocket.recv()
            except websockets.WebSocketException:
                logger.info("Receiving message failed")
                break

            event = from_json(data)
            if isinstance(event, ActionResponse):
                await self._on_action_response(event)

            elif isinstance(event, OutputEvent):
                await self._on_output(event)

    async def close(self):
        if not self.is_connected:
            logger.debug("Client is not connected, cannot close connection!")
            return

        logger.info("Shutting client down...")
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except CancelledError:
                pass
            except Exception as e:
                logger.info("Read task raised an exception", exc_info=e)

        if self.is_connected:
            await self.websocket.close()
            await self.websocket.wait_closed()

    async def _on_output(self, event: OutputEvent):
        pass

    def get_read_task(self):
        return self._read_task


def run_single_action_client(host: str, port: int, action_name: str, **kwargs):
    client = WSMonitorClient()

    async def main():
        while not await client.connect(host, port):
            logger.info("Waiting 1sec to re-connect")
            await asyncio.sleep(1)

        result = None
        if action_name == "output":
            async def on_output(event: OutputEvent):
                print(event.output, end="")

            client._on_output = on_output
            try:
                await client.get_read_task()
            except asyncio.CancelledError:
                pass
        else:
            result = await client.action(action_name, **kwargs)

        await client.close()
        asyncio.get_event_loop().stop()

        return result

    async def shutdown():
        await client.close()

    return util.run(main(), shutdown)
