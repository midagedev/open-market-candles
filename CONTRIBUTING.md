# Contributing

Thanks for helping make `open-market-candles` more useful.

## Before Opening A Pull Request

- Run `python3 scripts/collect_market_data.py --output public`.
- Run `python3 scripts/validate_dataset.py public`.
- Keep generated `public/` files out of the pull request.
- Keep the starter universe small unless the change includes a clear scaling reason.
- Do not add paid-provider responses, API keys, credentials, or copyrighted datasets.

## Provider Changes

Provider changes should explain:

- source terms and redistribution limits
- authentication requirements
- rate limits
- supported markets and intervals
- how failures appear in generated `errors`

Prefer licensed or explicitly redistributable sources over scraper-only sources.

## Symbol Changes

Symbol changes should be small and easy to review. Include:

- market
- exchange
- provider symbol
- display symbol
- company name

## Schema Changes

Avoid breaking clients casually. For breaking changes:

- update `schemaVersion`
- update [SCHEMA.md](SCHEMA.md)
- keep old fields when practical
- document migration notes in the pull request

## News And Events

Do not submit full article text. Prefer official filing metadata, source links, and original educational summaries based on official facts.
