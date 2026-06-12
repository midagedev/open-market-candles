# open-market-candles

[![Publish static market data](https://github.com/midagedev/open-market-candles/actions/workflows/publish-data.yml/badge.svg)](https://github.com/midagedev/open-market-candles/actions/workflows/publish-data.yml)
[![GitHub Pages](https://img.shields.io/badge/data-GitHub%20Pages-blue)](https://midagedev.github.io/open-market-candles/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Static hourly OHLCV bundles for a small US/KR stock universe, published as plain JSON files on GitHub Pages.

- Repository: https://github.com/midagedev/open-market-candles
- Static data site: https://midagedev.github.io/open-market-candles/
- Manifest: https://midagedev.github.io/open-market-candles/manifest.json
- Latest all-market gzip bundle: https://midagedev.github.io/open-market-candles/candles/1h/all/latest.json.gz

This project is intentionally simple: a scheduled GitHub Actions workflow collects candles, validates the generated files, and force-publishes the current static dataset to the `gh-pages` branch.

> Source notice: the default collector uses unofficial Yahoo Finance chart responses because they are available without API keys and cover both US and Korean symbols. Review upstream provider and exchange terms before treating generated data as openly redistributable or production-grade. See [DATA_NOTICE.md](DATA_NOTICE.md).

## What This Is

- A reference pipeline for publishing small market-data bundles as static files.
- A privacy-friendly data shape for client apps that should not reveal a user's watchlist through per-symbol requests.
- A forkable template for people who want to run the same pipeline with their own symbol universe or licensed provider.

## What This Is Not

- A licensed market data vendor.
- A guaranteed real-time feed.
- Investment advice.
- A place to republish full news articles or copyrighted research.

## Live Endpoints

| File | URL |
| --- | --- |
| Manifest | `https://midagedev.github.io/open-market-candles/manifest.json` |
| All symbols | `https://midagedev.github.io/open-market-candles/symbols/all.json` |
| US symbols | `https://midagedev.github.io/open-market-candles/symbols/us.json` |
| KR symbols | `https://midagedev.github.io/open-market-candles/symbols/kr.json` |
| All 1h candles | `https://midagedev.github.io/open-market-candles/candles/1h/all/latest.json` |
| US 1h candles | `https://midagedev.github.io/open-market-candles/candles/1h/us/latest.json` |
| KR 1h candles | `https://midagedev.github.io/open-market-candles/candles/1h/kr/latest.json` |

Every JSON file is also published with a `.gz` file next to it. For app clients, prefer the gzip bundle:

```text
https://midagedev.github.io/open-market-candles/candles/1h/all/latest.json.gz
```

## Quick Start

Fetch the manifest:

```bash
curl -L https://midagedev.github.io/open-market-candles/manifest.json
```

Fetch and inspect the all-market gzip bundle:

```bash
curl -L https://midagedev.github.io/open-market-candles/candles/1h/all/latest.json.gz \
  | gzip -dc \
  | python3 -m json.tool
```

Read the latest status with Python:

```bash
python3 - <<'PY'
import json
import urllib.request

url = "https://midagedev.github.io/open-market-candles/manifest.json"
with urllib.request.urlopen(url, timeout=20) as response:
    manifest = json.load(response)

print(manifest["generatedAt"])
for market, info in manifest["markets"].items():
    print(market, info["successCount"], "ok,", info["errorCount"], "errors")
PY
```

## Current Universe

The starter universe is deliberately small to keep GitHub Pages bandwidth, workflow time, and provider pressure low.

| Market | Symbols |
| --- | --- |
| US | AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA, BRK-B, JPM, V |
| KR | 005930, 000660, 035420, 035720, 005380, 000270, 051910, 006400, 068270, 207940 |

Edit [config/universe.json](config/universe.json) to change markets, symbols, interval, range, or provider metadata.

## Freshness

- Default interval: `1h`
- Default range: `1mo`
- Schedule: once per hour at minute 17 UTC
- Workflow: [Publish static market data](https://github.com/midagedev/open-market-candles/actions/workflows/publish-data.yml)

GitHub scheduled workflows can be delayed or skipped during heavy load. Client apps should always read `manifest.generatedAt` and tolerate stale or partial data.

## Local Development

No third-party Python packages are required.

```bash
python3 scripts/collect_market_data.py --output public
python3 scripts/validate_dataset.py public
python3 -m http.server 8000 --directory public
```

Then open:

```text
http://localhost:8000/manifest.json
```

## Fork And Operate

1. Fork this repository.
2. Edit [config/universe.json](config/universe.json).
3. Enable GitHub Actions on the fork.
4. Run the `Publish static market data` workflow manually once.
5. Enable GitHub Pages from the `gh-pages` branch root.
6. Point your app at `https://<owner>.github.io/<repo>/manifest.json`.

The workflow publishes generated files to `gh-pages` and keeps generated data out of the `main` branch history.

## Privacy Model

For privacy-sensitive clients, download a broad bundle such as:

```text
candles/1h/all/latest.json.gz
```

Avoid one request per watched symbol. Even without accounts or analytics, per-symbol requests can reveal user interests through server, CDN, or proxy logs.

## Schema

See [SCHEMA.md](SCHEMA.md). The short version:

- `manifest.json` tells clients which bundles exist and when they were generated.
- `symbols/*.json` lists configured symbols by market.
- `candles/1h/*/latest.json` contains symbol metadata and OHLCV candles.
- `errors` records per-symbol collection failures without failing the whole bundle.

## Limitations

- The default provider is unofficial and may rate-limit, change, or stop responding.
- Market data may be delayed, adjusted, incomplete, or subject to redistribution restrictions.
- The pipeline does not currently publish corporate actions, fundamentals, filings, or news.
- The generated data is not covered by the MIT license for this repository's code.

## Contributing

Issues and pull requests are welcome, especially for:

- safer licensed providers
- clearer schema evolution
- better validation
- small, well-explained universe changes
- official disclosure/event metadata

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing provider or dataset changes.
