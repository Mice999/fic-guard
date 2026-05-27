import sys

# When double-clicked as a frozen exe with no arguments, default to `web`.
if getattr(sys, "frozen", False) and len(sys.argv) == 1:
    sys.argv.append("web")

from fic_guard.cli import main

if __name__ == "__main__":
    main()
