import os
import re
import sqlite3
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

DB_FILE = "game.db"

# ---------------------------------------------------------------------- #
# Database helpers                                                       #
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

    # ── PERMANENT ARTIST VS POET PURGE GATES ──────────────────────────────
    fake_ive_tracks = [
        'Fresh', 'Medicine', 'Break Away', 'Sincerely Me', "Leavin'", 'Kids Again',
        'Somewhere Else', 'Everything Must Go', 'Break Away (Piano Version)', 
        'Leaving in the Morning (feat. Blackbear)', 'Stay', 'Wait for You', 
        'Anything at All', 'The Remedy', 'Different People (feat. Devyn De Loera)', 
        'Whiskey Problems', 'Let You Go', 'Remember This', 'The Best That You Can Be', 
        "Leavin' in the Morning", 'Different People', 'Car Crash', 'Favorite Fix', 
        'Unconscious Reality', 'Damn Rough Night', "We're All The Same", 
        'So Much I Never Said', 'Miserably Loving You', 'Broke But Not Broken', 
        "He's Just Not Me", 'Alive', 'Giving Yourself Away', 'Break', 'Hang Around', 
        "Where I'm Gonna Be", 'Dreaming My Way to You', 'Rescue', 'To Hell With The Letdown', 
        'Assurance Closure', 'Lisa Marie', 'Infallible Remedy', 'All In'
    ]
    
    cursor.execute("""
        DELETE FROM songs 
        WHERE artist = 'IVE' AND title IN ({})
    """.format(','.join('?' for _ in fake_ive_tracks)), fake_ive_tracks)
    
    if cursor.rowcount > 0:
        print(f"🧹 Startup Shield: Instantly neutralized {cursor.rowcount} corrupted rock tracks from the IVE pool.")
        conn.commit()
    # ──────────────────────────────────────────────────────────────────────

    # ── Schema migrations ──────────────────────────────────────────────────
    cursor.execute("PRAGMA table_info(songs)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    migrations = [
        ("spotify_uri",    "TEXT    DEFAULT ''"),
        ("recommended_by", "TEXT    DEFAULT 'System Core'"),
        ("notes",          "TEXT    DEFAULT ''"),
        ("last_updated",   "TEXT    DEFAULT '2026-05-31T00:00:00'")
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE songs ADD COLUMN {col_name} {col_def}")
            print(f"   ↳ Migrated: added column '{col_name}' to songs table.")

    conn.commit()
    conn.close()
    print("🎯 SQLite game tables verified and ready.")


# ---------------------------------------------------------------------- #
# App lifecycle                                                          #
# ---------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup database on boot, completely omitting any background scrape loops
    init_db_structures()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------- #
# Pydantic models                                                        #
# ---------------------------------------------------------------------- #

class TrackRecommendationRequest(BaseModel):
    title: str
    artist: str
    genre: str = "K-Pop"
    spotify_uri: str = ""
    stream_count: int = 0
    recommended_by: str
    notes: str = ""


class ScoreSubmissionRequest(BaseModel):
    username: str
    high_score: int


# ---------------------------------------------------------------------- #
# Endpoints                                                              #
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
    """Return two distinct random songs with their 'last_updated' timestamp."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, artist, genre, spotify_uri, stream_count, recommended_by, notes, last_updated "
        "FROM songs ORDER BY RANDOM() LIMIT 2"
    )
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough songs in the catalog yet.",
        )

    return {"song_a": dict(rows[0]), "song_b": dict(rows[1])}


@app.post("/api/game/recommend")
async def recommend_new_track(req: TrackRecommendationRequest):
    """Inserts community additions natively using user-submitted metrics."""
    print(f"\n📥 New recommendation from: {req.recommended_by}")
    initial_count = max(0, req.stream_count)

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
        return {"status": "success", "id": cursor.lastrowid, "stream_count": initial_count}
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
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)