#!/usr/bin/env python2
"""the __main__ script can be invoked by python."""
import sys

from . import runner


if __name__ == "__main__":
    runner.run(sys.argv[1:])
