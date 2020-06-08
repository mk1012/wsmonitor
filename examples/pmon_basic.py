import asyncio
import logging
import signal
import sys

from ws_pmom.process_monitor import ProcessMonitor

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(lineno)d -  %(message)s")
if __name__ == '__main__':
    reg = ProcessMonitor()
    loop = asyncio.get_event_loop()


    async def populate():
        reg.register_process("py", "python3 signal_inhibit.py")
        reg.register_process("ping", "ping -c 10 google.de")

        reg.start_process("py")
        reg.start_process("ping")

        await reg.start_monitor()


    def shutdown_handler():
        loop.create_task(reg.shutdown_monitor())


    loop.set_debug(True)
    loop.add_signal_handler(signal.SIGINT, shutdown_handler)
    loop.add_signal_handler(signal.SIGTERM, shutdown_handler)

    try:
        loop.run_until_complete(populate())
    finally:
        loop.stop()
        loop.close()
