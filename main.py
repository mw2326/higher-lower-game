import os
import re
import psycopg2  # Swapped sqlite3 for psycopg2
from psycopg2.extras import RealDictCursor  # This gives us rows as dictionaries natively
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Grabs our secure session pooler link from your Render Environment Variables
DATABASE_URL = os.environ.get("DATABASE_URL")

# ---------------------------------------------------------------------- #
# Database helpers                                                       #
# ---------------------------------------------------------------------- #

def get_db():
    # Connect directly to your live Supabase cloud engine
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


# NOTE: We removed the old init_db_structures() function because SQLite functions 
# like 'PRAGMA table_info' crash instantly on PostgreSQL. 
# Your table structure is now beautifully managed visually inside the Supabase dashboard!

# ---------------------------------------------------------------------- #
# App lifecycle                                                          #
# ---------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    # App initialization check
    print("🚀 Cloud database engine connected cleanly to Supabase session pooler.")
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
@app.head("/")
def read_root():
    return FileResponse("index.html")

@app.get("/style.css")
def read_css():
    return FileResponse("style.css")

@app.get("/app.js")
def read_js():
    return FileResponse("app.js")


@app.get("/api/search")
def search_catalog(q: str = ""):
    if not q:
        return []
    conn = get_db()
    cursor = conn.cursor()
    # 1. Swapped '?' for '%s' 
    # 2. Changed 'LIKE' to 'ILIKE' for superior case-insensitive cloud searching
    cursor.execute(
        "SELECT * FROM songs WHERE title ILIKE %s OR artist ILIKE %s OR recommended_by ILIKE %s LIMIT 100",
        (f"%{q}%", f"%{q}%", f"%{q}%"),
    )
    results = cursor.fetchall()  # RealDictCursor handles dictionaries automatically
    conn.close()
    return results


@app.get("/api/game/pair")
def get_game_pair():
    """Return two distinct random songs from your Supabase cloud data columns."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, artist, genre, spotify_uri, stream_count, image_url 
        FROM songs 
        ORDER BY RANDOM() LIMIT 2
    """)
    rows = cursor.fetchall()
    conn.close()

    if len(rows) < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough songs in your Supabase catalog yet! Run your migration script or click insert row.",
        )
    return {
        "song_a": {
            "id": rows[0][0],
            "title": rows[0][1],
            "artist": rows[0][2],
            "genre": rows[0][3],
            "spotify_uri": rows[0][4],
            "stream_count": rows[0][5],
            "image_url": rows[0][6]
        },
        "song_b": {
            "id": rows[1][0],
            "title": rows[1][1],
            "artist": rows[1][2],
            "genre": rows[1][3],
            "spotify_uri": rows[1][4],
            "stream_count": rows[1][5],
            "image_url": rows[1][6]
        }
    }


#@app.post("/api/game/recommend")
#async def recommend_new_track(req: TrackRecommendationRequest):
#    """Inserts community additions natively into Supabase using user-submitted metrics."""
#    print(f"\n📥 New cloud recommendation from: {req.recommended_by}")
#    initial_count = max(0, req.stream_count)
#
#    conn = get_db()
#    try:
#        cursor = conn.cursor()
#        # Swapped '?' for '%s' and added 'RETURNING id' since Postgres doesn't use lastrowid
#        cursor.execute(
#            """
#            INSERT INTO songs
#                (title, artist, genre, spotify_uri, stream_count,
#                 recommended_by, notes, last_updated)
#            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
#            """,
#            (
#                req.title.strip(),
#                req.artist.strip(),
#                req.genre.strip(),
#                req.spotify_uri.strip(),
#                initial_count,
#                req.recommended_by.strip() or "Anonymous",
#                req.notes.strip(),
#                datetime.utcnow().isoformat(),
#            ),
#        )
#        new_id = cursor.fetchone()["id"]
#        conn.commit()
#        return {"status": "success", "id": new_id, "stream_count": initial_count}
#    except Exception as db_err:
#        raise HTTPException(status_code=500, detail=f"Database error: {db_err}")
#    finally:
#        conn.close()


@app.post("/api/game/leaderboard")
def log_high_score(req: ScoreSubmissionRequest):
    conn = get_db()
    try:
        cursor = conn.cursor()
        # Swapped '?' for '%s'
        cursor.execute(
            "INSERT INTO leaderboard (username, high_score, achieved_at) VALUES (%s, %s, %s)",
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
        "SELECT username, high_score, achieved_at FROM leaderboard ORDER BY high_score DESC LIMIT 5"
    )
    top_scores = cursor.fetchall()
    conn.close()
    return top_scores


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)