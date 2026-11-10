"""WhereUPark command line.

    python -m whereupark sites            # show configured sites and spot counts
    python -m whereupark train            # initial training / manual retrain
    python -m whereupark ingest FILE.csv  # import real usage figures
    python -m whereupark serve [--port N] # run the API
    python -m whereupark schedule         # run the periodic retraining scheduler
"""
from __future__ import annotations

import argparse
import json
import logging


def main() -> None:
    p = argparse.ArgumentParser(prog="whereupark")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sites")
    sub.add_parser("train")
    ing = sub.add_parser("ingest")
    ing.add_argument("csv")
    ing.add_argument("--retrain", action="store_true", help="retrain after importing")
    srv = sub.add_parser("serve")
    srv.add_argument("--host", default="0.0.0.0")
    srv.add_argument("--port", type=int, default=8000)
    sub.add_parser("schedule")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.cmd == "sites":
        from .config import get_config
        for s in get_config().sites:
            tag = "PLACEHOLDER" if s.counts_are_placeholder else "audited"
            print(f"{s.name:<18} {s.capacity:>5}  {s.counts}  [{tag}]")
    elif args.cmd == "train":
        from .training import retrain
        print(json.dumps(retrain(), indent=2))
    elif args.cmd == "ingest":
        from .ingest import import_csv
        print(f"Imported {import_csv(args.csv)} observations")
        if args.retrain:
            from .training import retrain
            print(json.dumps(retrain(), indent=2))
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("whereupark.api:app", host=args.host, port=args.port)
    elif args.cmd == "schedule":
        from .scheduler import run
        run()


if __name__ == "__main__":
    main()
