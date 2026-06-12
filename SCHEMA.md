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

## Disclosure Bundle

```json
{
  "schemaVersion": "open-market-candles.disclosures.v1",
  "generatedAt": "2026-06-13T00:00:00Z",
  "kind": "disclosures",
  "market": "us",
  "marketName": "United States",
  "lookbackDays": 30,
  "fromDate": "2026-05-14",
  "toDate": "2026-06-13",
  "sources": [
    {
      "id": "sec-edgar",
      "name": "SEC EDGAR submissions API",
      "official": true,
      "url": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
    }
  ],
  "events": [
    {
      "id": "sec-0000320193-0000320193-26-000001",
      "market": "us",
      "symbol": "AAPL",
      "displaySymbol": "AAPL",
      "companyName": "Apple Inc.",
      "source": "SEC EDGAR",
      "sourceId": "sec-edgar",
      "official": true,
      "type": "10-Q",
      "title": "10-Q",
      "filedDate": "2026-06-12",
      "acceptedAt": "2026-06-12T20:00:00Z",
      "url": "https://www.sec.gov/Archives/edgar/data/..."
    }
  ],
  "errors": []
}
```

Korean OpenDART events use the same outer shape and include DART-specific fields such as `receiptNumber`, `corpCode`, `stockCode`, `filerName`, and `remarks`.

## Error Object

```json
{
  "symbol": "AAPL",
  "message": "request failed after retries: HTTP Error 429: Too Many Requests",
  "failedAt": "2026-06-13T00:00:00Z"
}
```

Disclosure bundles may also include source-level skip errors:

```json
{
  "market": "kr",
  "sourceId": "opendart",
  "message": "skipped: OPENDART_API_KEY is not configured",
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
- Disclosure event `filedDate` is a `YYYY-MM-DD` date.
- Disclosure event `acceptedAt` is UTC ISO-8601 when the source provides a timestamp, otherwise `null`.
