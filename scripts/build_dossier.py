#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a request-time drug dossier.")
    parser.add_argument("drug", help="Drug name to resolve, for example: aspirin")
    parser.add_argument("--depth", type=int, default=1, help="RxNorm graph depth")
    parser.add_argument(
        "--max-edges",
        type=int,
        default=75,
        help="Maximum RxNorm edges",
    )
    parser.add_argument(
        "--openfda-limit",
        type=int,
        default=5,
        help="OpenFDA labels to fetch",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use cache only; skip live OpenFDA",
    )
    parser.add_argument(
        "--no-openfda",
        action="store_true",
        help="Build RxNorm-only dossier",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    parser.add_argument(
        "--rxnconso",
        default="data/01_raw/rxnconso_raw.parquet",
        help="Path to RXNCONSO parquet",
    )
    parser.add_argument(
        "--rxnrel",
        default="data/01_raw/rxnrel_raw.parquet",
        help="Path to RXNREL parquet",
    )
    return parser.parse_args()


def main() -> None:
    from src.dossier.builder import DossierBuilder
    from src.dossier.openfda_store import OpenFDALabelStore
    from src.dossier.rxnorm_store import RxNormParquetStore

    args = parse_args()
    builder = DossierBuilder(
        rxnorm_store=RxNormParquetStore(args.rxnconso, args.rxnrel),
        openfda_store=OpenFDALabelStore(allow_live=not args.offline),
    )
    dossier = builder.build(
        args.drug,
        depth=args.depth,
        max_edges=args.max_edges,
        include_openfda=not args.no_openfda,
        openfda_limit=args.openfda_limit,
    )
    payload = dossier.to_jsonable()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w") as f:
            json.dump(payload, f, indent=2)
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
