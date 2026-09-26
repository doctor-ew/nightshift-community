#!/usr/bin/env python3
"""Keep recovery execution bounded even if its controller or browser server exits."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def run(parent, seconds, output, argv):
    deadline=time.monotonic()+seconds
    child=None
    stopping=False
    def stop(_signum, _frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        if stopping or os.getppid()!=parent or time.monotonic()>=deadline:return 124
        child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,start_new_session=True)
        while child.poll() is None:
            if stopping or os.getppid()!=parent or time.monotonic()>=deadline or Path(output).stat().st_size>2_000_000:
                return 124
            time.sleep(.05)
        return child.returncode
    finally:
        if child is not None:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=2)
            except subprocess.TimeoutExpired:pass
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()


if __name__=='__main__':
    raise SystemExit(run(int(sys.argv[1]),float(sys.argv[2]),sys.argv[3],sys.argv[4:]))
