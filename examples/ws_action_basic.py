import asyncio
import logging
import signal

logging.basicConfig(level=logging.DEBUG)
from ws_pmom.ws_monitor import WebsocketActionServer, ClientAction


async def hello():
    print("Hello world")
    return "Hello World"


def main():
    loop = asyncio.get_event_loop()
    wpm = WebsocketActionServer()
    wpm.add_action("test", ClientAction("test", [], hello))
    loop.set_debug(True)

    def shutdown_handler():
        wpm.shutdown_server()

    loop.add_signal_handler(signal.SIGINT, shutdown_handler)
    loop.add_signal_handler(signal.SIGTERM, shutdown_handler)

    async def main_loop():

        task = asyncio.create_task(wpm.start_server())
        await task
        loop.stop()

    try:
        loop.create_task(main_loop())
        loop.run_forever()

    finally:
        loop.stop()
        loop.close()


if __name__ == '__main__':
    main()
