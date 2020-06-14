import json
import logging
import sys

from wsmonitor.scripts.util import run
from wsmonitor.ws_process_monitor import WebsocketProcessMonitor

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def main(host, port, config_file=None):
    wpm = WebsocketProcessMonitor()
    if config_file is not None:
        data = config_file.read()
        config_file.close()

        processes = json.loads(data)
        for process in processes:
            wpm.register_process(process["uid"], process["cmd"], process["process_group"])

    run(wpm.run(host, port), wpm.shutdown())


if __name__ == '__main__':
    main("localhost", 8766)
