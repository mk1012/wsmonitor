import asyncio
import json
import logging
import signal
from json import JSONDecodeError
from typing import Coroutine, List, Type, Callable, Optional

from wsmonitor.format import JsonFormattable
from wsmonitor.process.data import ProcessSummaryEvent, StateChangedEvent, \
    OutputEvent, ActionResponse

logger = logging.getLogger(__name__)


def run(run: Coroutine, shutdown: Optional[Callable[[], Coroutine]] = None):
    # Similar to asyncio.run but we need to register signal_handlers as well
    # and make sure to call our custom shutdown methods

    loop = asyncio.get_event_loop()
    # loop.set_debug(True)
    main_task = asyncio.ensure_future(run)

    async def initiate_shutdown():
        logger.info("Shutdown signal received, shutting down...")
        if shutdown is not None:
            try:
                await shutdown()
            except Exception as excpt:
                logger.error("Shutdown raised: %s", excpt)

        logger.debug("Cancelling main task")
        main_task.cancel()
        try:
            await main_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning("Main task raised", exc_info=e)

        loop.stop()

    def signal_handler():
        loop.create_task(initiate_shutdown())

    loop.add_signal_handler(signal.SIGINT, signal_handler)
    loop.add_signal_handler(signal.SIGTERM, signal_handler)

    try:
        logger.info("Starting loop")
        loop.run_forever()
    finally:
        # TODO: check for unfinished tasks
        loop.stop()
        loop.close()

    return main_task.result()


MESSAGE_TYPES: List[Type[JsonFormattable]] = [ProcessSummaryEvent,
                                              StateChangedEvent, OutputEvent,
                                              ActionResponse]


def from_json(json_str: str):
    try:
        json_data = json.loads(json_str)
        msg_type = json_data["type"]
        payload = json_data["data"]

        for m_type in MESSAGE_TYPES:
            if m_type.__name__ == msg_type:
                return m_type.from_json(payload)

    except JSONDecodeError as excpt:
        logger.warning("Invalid json %s", excpt)

    except KeyError as excpt:
        logger.warning("Missing keys in json %s", excpt)

    return None
