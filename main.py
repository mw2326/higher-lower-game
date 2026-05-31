import os
import sqlite3
import random
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

DB_FILE = "game.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db_structures():
    """Validates and sets up the clean relational game catalog tables on boot."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Core game song catalog carrying streaming indices
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            genre TEXT DEFAULT 'K-Pop',
            stream_count INTEGER DEFAULT 0,
            recommended_by TEXT DEFAULT 'System Core',
            notes TEXT DEFAULT '',
            last_updated TEXT NOT NULL
        )
    """)
    
    # Leaderboard row state for persistent player streak records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            high_score INTEGER NOT NULL,
            achieved_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("🎯 SQLite Game Tables verified and ready.")

# --- Automated 1-Hour Async Background Task Loop ---
async def hourly_stream_updater():
    """
    Runs an continuous background worker task that increments stream counters 
    every hour to mimic the live data tracking mechanics seen on platforms like MyStreamCount.
    """
    # Wait 5 seconds on startup to allow baseline data initialization loops to clear
    await asyncio.sleep(5)
    
    while True:
        try:
            print(f"\n⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Launching hourly stream refresh cycle...")
            conn = get_db()
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, title, artist, stream_count FROM songs")
            songs = cursor.fetchall()
            
            if songs:
                updated_count = 0
                for song in songs:
                    # Simulate organic stream count velocity changes over an hour span
                    hourly_growth = random.randint(2500, 45000)
                    cursor.execute("""
                        UPDATE songs 
                        SET stream_count = stream_count + ?, last_updated = ? 
                        WHERE id = ?
                    """, (hourly_growth, datetime.utcnow().isoformat(), song['id']))
                    updated_count += 1
                
                conn.commit()
                print(f"   ✅ Real-Time Sync Complete. Cached streaming logs updated for {updated_count} tracks.")
            else:
                print("   ⚠️ Database current track listing is empty. Awaiting user recommendations...")
            
            conn.close()
        except Exception as err:
            print(f"   ❌ Automated Background Sync Task encountered an error: {err}")
            
        # Suspend thread operation for exactly 1 hour (3600 seconds)
        await asyncio.sleep(3600)

# Lifespan manager to tie asynchronous task scheduling safely to the app lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_structures()
    # Schedule the loop task asynchronously in the background
    updater_task = asyncio.create_task(hourly_stream_updater())
    yield
    # Safely terminate the thread background process when closing the application
    updater_task.cancel()

app = FastAPI(lifespan=lifespan)

# Enable CORS so your index.html can seamlessly query the endpoints locally
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Request Validation Models (Pydantic) ---
class TrackRecommendationRequest(BaseModel):
    title: str
    artist: str
    genre: str = "K-Pop"
    stream_count: int
    recommended_by: str
    notes: str = ""

class ScoreSubmissionRequest(BaseModel):
    username: str
    high_score: int

# --- API ENDPOINTS ---

@app.get("/")
def read_root():
    return FileResponse("index.html")

@app.get("/api/search")
def search_catalog(q: str = ""):
    if not q:
        return []
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM songs WHERE title LIKE ? OR artist LIKE ? OR recommended_by LIKE ? LIMIT 100"
    cursor.execute(query, (f"%{q}%", f"%{q}%", f"%{q}%"))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

# 1. Game Vector: Fetches a random pair of distinct songs for the Higher or Lower loop
@app.get("/api/game/pair")
def get_game_pair():
    conn = get_db()
    cursor = conn.cursor()
    
    # Grab two items completely random from your song pool
    cursor.execute("SELECT id, title, artist, genre, stream_count, recommended_by, notes FROM songs ORDER BY RANDOM() LIMIT 2")
    rows = cursor.fetchall()
    conn.close()
    
    if len(rows) < 2:
        raise HTTPException(
            status_code=400, 
            detail="Insufficient song data pool size. Please add a few track recommendations first!"
        )
        
    return {
        "song_a": dict(rows[0]),
        "song_b": dict(rows[1])
    }

# 2. Endorsement Handler: Allows custom community submissions tracking "those who recommend it"
@app.post("/api/game/recommend")
def recommend_new_track(req: TrackRecommendationRequest):
    print(f"\n📥 Processing incoming recommendation submission from: {req.recommended_by}")
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO songs (title, artist, genre, stream_count, recommended_by, notes, last_updated) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            req.title.strip(), 
            req.artist.strip(), 
            req.genre.strip(), 
            max(0, req.stream_count), 
            req.recommended_by.strip() if req.recommended_by.strip() else "Anonymous Contributor",
            req.notes.strip(),
            datetime.utcnow().isoformat()
        ))
        conn.commit()
        new_id = cursor.lastrowid
        print(f"   ✅ Track ingestion successful! Registered ID -> {new_id}")
        conn.close()
        return {"status": "success", "id": new_id, "message": f"Successfully ingested recommendation from {req.recommended_by}"}
    except Exception as db_err:
        conn.close()
        print(f"   ❌ Ingestion Error: {db_err}")
        raise HTTPException(status_code=500, detail="Failed to parse and store track recommendation entry.")

# 3. Leaderboard Vector: Stores player high score streaks 
@app.post("/api/game/leaderboard")
def log_high_score(req: ScoreSubmissionRequest):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO leaderboard (username, high_score, achieved_at) 
            VALUES (?, ?, ?)
        """, (req.username.strip(), req.high_score, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Failed to submit score: {e}")

@app.get("/api/game/leaderboard")
def get_leaderboard():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, high_score, achieved_at FROM leaderboard ORDER BY high_score DESC LIMIT 10")
    top_scores = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return top_scores

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)