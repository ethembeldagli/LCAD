#!/usr/bin/env python3
import sys
from gui import LCAD


def main():
    app = LCAD()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
