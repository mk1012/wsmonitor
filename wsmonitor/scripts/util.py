import asyncio
import signal
from typing import Coroutine


def run(run: Coroutine, shutdown: Coroutine):
    # Similar to asyncio.run but we need to register signal_handlers as well
    # and make sure to call our custom shutdown methods

    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    async def initiate_shutdown():
        await shutdown
        loop.stop()

    def signal_handler():
        loop.create_task(initiate_shutdown())

    loop.add_signal_handler(signal.SIGINT, signal_handler)
    loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        loop.create_task(run)
        loop.run_forever()
    finally:
        # TODO: check for unfinished tasks
        loop.stop()
        loop.close()
