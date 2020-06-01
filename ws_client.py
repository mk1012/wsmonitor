import asyncio
import json

import websockets


async def hello():
    uri = "ws://localhost:8766"
    async with websockets.connect(uri) as websocket:
        data = json.dumps({"cmd": "source ~/Arbeit_IPR/ws/devel/setup.bash && roslaunch rll_move move_iface.launch", "action": "register", "name": "Mark2"})
        await websocket.send(data)
        data = json.dumps({"uid": "test", "action": "start"})
        await websocket.send(data)
        data = json.dumps({"uid": "test", "action": "stop"})
        await websocket.send(data)
        data = json.dumps({"uid": "test", "action": "start"})
        await websocket.send(data)
        while True:
            data = await websocket.recv()
            print(data)


asyncio.get_event_loop().run_until_complete(hello())
