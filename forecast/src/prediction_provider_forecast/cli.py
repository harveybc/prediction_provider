"""Small offline commands; no web service or training runtime is booted."""

import argparse
import json
from pathlib import Path
import sys

from .provider import ForecastProvider


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-dev", help="export retained R0_s1 weights, never train")
    export.add_argument("--predictor-root", type=Path, required=True)
    export.add_argument("--run-root", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    example = commands.add_parser("export-predictor-example",
                                  help="export one committed predictor example checkpoint, never train")
    example.add_argument("--predictor-root", type=Path, required=True)
    example.add_argument("--inference-config", type=Path, required=True,
                         help="a predictor inference config carrying load_model and x_train_file")
    example.add_argument("--out", type=Path, required=True)
    caps = commands.add_parser("capabilities")
    caps.add_argument("--bundle", type=Path)
    load = commands.add_parser("load")
    load.add_argument("--bundle", type=Path, required=True)
    load.add_argument("--state", required=True)
    infer = commands.add_parser("infer")
    infer.add_argument("--bundle", type=Path, required=True)
    infer.add_argument("--request", type=Path, required=True)
    chat = commands.add_parser("chat-request")
    chat.add_argument("--bundle", type=Path, required=True)
    chat.add_argument("--prompt", required=True)
    chat.add_argument("--data", type=Path, required=True)
    chat.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "export-dev":
            from .export import export_dev
            result = export_dev(args.predictor_root, args.run_root, args.out)
        elif args.command == "export-predictor-example":
            from .export import export_predictor_example
            result = export_predictor_example(args.predictor_root, args.inference_config, args.out)
        else:
            provider = ForecastProvider(args.bundle)
            if args.command == "capabilities":
                result = provider.capabilities()
            elif args.command == "load":
                result = provider.load(args.state)
            elif args.command == "chat-request":
                result = provider.chat_request(args.prompt, json.loads(args.data.read_text()),
                                               json.loads(args.config.read_text()))
            else:
                request = json.loads(sys.stdin.read() if str(args.request) == "-" else args.request.read_text())
                provider._check_request(request)
                result = provider.infer(request, provider.load(request["fitted_state_ref"]))
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, RuntimeError, ImportError, AssertionError) as exc:
        print(json.dumps({"status": "REFUSED", "error_type": type(exc).__name__, "why": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
