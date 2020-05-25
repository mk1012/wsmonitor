import signal
import time, sys


def signal_handler(sig, frame):
    print('You pressed:', sig)
    if sig == 15:
        time.sleep(.2)
        sys.exit(42)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

while True:
    print("Busy waiting...")
    time.sleep(1)
