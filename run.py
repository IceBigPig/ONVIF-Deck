import sys
from pathlib import Path


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from onvif_scanner.app import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
