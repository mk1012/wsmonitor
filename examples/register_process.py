import asyncio
import json

import websockets

import click


@click.command()
@click.option('--uid', prompt='Unique ID', help='Internal unique process identifier.')
@click.option('--command', prompt="Full command", help='Full comman to execute')
@click.option('--host', default="localhost", help='Server host address')
@click.option('--port', default=8766, help='Server port')
def main(uid: str, command: str, host: str, port: int):
    data = {
        "action": "register",
        "data": {
            "uid": uid,
            "cmd": command,
            "group": False
        }
    }

    async def send():
        uri = f"ws://{host}:{port}"
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps(data))
            response = await websocket.recv()
            print(response)

            data["action"] = "start"
            await websocket.send(json.dumps(data))
            for i in range(10):
                response = await websocket.recv()
                print(response)

    asyncio.get_event_loop().run_until_complete(send())


if __name__ == "__main__":
    main()
