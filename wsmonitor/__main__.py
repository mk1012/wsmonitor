import logging

from wsmonitor.cli import cli
from wsmonitor.gui.main_window import main

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
logging.getLogger().addHandler(logging.StreamHandler())

if __name__ == "__main__":
    cli()
