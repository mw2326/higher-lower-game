# Higher or Lower: K-Pop Stream Edition

A web-based guessing game where you compare real Spotify stream counts for K-pop tracks.

Stream counts are scraped from [MyStreamCount](https://www.mystreamcount.com).

---

## How It Works

Two songs are shown side by side. The left card reveals its stream count; the right card hides it. You guess **Higher** or **Lower**. If you're right, the right card becomes the new baseline and a new mystery song appears. Get it wrong and your streak resets — but you can submit your score to the leaderboard first.

Anyone can recommend new tracks to the catalog through the in-game form. Paste a Spotify track URI and the backend fetches the live stream count immediately.

---

## Project Structure

```
higher-lower-game/
├── main.py                       # FastAPI backend — game endpoints, scraper, leaderboard
├── index.html                    # Frontend — game UI, recommendation form, leaderboard
├── pipeline/
│   ├── migrate_and_seed.py       # Copies songs from music_v2.db into game.db
│   ├── scrape_streams_safely.py  # Safely scrapes missing Spotify stream counts
│   ├── seed_spotify_complete.py  # Builds a clean SQLite database of complete artist discographies
│   ├── audit.py                  # Checks DB health — missing URIs, zero counts, etc.
│   └── verify.py                 # Spot-checks scraped stream counts against live site
├── reset_to_baseline.py          # Resets game.db to the committed baseline snapshot
├── game_baseline.db              # Clean committed snapshot used by reset script
└── .gitignore
```

---

## Tech Stack

- **Backend:** FastAPI, Uvicorn
- **Scraping:** httpx, BeautifulSoup4
- **Database:** SQLite
- **Frontend:** HTML / CSS / Vanilla JavaScript
- **Data sources:** Spotify Web API (URIs), MyStreamCount (live stream counts)

---

## Getting Started

### 1. Install dependencies

```bash
pip install fastapi uvicorn httpx beautifulsoup4 requests
```

### 2. Set up the database

If you're starting fresh from the baseline snapshot:

```bash
python reset_to_baseline.py
```

Or if you're migrating from an existing `music_v2.db`:

```bash
python pipeline/migrate_and_seed.py
```

### 3. Populate Spotify URIs

Open `pipeline/populate_spotify_uris.py` and paste your Spotify API credentials at the top (get them free at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)):

```python
SPOTIFY_CLIENT_ID     = "your_client_id"
SPOTIFY_CLIENT_SECRET = "your_client_secret"
```

Then run it:

```bash
python pipeline/populate_spotify_uris.py
```

This looks up every song in the catalog and saves its Spotify track ID to the database. Songs with a URI will have their stream counts updated by the hourly scraper.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/game/pair` | Returns two random songs for a round |
| `POST` | `/api/game/recommend` | Adds a new track to the catalog |
| `GET` | `/api/game/leaderboard` | Returns the top 10 all-time streaks |
| `POST` | `/api/game/leaderboard` | Submits a score `{ username, high_score }` |
| `GET` | `/api/search?q={query}` | Searches the catalog by title, artist, or submitter |

