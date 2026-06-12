# open-market-candles

Static hourly OHLCV bundles for a small KR/US stock universe.

This repository is designed as a simple public data-publishing pipeline:

- GitHub Actions collects market candles on a schedule.
- Generated JSON files are published to GitHub Pages.
- Client apps can download broad market bundles instead of per-symbol files, which avoids exposing a user's exact watchlist through request logs.
- No account system, analytics SDK, app telemetry, or user portfolio data is involved.

> Important: the default collector uses Yahoo Finance chart responses because they are available without API keys and cover both US and Korean symbols. This is an unofficial source. Review provider terms before treating generated data as openly licensed or production-grade.

## Published Files

When GitHub Pages is enabled, the public URL shape is:

```text
https://<owner>.github.io/open-market-candles/manifest.json
https://<owner>.github.io/open-market-candles/symbols/us.json
https://<owner>.github.io/open-market-candles/symbols/kr.json
https://<owner>.github.io/open-market-candles/candles/1h/us/latest.json
https://<owner>.github.io/open-market-candles/candles/1h/kr/latest.json
https://<owner>.github.io/open-market-candles/candles/1h/all/latest.json
```

Gzip variants are generated next to the JSON files:

```text
*.json.gz
```

## Local Run

```bash
python3 scripts/collect_market_data.py --output public
python3 scripts/validate_dataset.py public
```

Open the generated static site:

```bash
python3 -m http.server 8000 --directory public
```

## Configuration

Edit [config/universe.json](config/universe.json) to change:

- markets
- symbols
- default interval
- default range
- provider metadata

The default schedule in [.github/workflows/publish-data.yml](.github/workflows/publish-data.yml) runs once per hour at minute 17 UTC. GitHub can delay or skip scheduled workflows during heavy load, so client apps should always read `manifest.generatedAt` and tolerate stale data.

## Data Shape

See [SCHEMA.md](SCHEMA.md).

## Legal And Source Notice

See [DATA_NOTICE.md](DATA_NOTICE.md). Code is MIT licensed. Generated market data may be subject to upstream provider terms and exchange rules.

## Privacy Model For Client Apps

For privacy-sensitive apps, download a broad bundle such as:

```text
candles/1h/all/latest.json.gz
```

Avoid requesting one file per symbol from a server you do not control. Even without app accounts, per-symbol network requests can reveal user interest through CDN or server logs.
