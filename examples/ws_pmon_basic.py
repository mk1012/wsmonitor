import asyncio
import logging
import signal
import sys

from ws_pmom.ws_process_monitor import WebsocketProcessMonitor

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    wpm = WebsocketProcessMonitor()

    wpm.register_process("test", "ping -c 20 8.8.8.8", True)

    async def do_shutdown():
        await wpm.shutdown()
        loop.stop()

    def shutdown_handler():
        task = loop.create_task(do_shutdown())

    loop.add_signal_handler(signal.SIGINT, shutdown_handler)
    loop.add_signal_handler(signal.SIGTERM, shutdown_handler)

    try:
        loop.create_task(wpm.run())
        loop.run_forever()
    finally:
        loop.stop()
        loop.close()


if __name__ == '__main__':
    main()
