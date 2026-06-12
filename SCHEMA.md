# Schema

The generated schema is intentionally small and stable.

Live manifest:

```text
https://midagedev.github.io/open-market-candles/manifest.json
```

## manifest.json

```json
{
  "schemaVersion": "open-market-candles.manifest.v1",
  "generatedAt": "2026-06-13T00:00:00Z",
  "intervals": ["1h"],
  "markets": {
    "us": {
      "name": "United States",
      "symbolCount": 10,
      "successCount": 10,
      "errorCount": 0,
      "symbols": "symbols/us.json",
      "symbolsGzip": "symbols/us.json.gz",
      "bundle": "candles/1h/us/latest.json",
      "bundleGzip": "candles/1h/us/latest.json.gz"
    }
  },
  "bundles": {
    "all": {
      "bundle": "candles/1h/all/latest.json",
      "bundleGzip": "candles/1h/all/latest.json.gz"
    }
  }
}
```

## Candle Bundle

```json
{
  "schemaVersion": "open-market-candles.bundle.v1",
  "generatedAt": "2026-06-13T00:00:00Z",
  "provider": {
    "id": "yahoo-chart",
    "name": "Yahoo Finance chart",
    "official": false
  },
  "interval": "1h",
  "range": "1mo",
  "market": "us",
  "symbols": [
    {
      "symbol": "AAPL",
      "displaySymbol": "AAPL",
      "name": "Apple Inc.",
      "currency": "USD",
      "exchange": "NASDAQ",
      "timezone": "America/New_York",
      "regularMarketPrice": 200.0,
      "regularMarketTime": "2026-06-12T20:00:00Z",
      "candles": [
        {
          "time": "2026-06-12T13:30:00Z",
          "open": 200.0,
          "high": 201.0,
          "low": 199.0,
          "close": 200.5,
          "volume": 1000000
        }
      ]
    }
  ],
  "errors": []
}
```

## Error Object

```json
{
  "symbol": "AAPL",
  "message": "request failed after retries: HTTP Error 429: Too Many Requests",
  "failedAt": "2026-06-13T00:00:00Z"
}
```

## Notes

- Times are UTC ISO-8601 strings.
- Prices are numbers.
- Volume is an integer when available, otherwise `0`.
- Client apps should treat missing symbols and stale bundles as normal network-data conditions.
- Clients should fetch `manifest.json` first, then follow relative paths from the manifest.
- `schemaVersion` changes when a breaking schema change is introduced.
