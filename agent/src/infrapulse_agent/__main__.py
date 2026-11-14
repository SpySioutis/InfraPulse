"""InfraPulse agent entrypoint: `python -m infrapulse_agent`."""

from __future__ import annotations

import argparse
import logging
import sys

from infrapulse_agent.client import run_forever
from infrapulse_agent.config import AgentConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="InfraPulse monitoring agent")
    parser.add_argument("--config", default=None, help="path to agent.json (default: $AGENT_CONFIG or /etc/infrapulse/agent.json)")
    parser.add_argument("--once", action="store_true", help="collect and print one report as JSON, then exit")
    args = parser.parse_args(argv)

    config = AgentConfig.load(args.config)
    if args.once:
        from infrapulse_agent.collect import Collector
        import json

        print(json.dumps(Collector().collect(), indent=2))
        return 0
    try:
        run_forever(config, args.config)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
