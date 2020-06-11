import asyncio
import json
import logging
import signal
import sys

from wsmonitor.ws_process_monitor import WebsocketProcessMonitor

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    wpm = WebsocketProcessMonitor()

    with open("processes.json") as file:
        processes = json.load(file)
    for process in processes:
        wpm.register_process(process["uid"], process["cmd"], process["process_group"])

    async def do_shutdown():
        await wpm.shutdown()
        loop.stop()

    def shutdown_handler():
        loop.create_task(do_shutdown())

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
