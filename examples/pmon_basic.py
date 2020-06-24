import asyncio
import logging
import sys

from wsmonitor.process.process_monitor import ProcessMonitor
from wsmonitor import util

if __name__ == '__main__':
    reg = ProcessMonitor()
    loop = asyncio.get_event_loop()


    async def populate():
        reg.add_process("py", "python3 signal_inhibit.py")
        reg.add_process("ping", "ping -c 10 google.de")

        await reg.start_process("py")
        await reg.start_process("ping")

        reg.start_monitor()


    async def shutdown():
        await reg.shutdown()
        loop.stop()


    util.run(populate(), shutdown)
