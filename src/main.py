#!/usr/bin/env python3
"""
gitsh - A simplified Git implementation
Entry point for the CLI
"""

from cli import main
import sys
from importlib import reload
reload(sys)
if __name__ == "__main__":
    main()

