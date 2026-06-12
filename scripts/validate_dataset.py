#!/usr/bin/env python3
"""Validate generated static market data files."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gzip_json(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as gz_file:
        return json.load(gz_file)


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def parse_iso(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{label}: expected ISO timestamp string")
        return
    normalized = value.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        errors.append(f"{label}: invalid ISO timestamp: {value}")


def validate_bundle(path: Path, min_success: int, errors: list[str]) -> None:
    require(path.exists(), f"missing bundle: {path}", errors)
    require(path.with_suffix(path.suffix + ".gz").exists(), f"missing gzip bundle: {path}.gz", errors)
    if not path.exists():
        return

    bundle = load_json(path)
    gzip_bundle = load_gzip_json(path.with_suffix(path.suffix + ".gz"))
    require(bundle == gzip_bundle, f"gzip mismatch: {path}", errors)

    require(bundle.get("schemaVersion") == "open-market-candles.bundle.v1", f"{path}: bad schemaVersion", errors)
    parse_iso(bundle.get("generatedAt"), f"{path}: generatedAt", errors)
    symbols = bundle.get("symbols")
    require(isinstance(symbols, list), f"{path}: symbols must be a list", errors)
    if not isinstance(symbols, list):
        return

    require(len(symbols) >= min_success, f"{path}: expected at least {min_success} successful symbols", errors)
    seen: set[str] = set()
    for symbol in symbols:
        symbol_id = symbol.get("symbol")
        require(isinstance(symbol_id, str) and bool(symbol_id), f"{path}: symbol missing id", errors)
        if isinstance(symbol_id, str):
            require(symbol_id not in seen, f"{path}: duplicate symbol {symbol_id}", errors)
            seen.add(symbol_id)
        candles = symbol.get("candles")
        require(isinstance(candles, list) and bool(candles), f"{path}: {symbol_id} has no candles", errors)
        if not isinstance(candles, list):
            continue
        for index, candle in enumerate(candles):
            label = f"{path}: {symbol_id} candle {index}"
            parse_iso(candle.get("time"), f"{label} time", errors)
            for key in ["open", "high", "low", "close"]:
                require(isinstance(candle.get(key), (int, float)), f"{label}: {key} must be numeric", errors)
            require(isinstance(candle.get("volume"), int), f"{label}: volume must be int", errors)


def validate(root: Path, min_success_per_market: int) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "manifest.json"
    require(manifest_path.exists(), f"missing manifest: {manifest_path}", errors)
    if not manifest_path.exists():
        return errors

    manifest = load_json(manifest_path)
    require(manifest.get("schemaVersion") == "open-market-candles.manifest.v1", "manifest: bad schemaVersion", errors)
    parse_iso(manifest.get("generatedAt"), "manifest generatedAt", errors)

    markets = manifest.get("markets")
    require(isinstance(markets, dict) and bool(markets), "manifest: markets must be a non-empty object", errors)
    if isinstance(markets, dict):
        for market, info in markets.items():
            bundle = info.get("bundle")
            symbols = info.get("symbols")
            require(isinstance(bundle, str), f"manifest: {market} bundle missing", errors)
            require(isinstance(symbols, str), f"manifest: {market} symbols missing", errors)
            if isinstance(symbols, str):
                require((root / symbols).exists(), f"missing symbols file: {symbols}", errors)
                require((root / f"{symbols}.gz").exists(), f"missing symbols gzip: {symbols}.gz", errors)
            if isinstance(bundle, str):
                validate_bundle(root / bundle, min_success_per_market, errors)

    all_bundle = (((manifest.get("bundles") or {}).get("all") or {}).get("bundle"))
    require(isinstance(all_bundle, str), "manifest: all bundle missing", errors)
    if isinstance(all_bundle, str):
        validate_bundle(root / all_bundle, max(1, min_success_per_market), errors)

    require((root / "index.html").exists(), "missing index.html", errors)
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--min-success-per-market", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate(args.root, args.min_success_per_market)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print(f"valid dataset: {args.root}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
