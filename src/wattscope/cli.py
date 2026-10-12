"""Small reproducible command interface; run with python -m wattscope.cli."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="WattScope day-ahead load forecasting")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository/artifact root")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Download and prepare the original UCI data")
    prepare.add_argument("--archive", type=Path, help="Use an already downloaded original UCI ZIP")
    commands.add_parser("train", help="Run chronological model selection, calibration and testing")
    forecast = commands.add_parser("forecast", help="Print a forecast as JSON")
    forecast.add_argument("--client", default="MT_001")
    forecast.add_argument("--origin", default=None)
    serve = commands.add_parser("serve", help="Start the local API and dashboard")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "prepare":
        from wattscope.data import prepare_data

        prepare_data(args.root, args.archive)
    elif args.command == "train":
        from wattscope.train import train

        train(args.root)
    elif args.command == "forecast":
        from wattscope.service import ForecastService

        print(json.dumps(ForecastService(args.root).forecast(args.client, args.origin), indent=2))
    else:
        import os

        import uvicorn

        os.environ["WATTSCOPE_ROOT"] = str(args.root.resolve())
        uvicorn.run("wattscope.api:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
