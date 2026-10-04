# Riftbound Market Pulse

Public website: https://bing-bot-boop.github.io/riftbound-market-pulse/

Card catalogue, images, current published prices, watchlist, card comparisons, tournament histories, and direct evidence links.

## Automatic updates

The `Update public Riftbound sources` GitHub Actions workflow runs around hourly (17 minutes past the hour), on source-script changes, or manually with Run workflow. It checks Riftbound Zone's published usage, winners and win rates, and KLXCards' most-played card histories and latest published deck listings. Catalogue and price backups are collected daily. The page requests current RiftHunt prices directly and reloads available feeds every 15 minutes while visible.

Refresh live data reloads the public feeds and the latest collected tournament data. It does not dispatch a crawler or discover arbitrary websites. RiftHunt's price export is updated daily; none of these sources provides marketplace tick data. Published best-finish lists are selected by KLXCards, not all appearances. Missing history is unknown, not zero.

The page fetches collected data from the repository's raw data files so scheduled bot commits are usable even when GitHub does not trigger a Pages build for them. It falls back to the deployed snapshot and browser cache when necessary, and displays source check times and failures. Last successful per-card histories are retained with their original check time after failed checks.

GitHub can delay scheduled workflows, and it disables schedules in public repositories after 60 days without repository activity. Monitor the update status link and the freshness notice; resume a disabled workflow from Actions. Source sites can change their layouts or availability. The collector validates responses and retains prior data rather than inventing replacement statistics.

## Development

Static site: `index.html`, `404.html`, `health.html`, `.nojekyll`. No build step.

Collector:

```sh
pip install beautifulsoup4==4.15.0
python scripts/refresh_sources.py
```

The workflow needs `contents: write` to commit refreshed public JSON files. It uses GitHub's automatic workflow token; no keys belong in the browser.

Source catalogue: https://rifthunt.com/api/
Tournament usage: https://riftbound.zone/en/meta-stats/
Published histories: https://klxcards.com/decks/riftbound/

Unofficial community project. Card names, rules, and art belong to Riot Games.
