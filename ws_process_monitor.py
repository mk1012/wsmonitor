import json
import logging
import signal
from typing import Union, Dict

from websockets import WebSocketException

from process_monitor import ProcessMonitor

import asyncio
import websockets

from ws_monitor import WebsocketControl, ClientAction

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class WebsocketProcessMonitor(ProcessMonitor, WebsocketControl):

    def __init__(self):
        ProcessMonitor.__init__(self)
        WebsocketControl.__init__(self)

        self.periodic_update_sleep_duration = 10
        self.known_actions.update({
            # "register": ClientAction("register",  ["uid", "cmd"],  self.register),
            "start": ClientAction("start", ["uid"], self.__start_action),
            "stop": ClientAction("stop", ["uid"], self.__stop_action),
        })

    async def __start_action(self, uid):
        result = self.start(uid)
        print("Result", result)
        if isinstance(result, str):
            return self.format_response(False, "start", {"uid": uid, "data": result})

        return self.format_response(True, "start", {"uid": uid})

    async def __stop_action(self, uid):
        result = await self.stop(uid)
        if isinstance(result, str):
            return self.format_response(False, "stop", {"uid": uid, "data": result})

        return self.format_response(True, "stop", {"uid": uid, "data": result})

    async def _periodic_update_func(self):
        self._is_running = True
        while self._is_running:
            await asyncio.sleep(self.periodic_update_sleep_duration)
            print("Periodic update")
            state_data = self.state_response(self.as_json_data())  # json.dumps
            await self.broadcast(state_data)

    def _get_monitor_tasks(self):
        tasks = ProcessMonitor._get_monitor_tasks(self)
        periodic_state_update_task = asyncio.create_task(self._periodic_update_func())
        tasks.append(periodic_state_update_task)
        return tasks

    async def on_state_event(self, event):
        logger.info("Received state event: %s", event)
        await self.broadcast(json.dumps(event.get_data()))

    async def on_output_event(self, event):
        await self.broadcast(json.dumps(event.get_data()))

    def get_server_loop_task(self):
        return self.start_monitor_tasks()


def main():
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    wpm = WebsocketProcessMonitor()

    loop.create_task(wpm.register("test", "ping 8.8.8.8", False))

    def shutdown_handler(_1, _2):
        loop.create_task(wpm.shutdown())

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        loop.run_until_complete(wpm.listen())
    finally:
        loop.stop()
        loop.close()


if __name__ == '__main__':
    main()
