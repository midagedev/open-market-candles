# Operations

Production repository:

- Repository: https://github.com/midagedev/open-market-candles
- Static site: https://midagedev.github.io/open-market-candles/
- Manifest: https://midagedev.github.io/open-market-candles/manifest.json
- Workflow: https://github.com/midagedev/open-market-candles/actions/workflows/publish-data.yml

## Repository Setup

1. Create a public GitHub repository.
2. Push `main`.
3. Run the publish workflow once so the `gh-pages` branch exists.
4. Enable GitHub Pages from the `gh-pages` branch root.

Using the GitHub CLI:

```bash
gh api \
  --method POST \
  -H "Accept: application/vnd.github+json" \
  /repos/<owner>/<repo>/pages \
  -f source[branch]=gh-pages \
  -f source[path]=/
```

Verify:

```bash
gh api /repos/<owner>/<repo>/pages
```

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

## Repository Metadata

For a public repository, set the homepage to the Pages URL:

```bash
gh repo edit <owner>/<repo> \
  --homepage https://<owner>.github.io/<repo>/ \
  --add-topic market-data \
  --add-topic stocks \
  --add-topic ohlcv \
  --add-topic github-actions
```

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
