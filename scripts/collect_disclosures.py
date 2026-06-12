#!/usr/bin/env python3
"""Collect official disclosure metadata and publish static event bundles."""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SEC_BASE_URL = "https://data.sec.gov/submissions"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
OPENDART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DART_VIEWER_URL = "https://dart.fss.or.kr/dsaf001/main.do"
DEFAULT_SEC_USER_AGENT = "open-market-candles hckim@imagoworks.ai"


class DisclosureError(RuntimeError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")
    with gzip.open(path.with_suffix(path.suffix + ".gz"), "wt", encoding="utf-8") as gz_file:
        gz_file.write(text)
        gz_file.write("\n")


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def request_json(url: str, headers: dict[str, str], timeout: int, retries: int, retry_sleep: float) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip" or raw.startswith(b"\x1f\x8b"):
                    raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            last_error = exc
            if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                break
            time.sleep(min(retry_sleep * (2**attempt), 60))
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(min(retry_sleep * (2**attempt), 60))
    raise DisclosureError(f"request failed after retries: {last_error}")


def parse_sec_datetime(value: str) -> str | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def sec_primary_document_url(cik: str, accession_number: str, primary_document: str) -> str | None:
    if not accession_number or not primary_document:
        return None
    cik_int = str(int(cik))
    accession_no_dashes = accession_number.replace("-", "")
    return f"{SEC_ARCHIVES_URL}/{cik_int}/{accession_no_dashes}/{primary_document}"


def collect_sec_symbol(
    symbol: dict[str, Any],
    since: date,
    headers: dict[str, str],
    timeout: int,
    retries: int,
    retry_sleep: float,
) -> list[dict[str, Any]]:
    cik = str(symbol.get("secCik") or "").zfill(10)
    if not cik or cik == "0000000000":
        raise DisclosureError(f"{symbol['symbol']}: missing secCik")

    payload = request_json(
        f"{SEC_BASE_URL}/CIK{cik}.json",
        headers=headers,
        timeout=timeout,
        retries=retries,
        retry_sleep=retry_sleep,
    )
    recent = (payload.get("filings") or {}).get("recent") or {}
    accession_numbers = recent.get("accessionNumber") or []
    events: list[dict[str, Any]] = []

    for index, accession_number in enumerate(accession_numbers):
        filing_date = list_get(recent.get("filingDate") or [], index) or ""
        parsed_filing_date = parse_date(filing_date)
        if parsed_filing_date is None or parsed_filing_date < since:
            continue

        form = list_get(recent.get("form") or [], index) or ""
        primary_document = list_get(recent.get("primaryDocument") or [], index) or ""
        accepted_at = parse_sec_datetime(list_get(recent.get("acceptanceDateTime") or [], index) or "")
        url = sec_primary_document_url(cik, accession_number, primary_document)
        events.append(
            {
                "id": f"sec-{cik}-{accession_number}",
                "market": "us",
                "symbol": symbol["symbol"],
                "displaySymbol": symbol.get("displaySymbol", symbol["symbol"]),
                "companyName": symbol.get("name") or payload.get("name"),
                "source": "SEC EDGAR",
                "sourceId": "sec-edgar",
                "official": True,
                "type": form,
                "title": form,
                "filedDate": filing_date,
                "acceptedAt": accepted_at,
                "url": url,
                "accessionNumber": accession_number,
                "primaryDocument": primary_document,
                "primaryDocDescription": list_get(recent.get("primaryDocDescription") or [], index) or "",
                "reportDate": list_get(recent.get("reportDate") or [], index) or "",
                "items": list_get(recent.get("items") or [], index) or "",
                "size": finite_int_or_none(list_get(recent.get("size") or [], index)),
            }
        )

    return events


def collect_sec(
    market: dict[str, Any],
    since: date,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    user_agent = os.environ.get("SEC_USER_AGENT") or args.sec_user_agent or DEFAULT_SEC_USER_AGENT
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }
    events: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for symbol in market["symbols"]:
        try:
            symbol_events = collect_sec_symbol(
                symbol=symbol,
                since=since,
                headers=headers,
                timeout=args.timeout,
                retries=args.retries,
                retry_sleep=args.retry_sleep,
            )
            events.extend(symbol_events)
            print(f"  ok SEC {symbol['symbol']}: {len(symbol_events)} disclosures", file=sys.stderr)
        except Exception as exc:
            errors.append(
                {
                    "symbol": symbol["symbol"],
                    "sourceId": "sec-edgar",
                    "message": str(exc),
                    "failedAt": utc_now_iso(),
                }
            )
            print(f"  error SEC {symbol['symbol']}: {exc}", file=sys.stderr)
            if args.fail_fast:
                raise
        time.sleep(args.request_delay)

    return events, errors, {
        "id": "sec-edgar",
        "name": "SEC EDGAR submissions API",
        "official": True,
        "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
    }


def collect_opendart(
    market: dict[str, Any],
    since: date,
    until: date,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    api_key = os.environ.get("OPENDART_API_KEY") or args.opendart_api_key
    source = {
        "id": "opendart",
        "name": "OpenDART disclosure search API",
        "official": True,
        "url": "https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001",
        "requiresSecret": "OPENDART_API_KEY",
    }
    if not api_key:
        return [], [
            {
                "market": market["id"],
                "sourceId": "opendart",
                "message": "skipped: OPENDART_API_KEY is not configured",
                "failedAt": utc_now_iso(),
            }
        ], source

    wanted = {
        normalize_kr_stock_code(symbol.get("displaySymbol") or symbol["symbol"]): symbol
        for symbol in market["symbols"]
    }
    events: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    page_no = 1
    total_page = 1

    while page_no <= total_page:
        query = urlencode(
            {
                "crtfc_key": api_key,
                "bgn_de": since.strftime("%Y%m%d"),
                "end_de": until.strftime("%Y%m%d"),
                "last_reprt_at": "N",
                "corp_cls": "Y",
                "page_no": page_no,
                "page_count": args.opendart_page_count,
                "sort": "date",
                "sort_mth": "desc",
            }
        )
        payload = request_json(
            f"{OPENDART_LIST_URL}?{query}",
            headers={"Accept": "application/json"},
            timeout=args.timeout,
            retries=args.retries,
            retry_sleep=args.retry_sleep,
        )
        status = payload.get("status")
        if status == "013":
            break
        if status != "000":
            raise DisclosureError(f"OpenDART status {status}: {payload.get('message')}")

        total_page = int(payload.get("total_page") or 1)
        for item in payload.get("list") or []:
            stock_code = normalize_kr_stock_code(item.get("stock_code") or "")
            symbol = wanted.get(stock_code)
            if not symbol:
                continue
            rcept_no = item.get("rcept_no") or ""
            report_name = item.get("report_nm") or ""
            filed_date = dart_date_to_iso_date(item.get("rcept_dt") or "")
            events.append(
                {
                    "id": f"dart-{rcept_no}",
                    "market": "kr",
                    "symbol": symbol["symbol"],
                    "displaySymbol": symbol.get("displaySymbol", stock_code),
                    "companyName": item.get("corp_name") or symbol.get("name"),
                    "source": "OpenDART",
                    "sourceId": "opendart",
                    "official": True,
                    "type": report_name,
                    "title": report_name,
                    "filedDate": filed_date,
                    "acceptedAt": None,
                    "url": f"{DART_VIEWER_URL}?rcpNo={rcept_no}" if rcept_no else None,
                    "receiptNumber": rcept_no,
                    "corpCode": item.get("corp_code") or "",
                    "stockCode": stock_code,
                    "filerName": item.get("flr_nm") or "",
                    "corpClass": item.get("corp_cls") or "",
                    "remarks": item.get("rm") or "",
                }
            )
        print(f"  ok OpenDART page {page_no}/{total_page}: {len(events)} matched disclosures", file=sys.stderr)
        page_no += 1
        time.sleep(args.request_delay)

    return events, errors, source


def list_get(values: list[Any], index: int) -> Any:
    if index >= len(values):
        return None
    return values[index]


def finite_int_or_none(value: Any) -> int | None:
    if isinstance(value, (int, float)) and math.isfinite(value):
        return int(value)
    return None


def normalize_kr_stock_code(value: str) -> str:
    return value.replace(".KS", "").replace(".KQ", "").zfill(6)


def dart_date_to_iso_date(value: str) -> str:
    if len(value) == 8 and value.isdigit():
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    return value


def build_bundle(
    generated_at: str,
    market: dict[str, Any],
    lookback_days: int,
    since: date,
    until: date,
    sources: list[dict[str, Any]],
    events: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    events.sort(key=lambda event: (event.get("filedDate") or "", event.get("acceptedAt") or ""), reverse=True)
    return {
        "schemaVersion": "open-market-candles.disclosures.v1",
        "generatedAt": generated_at,
        "kind": "disclosures",
        "market": market["id"],
        "marketName": market["name"],
        "lookbackDays": lookback_days,
        "fromDate": since.isoformat(),
        "toDate": until.isoformat(),
        "sources": sources,
        "events": events,
        "errors": errors,
    }


def update_manifest(output_dir: Path, generated_at: str, interval: str, market_manifests: dict[str, Any], all_path: Path) -> None:
    manifest_path = output_dir / "manifest.json"
    manifest = read_json_if_exists(manifest_path)
    if not manifest:
        manifest = {
            "schemaVersion": "open-market-candles.manifest.v1",
            "generatedAt": generated_at,
            "intervals": [interval],
            "markets": {},
            "bundles": {},
        }

    manifest["generatedAt"] = manifest.get("generatedAt") or generated_at
    manifest.setdefault("events", {})["disclosures"] = {
        "schemaVersion": "open-market-candles.disclosures.v1",
        "generatedAt": generated_at,
        "markets": market_manifests,
        "bundle": all_path.as_posix(),
        "bundleGzip": f"{all_path.as_posix()}.gz",
    }
    write_json(manifest_path, manifest)
    write_index_html(output_dir / "index.html", manifest)


def write_index_html(path: Path, manifest: dict[str, Any]) -> None:
    generated_at = manifest.get("generatedAt", "")
    market_links = "\n".join(
        f"<li><a href=\"{info['bundle']}\">{market.upper()} candles</a> "
        f"(<a href=\"{info['bundleGzip']}\">gzip</a>)</li>"
        for market, info in (manifest.get("markets") or {}).items()
    )
    disclosure_info = (manifest.get("events") or {}).get("disclosures") or {}
    disclosure_links = ""
    if disclosure_info:
        disclosure_links = "\n".join(
            f"<li><a href=\"{info['bundle']}\">{market.upper()} disclosures</a> "
            f"(<a href=\"{info['bundleGzip']}\">gzip</a>)</li>"
            for market, info in (disclosure_info.get("markets") or {}).items()
        )

    text = f"""<!doctype html>
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
    <h2>Market data</h2>
    <ul>
      <li><a href="manifest.json">manifest.json</a></li>
      <li><a href="candles/1h/all/latest.json">all candles</a> (<a href="candles/1h/all/latest.json.gz">gzip</a>)</li>
      {market_links}
    </ul>
    <h2>Disclosure events</h2>
    <ul>
      <li><a href="events/disclosures/all/latest.json">all disclosures</a> (<a href="events/disclosures/all/latest.json.gz">gzip</a>)</li>
      {disclosure_links}
    </ul>
    <p>Generated market data may be subject to upstream provider and exchange terms.</p>
  </main>
</body>
</html>
"""
    path.write_text(text, encoding="utf-8")


def collect(config: dict[str, Any], output_dir: Path, args: argparse.Namespace) -> int:
    generated_at = utc_now_iso()
    lookback_days = args.lookback_days or int(config.get("defaultDisclosureLookbackDays") or 30)
    until = datetime.now(timezone.utc).date()
    since = until - timedelta(days=lookback_days)
    interval = config.get("defaultInterval", "1h")
    output_dir.mkdir(parents=True, exist_ok=True)

    market_manifests: dict[str, Any] = {}
    all_events: list[dict[str, Any]] = []
    all_errors: list[dict[str, Any]] = []
    all_sources: dict[str, dict[str, Any]] = {}

    for market in config["markets"]:
        market_id = market["id"]
        print(f"Collecting disclosures {market_id}", file=sys.stderr)
        if market_id == "us":
            events, errors, source = collect_sec(market, since, args)
            sources = [source]
        elif market_id == "kr":
            events, errors, source = collect_opendart(market, since, until, args)
            sources = [source]
        else:
            events = []
            errors = [
                {
                    "market": market_id,
                    "message": "skipped: no disclosure provider configured for market",
                    "failedAt": utc_now_iso(),
                }
            ]
            sources = []

        bundle = build_bundle(generated_at, market, lookback_days, since, until, sources, events, errors)
        bundle_path = Path("events") / "disclosures" / market_id / "latest.json"
        write_json(output_dir / bundle_path, bundle)

        market_manifests[market_id] = {
            "name": market["name"],
            "eventCount": len(events),
            "errorCount": len(errors),
            "bundle": bundle_path.as_posix(),
            "bundleGzip": f"{bundle_path.as_posix()}.gz",
        }
        all_events.extend(events)
        all_errors.extend({**error, "market": error.get("market") or market_id} for error in errors)
        for source in sources:
            all_sources[source["id"]] = source

    all_market = {"id": "all", "name": "All markets"}
    all_bundle_path = Path("events") / "disclosures" / "all" / "latest.json"
    all_bundle = build_bundle(
        generated_at=generated_at,
        market=all_market,
        lookback_days=lookback_days,
        since=since,
        until=until,
        sources=list(all_sources.values()),
        events=all_events,
        errors=all_errors,
    )
    write_json(output_dir / all_bundle_path, all_bundle)
    update_manifest(output_dir, generated_at, interval, market_manifests, all_bundle_path)

    if all_errors and args.fail_on_errors:
        return 2
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/universe.json"))
    parser.add_argument("--output", type=Path, default=Path("public"))
    parser.add_argument("--lookback-days", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-sleep", type=float, default=2.0)
    parser.add_argument("--request-delay", type=float, default=0.4)
    parser.add_argument("--sec-user-agent", default=None)
    parser.add_argument("--opendart-api-key", default=None)
    parser.add_argument("--opendart-page-count", type=int, default=100)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--fail-on-errors", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    return collect(config, args.output, args)


if __name__ == "__main__":
    raise SystemExit(main())
