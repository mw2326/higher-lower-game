import os
import re
import sqlite3
import asyncio
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

DB_FILE = "game.db"
MSC_BASE = "https://www.mystreamcount.com/track/"

# ---------------------------------------------------------------------- #
# Database helpers                                                         #
# ---------------------------------------------------------------------- #

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_structures():
    """
    Create tables on first boot and migrate any missing columns on existing DBs.
    This handles the case where game.db was created before spotify_uri was added.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT    NOT NULL,
            artist           TEXT    NOT NULL,
            genre            TEXT    DEFAULT 'K-Pop',
            spotify_uri      TEXT    DEFAULT '',
            stream_count     INTEGER DEFAULT 0,
            recommended_by   TEXT    DEFAULT 'System Core',
            notes            TEXT    DEFAULT '',
            last_updated     TEXT    NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    NOT NULL,
            high_score   INTEGER NOT NULL,
            achieved_at  TEXT    NOT NULL
        )
    """)

    # ── Schema migrations ──────────────────────────────────────────────────
    # Safely add any columns that may be missing from an older game.db on disk.
    # We check existing columns first so this is safe to run on every startup.
    cursor.execute("PRAGMA table_info(songs)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    migrations = [
        ("spotify_uri",    "TEXT    DEFAULT ''"),
        ("recommended_by", "TEXT    DEFAULT 'System Core'"),
        ("notes",          "TEXT    DEFAULT ''"),
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE songs ADD COLUMN {col_name} {col_def}")
            print(f"   ↳ Migrated: added column '{col_name}' to songs table.")

    conn.commit()
    conn.close()
    print("🎯 SQLite game tables verified and ready.")


# ---------------------------------------------------------------------- #
# Stream scraper                                                           #
# ---------------------------------------------------------------------- #

async def fetch_stream_count(spotify_uri: str, client: httpx.AsyncClient):
    """
    Scrape the live stream count for a track from mystreamcount.com.

    URL pattern: https://www.mystreamcount.com/track/{spotify_uri}
    The count is rendered server-side, so a plain GET is enough.
    """
    if not spotify_uri:
        return None

    url = f"{MSC_BASE}{spotify_uri}"
    try:
        response = await client.get(url, timeout=15)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        print(f"   ⚠️  HTTP error fetching {url}: {exc}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # The stream count appears as plain text — a large integer with comma separators.
    # We scan all text nodes for something that looks like a stream count (7+ digits).
    for tag in soup.find_all(string=True):
        text = tag.strip().replace(",", "")
        if text.isdigit() and len(text) >= 7:
            return int(text)

    # Fallback: regex sweep over raw page text
    match = re.search(r"([\d]{1,3}(?:,[\d]{3})+)\s*streams", response.text, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))

    return None


# ---------------------------------------------------------------------- #
# Hourly background updater                                                #
# ---------------------------------------------------------------------- #

async def hourly_stream_updater():
    """
    Every hour, fetch real stream counts from mystreamcount.com for every
    song in the catalog that has a spotify_uri set.
    Songs without a URI are skipped (their counts stay as seeded).
    """
    await asyncio.sleep(5)  # Let the app finish starting up first

    while True:
        print(f"\n⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting hourly stream refresh...")

        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, artist, spotify_uri FROM songs WHERE spotify_uri != ''")
            songs = cursor.fetchall()
            conn.close()

            if not songs:
                print("   ⚠️  No songs with a spotify_uri found — nothing to scrape.")
            else:
                async with httpx.AsyncClient(
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                    },
                    follow_redirects=True,
                ) as client:
                    updated = 0
                    for song in songs:
                        count = await fetch_stream_count(song["spotify_uri"], client)
                        if count is not None:
                            conn = get_db()
                            conn.execute(
                                "UPDATE songs SET stream_count = ?, last_updated = ? WHERE id = ?",
                                (count, datetime.utcnow().isoformat(), song["id"]),
                            )
                            conn.commit()
                            conn.close()
                            updated += 1
                            print(f"   ✅ {song['artist']} — {song['title']}: {count:,}")
                        else:
                            print(f"   ❌ Could not fetch: {song['title']} (uri={song['spotify_uri']})")

                        await asyncio.sleep(2)  # Be polite — don't hammer the site

                print(f"   🏁 Refresh complete. Updated {updated}/{len(songs)} tracks.")

        except Exception as err:
            print(f"   ❌ Hourly updater error: {err}")

        await asyncio.sleep(3600)


# ---------------------------------------------------------------------- #
# App lifecycle                                                             #
# ---------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_structures()
    updater_task = asyncio.create_task(hourly_stream_updater())
    yield
    updater_task.cancel()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------- #
# Pydantic models                                                          #
# ---------------------------------------------------------------------- #

class TrackRecommendationRequest(BaseModel):
    title: str
    artist: str
    genre: str = "K-Pop"
    spotify_uri: str = ""   # e.g. "1d7Ptw3qYcfpdLNL5REhtJ"
    stream_count: int = 0   # fallback if no URI; scraper will update if URI given
    recommended_by: str
    notes: str = ""


class ScoreSubmissionRequest(BaseModel):
    username: str
    high_score: int


# ---------------------------------------------------------------------- #
# Endpoints                                                                #
# ---------------------------------------------------------------------- #

@app.get("/")
def read_root():
    return FileResponse("index.html")


@app.get("/api/search")
def search_catalog(q: str = ""):
    if not q:
        return []
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM songs WHERE title LIKE ? OR artist LIKE ? OR recommended_by LIKE ? LIMIT 100",
        (f"%{q}%", f"%{q}%", f"%{q}%"),
    )
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


@app.get("/api/game/pair")
def get_game_pair():
    """Return two distinct random songs for a Higher-or-Lower round."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, artist, genre, spotify_uri, stream_count, recommended_by, notes "
        "FROM songs ORDER BY RANDOM() LIMIT 2"
    )
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough songs in the catalog yet. Add at least 2 tracks via the recommendation form!",
        )

    return {"song_a": dict(rows[0]), "song_b": dict(rows[1])}


@app.post("/api/game/recommend")
async def recommend_new_track(req: TrackRecommendationRequest):
    """
    Add a community-submitted track to the catalog.
    If a spotify_uri is provided, immediately fetch the live stream count.
    """
    print(f"\n📥 New recommendation from: {req.recommended_by}")

    initial_count = max(0, req.stream_count)
    if req.spotify_uri.strip():
        async with httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
            follow_redirects=True,
        ) as client:
            live_count = await fetch_stream_count(req.spotify_uri.strip(), client)
            if live_count is not None:
                initial_count = live_count
                print(f"   🎧 Live count fetched: {live_count:,}")
            else:
                print("   ⚠️  Could not fetch live count; using submitted value.")

    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO songs
                (title, artist, genre, spotify_uri, stream_count,
                 recommended_by, notes, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.title.strip(),
                req.artist.strip(),
                req.genre.strip(),
                req.spotify_uri.strip(),
                initial_count,
                req.recommended_by.strip() or "Anonymous",
                req.notes.strip(),
                datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
        print(f"   ✅ Track added with ID {new_id}")
        return {"status": "success", "id": new_id, "stream_count": initial_count}
    except Exception as db_err:
        raise HTTPException(status_code=500, detail=f"Database error: {db_err}")
    finally:
        conn.close()


@app.post("/api/game/leaderboard")
def log_high_score(req: ScoreSubmissionRequest):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO leaderboard (username, high_score, achieved_at) VALUES (?, ?, ?)",
            (req.username.strip(), req.high_score, datetime.now().isoformat()),
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit score: {e}")
    finally:
        conn.close()


@app.get("/api/game/leaderboard")
def get_leaderboard():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, high_score, achieved_at FROM leaderboard ORDER BY high_score DESC LIMIT 10"
    )
    top_scores = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return top_scores


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)