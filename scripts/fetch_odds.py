"""Server-side odds fetcher. Never expose ODDS_API_KEY to the public site."""
import datetime as dt
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "odds.json"
KEY = os.getenv("ODDS_API_KEY", "").strip()
if not KEY:
    print("ODDS_API_KEY GitHub Actions secret not configured; keeping existing snapshot.")
    raise SystemExit(0)

params = urllib.parse.urlencode({
    "apiKey": KEY,
    "regions": "us",
    "markets": "spreads,totals",
    "oddsFormat": "american",
})
url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds/?" + params
try:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Wolfpack/1.0"}), timeout=25) as resp:
        games = json.load(resp)
        remaining = resp.headers.get("x-requests-remaining")
except (urllib.error.URLError, ValueError) as exc:
    print("Odds request failed; keeping last good snapshot:", str(exc))
    raise SystemExit(1)
if not isinstance(games, list):
    raise ValueError("Unexpected odds payload")
snapshot = {
    "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "source": "The Odds API",
    "remaining_credits": remaining,
    "games": games,
}
OUT.write_text(json.dumps(snapshot, separators=(",", ":")) + "\n")
print(f"Fetched {len(games)} events; credits remaining: {remaining}")
