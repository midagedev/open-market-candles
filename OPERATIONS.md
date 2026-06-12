# Operations

## Repository Setup

1. Create a public GitHub repository.
2. Push `main`.
3. Enable GitHub Pages from the `gh-pages` branch root, or run:

```bash
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  /repos/<owner>/open-market-candles/pages \
  -f source='{"branch":"gh-pages","path":"/"}'
```

If Pages already exists, use `PUT` instead of `POST`.

## Scheduled Publishing

The workflow:

- checks out `main`
- runs the collector
- validates the generated static files
- force-pushes the generated `public/` directory to `gh-pages`

This keeps generated data out of `main` history while still making the latest dataset available as static files.

## Manual Publish

From a local checkout:

```bash
python3 scripts/collect_market_data.py --output public
python3 scripts/validate_dataset.py public
scripts/publish_gh_pages.sh public
```

The publish script uses the current `origin` remote.

## Failure Policy

The collector allows partial success by default. If one symbol fails, the bundle still publishes successful symbols and records failures under `errors`.

The validator requires at least one successful symbol per configured market. This catches total provider outages while tolerating individual ticker problems.

## Scaling

Keep the starter universe small. If the universe grows:

- increase delays between provider requests
- split by market
- cache unchanged files
- consider a licensed provider
- avoid committing generated data to `main`
