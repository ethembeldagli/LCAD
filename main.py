#!/usr/bin/env python3
import sys
from gui import LutrisCoverDownloaderApp


def main():
    app = LutrisCoverDownloaderApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
