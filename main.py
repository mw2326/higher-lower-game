import os
import re
import psycopg2
from psycopg2.extras import RealDictCursor  # Gives us rows as dictionaries natively
from psycopg2.pool import ThreadedConnectionPool  # Active pool engine
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

# Grabs our secure session pooler link from your Render Environment Variables
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL environment variable is missing from your environment dashboard!")

# 🎯 INITIALIZE GLOBAL POOL: Creates and holds open a reusable bundle of authenticated sockets
try:
    db_pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)
    print("✅ Permanent database connection pool established successfully.")
except Exception as pool_err:
    print(f"❌ Failed to initialize database connection pool: {pool_err}")
    raise pool_err


# ---------------------------------------------------------------------- #
# App lifecycle                                                          #
# ---------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    # App initialization confirmation
    print("🚀 Cloud backend engine running flawlessly on Render.")
    yield
    # Clean up and disconnect all sockets when the server spins down or restarts
    db_pool.closeall()
    print("🛑 Database connection pool closed down gracefully.")


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
    
    # 🏎️ Borrow an open, hot socket from our pool instantly
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT * FROM songs WHERE title ILIKE %s OR artist ILIKE %s OR recommended_by ILIKE %s LIMIT 100",
            (f"%{q}%", f"%{q}%", f"%{q}%"),
        )
        results = cursor.fetchall()
        return results
    finally:
        # 🎯 CRUCIAL: Return the connection to the pool so other players can use it
        db_pool.putconn(conn)


@app.get("/api/game/pair")
def get_game_pair():
    """Return two distinct random songs from your Supabase cloud data columns."""
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT id, title, artist, genre, spotify_uri, stream_count, image_url 
            FROM songs 
            ORDER BY RANDOM() LIMIT 2
        """)
        rows = cursor.fetchall()

        if len(rows) < 2:
            raise HTTPException(
                status_code=400,
                detail="Not enough songs in your Supabase catalog yet! Run your migration script or click insert row.",
            )
        return {
            "song_a": {
                "id": rows[0]["id"],
                "title": rows[0]["title"],
                "artist": rows[0]["artist"],
                "genre": rows[0]["genre"],
                "spotify_uri": rows[0]["spotify_uri"],
                "stream_count": rows[0]["stream_count"],
                "image_url": rows[0]["image_url"]
            },
            "song_b": {
                "id": rows[1]["id"],
                "title": rows[1]["title"],
                "artist": rows[1]["artist"],
                "genre": rows[1]["genre"],
                "spotify_uri": rows[1]["spotify_uri"],
                "stream_count": rows[1]["stream_count"],
                "image_url": rows[1]["image_url"]
            }
        }
    finally:
        db_pool.putconn(conn)


@app.post("/api/game/leaderboard")
def log_high_score(req: ScoreSubmissionRequest):
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "INSERT INTO leaderboard (username, high_score, achieved_at) VALUES (%s, %s, %s)",
            (req.username.strip(), req.high_score, datetime.now().isoformat()),
        )
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit score: {e}")
    finally:
        db_pool.putconn(conn)


@app.get("/api/game/leaderboard")
def get_leaderboard():
    conn = db_pool.getconn()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(
            "SELECT username, high_score, achieved_at FROM leaderboard ORDER BY high_score DESC LIMIT 5"
        )
        top_scores = cursor.fetchall()
        return top_scores
    finally:
        db_pool.putconn(conn)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)