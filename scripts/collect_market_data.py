#!/usr/bin/env python3
"""Collect market candles and publish static JSON bundles."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0"


@dataclass(frozen=True)
class FetchResult:
    symbol: dict[str, Any]
    meta: dict[str, Any]
    candles: list[dict[str, Any]]


class ProviderError(RuntimeError):
    pass


class YahooChartProvider:
    def __init__(
        self,
        provider_config: dict[str, Any],
        interval: str,
        data_range: str,
        timeout: int,
        retries: int,
        retry_sleep: float,
    ) -> None:
        self.config = provider_config
        self.interval = interval
        self.data_range = data_range
        self.timeout = timeout
        self.retries = retries
        self.retry_sleep = retry_sleep
        configured_urls = provider_config.get("baseUrls") or [provider_config["baseUrl"]]
        self.base_urls = [str(url).rstrip("/") for url in configured_urls]

    def fetch(self, symbol_config: dict[str, Any]) -> FetchResult:
        symbol = symbol_config["symbol"]
        query = urlencode(
            {
                "range": self.data_range,
                "interval": self.interval,
                "includePrePost": "false",
                "events": "div,splits",
            }
        )
        payload = None
        last_error: Exception | None = None
        for base_url in self.base_urls:
            url = f"{base_url}/{quote(symbol, safe='')}?{query}"
            try:
                payload = self._request_json(url)
                break
            except ProviderError as exc:
                last_error = exc
        if payload is None:
            raise ProviderError(f"{symbol}: all provider hosts failed: {last_error}")

        chart = payload.get("chart", {})
        if chart.get("error"):
            raise ProviderError(f"{symbol}: {chart['error']}")

        results = chart.get("result") or []
        if not results:
            raise ProviderError(f"{symbol}: empty chart result")

        result = results[0]
        meta = result.get("meta") or {}
        timestamps = result.get("timestamp") or []
        indicators = result.get("indicators") or {}
        quotes = indicators.get("quote") or []
        if not timestamps or not quotes:
            raise ProviderError(f"{symbol}: missing timestamps or quotes")

        quote_data = quotes[0]
        candles = normalize_candles(timestamps, quote_data)
        if not candles:
            raise ProviderError(f"{symbol}: no complete candles")

        merged_symbol = {
            **symbol_config,
            "currency": meta.get("currency") or symbol_config.get("currency"),
            "exchangeName": meta.get("exchangeName"),
            "fullExchangeName": meta.get("fullExchangeName"),
            "timezone": meta.get("exchangeTimezoneName") or meta.get("timezone"),
            "regularMarketPrice": finite_or_none(meta.get("regularMarketPrice")),
            "regularMarketTime": timestamp_to_iso(meta.get("regularMarketTime")),
            "previousClose": finite_or_none(meta.get("previousClose")),
            "sourceSymbol": meta.get("symbol") or symbol,
        }

        return FetchResult(symbol=merged_symbol, meta=meta, candles=candles)

    def _request_json(self, url: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            request = Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/json,text/plain,*/*",
                },
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                return json.loads(raw.decode("utf-8"))
            except HTTPError as exc:
                last_error = exc
                if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                    break
                retry_after = exc.headers.get("Retry-After")
                sleep_seconds = parse_retry_after(retry_after) or self.retry_sleep * (2**attempt)
                time.sleep(min(sleep_seconds, 60))
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(min(self.retry_sleep * (2**attempt), 60))

        raise ProviderError(f"request failed after retries: {last_error}")


def normalize_candles(
    timestamps: list[int],
    quote_data: dict[str, list[Any]],
) -> list[dict[str, Any]]:
    opens = quote_data.get("open") or []
    highs = quote_data.get("high") or []
    lows = quote_data.get("low") or []
    closes = quote_data.get("close") or []
    volumes = quote_data.get("volume") or []
    candles: list[dict[str, Any]] = []

    for index, ts in enumerate(timestamps):
        open_price = list_get(opens, index)
        high_price = list_get(highs, index)
        low_price = list_get(lows, index)
        close_price = list_get(closes, index)
        if any(not is_finite_number(value) for value in [open_price, high_price, low_price, close_price]):
            continue

        volume = list_get(volumes, index)
        candles.append(
            {
                "time": timestamp_to_iso(ts),
                "open": round(float(open_price), 6),
                "high": round(float(high_price), 6),
                "low": round(float(low_price), 6),
                "close": round(float(close_price), 6),
                "volume": int(volume) if isinstance(volume, (int, float)) and math.isfinite(volume) else 0,
            }
        )

    return candles


def list_get(values: list[Any], index: int) -> Any:
    if index >= len(values):
        return None
    return values[index]


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def finite_or_none(value: Any) -> float | int | None:
    if is_finite_number(value):
        return value
    return None


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def timestamp_to_iso(value: Any) -> str | None:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")
    with gzip.open(path.with_suffix(path.suffix + ".gz"), "wt", encoding="utf-8") as gz_file:
        gz_file.write(text)
        gz_file.write("\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_symbol_index(market: dict[str, Any], results: list[FetchResult]) -> dict[str, Any]:
    symbols = []
    fetched_by_symbol = {result.symbol["symbol"]: result.symbol for result in results}
    for configured in market["symbols"]:
        fetched = fetched_by_symbol.get(configured["symbol"], {})
        symbols.append(
            {
                "symbol": configured["symbol"],
                "displaySymbol": configured.get("displaySymbol", configured["symbol"]),
                "name": configured.get("name"),
                "exchange": configured.get("exchange"),
                "currency": fetched.get("currency") or configured.get("currency") or market.get("currency"),
                "timezone": fetched.get("timezone") or market.get("timezone"),
            }
        )

    return {
        "schemaVersion": "open-market-candles.symbols.v1",
        "market": market["id"],
        "name": market["name"],
        "symbols": symbols,
    }


def build_bundle(
    generated_at: str,
    provider_config: dict[str, Any],
    interval: str,
    data_range: str,
    market: dict[str, Any],
    results: list[FetchResult],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schemaVersion": "open-market-candles.bundle.v1",
        "generatedAt": generated_at,
        "provider": {
            "id": provider_config["id"],
            "name": provider_config["name"],
            "official": bool(provider_config.get("official")),
            "notice": provider_config.get("notice"),
        },
        "interval": interval,
        "range": data_range,
        "market": market["id"],
        "marketName": market["name"],
        "symbols": [
            {
                **result.symbol,
                "candles": result.candles,
            }
            for result in results
        ],
        "errors": errors,
    }


def build_index_html(manifest: dict[str, Any]) -> str:
    generated_at = manifest["generatedAt"]
    markets = "\n".join(
        f"<li><a href=\"{info['bundle']}\">{market.upper()} candles</a> "
        f"(<a href=\"{info['bundleGzip']}\">gzip</a>)</li>"
        for market, info in manifest["markets"].items()
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>open-market-candles</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 40px; line-height: 1.5; }}
    code {{ background: #f2f2f2; padding: 2px 4px; border-radius: 4px; }}
    main {{ max-width: 760px; }}
  </style>
</head>
<body>
  <main>
    <h1>open-market-candles</h1>
    <p>Generated at <code>{generated_at}</code>.</p>
    <ul>
      <li><a href="manifest.json">manifest.json</a></li>
      <li><a href="candles/1h/all/latest.json">all candles</a> (<a href="candles/1h/all/latest.json.gz">gzip</a>)</li>
      {markets}
    </ul>
    <p>Generated market data may be subject to upstream provider and exchange terms.</p>
  </main>
</body>
</html>
"""


def collect(config: dict[str, Any], output_dir: Path, interval: str, data_range: str, args: argparse.Namespace) -> int:
    generated_at = utc_now_iso()
    provider_id = args.provider or config["defaultProvider"]
    provider_config = config["providers"][provider_id]
    provider = YahooChartProvider(
        provider_config=provider_config,
        interval=interval,
        data_range=data_range,
        timeout=args.timeout,
        retries=args.retries,
        retry_sleep=args.retry_sleep,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    market_manifests: dict[str, Any] = {}
    all_results: list[FetchResult] = []
    all_errors: list[dict[str, Any]] = []

    for market in config["markets"]:
        market_id = market["id"]
        market_results: list[FetchResult] = []
        market_errors: list[dict[str, Any]] = []

        print(f"Collecting {market_id}: {len(market['symbols'])} symbols", file=sys.stderr)
        for symbol_config in market["symbols"]:
            symbol = symbol_config["symbol"]
            try:
                result = provider.fetch(symbol_config)
                market_results.append(result)
                print(f"  ok {symbol}: {len(result.candles)} candles", file=sys.stderr)
            except Exception as exc:
                error = {
                    "symbol": symbol,
                    "message": str(exc),
                    "failedAt": utc_now_iso(),
                }
                market_errors.append(error)
                print(f"  error {symbol}: {exc}", file=sys.stderr)
                if args.fail_fast:
                    raise
            time.sleep(args.request_delay)

        symbol_index = build_symbol_index(market, market_results)
        write_json(output_dir / "symbols" / f"{market_id}.json", symbol_index)

        market_bundle = build_bundle(
            generated_at=generated_at,
            provider_config=provider_config,
            interval=interval,
            data_range=data_range,
            market=market,
            results=market_results,
            errors=market_errors,
        )
        bundle_path = Path("candles") / interval / market_id / "latest.json"
        write_json(output_dir / bundle_path, market_bundle)

        market_manifests[market_id] = {
            "name": market["name"],
            "symbolCount": len(market["symbols"]),
            "successCount": len(market_results),
            "errorCount": len(market_errors),
            "symbols": f"symbols/{market_id}.json",
            "symbolsGzip": f"symbols/{market_id}.json.gz",
            "bundle": bundle_path.as_posix(),
            "bundleGzip": f"{bundle_path.as_posix()}.gz",
        }

        all_results.extend(market_results)
        all_errors.extend({**error, "market": market_id} for error in market_errors)

    all_symbol_index = {
        "schemaVersion": "open-market-candles.symbols.v1",
        "market": "all",
        "name": "All markets",
        "symbols": [
            symbol
            for market in config["markets"]
            for symbol in build_symbol_index(market, all_results)["symbols"]
        ],
    }
    write_json(output_dir / "symbols" / "all.json", all_symbol_index)

    all_bundle = {
        "schemaVersion": "open-market-candles.bundle.v1",
        "generatedAt": generated_at,
        "provider": {
            "id": provider_config["id"],
            "name": provider_config["name"],
            "official": bool(provider_config.get("official")),
            "notice": provider_config.get("notice"),
        },
        "interval": interval,
        "range": data_range,
        "market": "all",
        "marketName": "All markets",
        "symbols": [
            {
                **result.symbol,
                "candles": result.candles,
            }
            for result in all_results
        ],
        "errors": all_errors,
    }
    all_bundle_path = Path("candles") / interval / "all" / "latest.json"
    write_json(output_dir / all_bundle_path, all_bundle)

    manifest = {
        "schemaVersion": "open-market-candles.manifest.v1",
        "generatedAt": generated_at,
        "intervals": [interval],
        "range": data_range,
        "provider": {
            "id": provider_config["id"],
            "name": provider_config["name"],
            "official": bool(provider_config.get("official")),
            "notice": provider_config.get("notice"),
        },
        "markets": market_manifests,
        "bundles": {
            "all": {
                "bundle": all_bundle_path.as_posix(),
                "bundleGzip": f"{all_bundle_path.as_posix()}.gz",
                "symbols": "symbols/all.json",
                "symbolsGzip": "symbols/all.json.gz",
            }
        },
        "privacyRecommendation": "Download broad market bundles instead of per-symbol files when building privacy-sensitive clients.",
        "dataNotice": "Generated market data may be subject to upstream provider and exchange terms. See DATA_NOTICE.md in the source repository.",
    }
    write_json(output_dir / "manifest.json", manifest)
    write_text(output_dir / "index.html", build_index_html(manifest))
    write_text(output_dir / "DATA_NOTICE.txt", "Generated market data may be subject to upstream provider and exchange terms.\n")
    write_text(output_dir / ".nojekyll", "")

    failure_count = sum(market["errorCount"] for market in market_manifests.values())
    if failure_count and args.fail_on_errors:
        return 2
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/universe.json"))
    parser.add_argument("--output", type=Path, default=Path("public"))
    parser.add_argument("--provider", default=None)
    parser.add_argument("--interval", default=None)
    parser.add_argument("--range", default=None, dest="data_range")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    parser.add_argument("--request-delay", type=float, default=0.5)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--fail-on-errors", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    interval = args.interval or config["defaultInterval"]
    data_range = args.data_range or config["defaultRange"]
    return collect(config, args.output, interval, data_range, args)


if __name__ == "__main__":
    raise SystemExit(main())
