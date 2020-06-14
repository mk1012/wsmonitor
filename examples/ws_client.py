import asyncio
import json
from typing import Optional

import websockets

from wsmonitor.scripts import util


class WSMonitorClient:

    def __init__(self):
        self.is_running = False
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None

    async def connect(self, host="127.0.0.1", port=8766):
        uri = f"ws://{host}:{port}"
        self.websocket = await websockets.connect(uri)

    async def action(self, action_name: str, uid: str):
        data = json.dumps({"action": action_name, "data": {"uid": uid}})
        await self.websocket.send(data)

        # while True:
        #    data = await self.websocket.recv()
        #    print(data)

    async def close(self):
        await self.websocket.close()
        await self.websocket.wait_closed()


if __name__ == "__main__":
    client = WSMonitorClient()


    async def main():
        await client.connect()
        await client.action("start", "ping")


    async def shutdown():
        await client.close()


    util.run(main(), shutdown())
