"""Optional desktop entry point. The original aicommit CLI is not modified."""

from aicommit.gui_v03 import main

if __name__ == "__main__":
    raise SystemExit(main())
