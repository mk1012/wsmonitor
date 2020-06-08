import signal
import time, sys


def signal_handler(sig, frame):
    print('Signal received:', sig)
    if sig == signal.SIGTERM:
        time.sleep(.2)
        sys.exit(42)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

for i in range(10):
    print("Busy waiting...")
    time.sleep(1)
