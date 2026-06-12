# Data Notice

This repository separates code from generated market data. It is a publishing pipeline and reference static dataset, not a licensed market data vendor.

## Code

The scripts, workflow files, and documentation in this repository are licensed under the MIT License.

## Generated Market Data

Generated files under the published static site contain transformed market data from the configured provider. The default provider is `yahoo-chart`, which reads Yahoo Finance chart responses through unofficial endpoints.

Do not assume that generated market data is public domain or covered by this repository's MIT License. Market data may be subject to:

- source website terms
- exchange redistribution rules
- delayed-data rules
- commercial-use restrictions
- API availability and rate limits

If you need a legally clean public dataset, replace the default provider with a source whose license explicitly permits redistribution, or publish only derived data that your counsel and provider agreement allow.

Do not submit paid-provider data, credentials, private API responses, or copyrighted market datasets in issues or pull requests.

## News And Articles

This repository intentionally does not republish full news articles. News content is copyright-sensitive. A future events pipeline should prefer:

- official disclosures
- SEC EDGAR metadata and filing links
- OpenDART metadata and filing links
- licensed news metadata
- short, original educational explanations based on official facts

## Not Investment Advice

The generated files are for educational and software-development use. They are not investment advice and should not be used as the sole source for trading decisions.

## No Warranty

The data can be stale, delayed, adjusted, incomplete, or wrong. Client applications should display freshness, tolerate missing symbols, and avoid making financial decisions from this dataset alone.
