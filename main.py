from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from datetime import datetime
import torch
import torch.nn as nn
import os

app = FastAPI()

# Enable CORS so HTML frontend can communicate with the backend seamlessly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "music_v2.db"
MODEL_PATH = "model.pth"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

class NeuralCollaborativeFiltering(nn.Module):
    def __init__(self, num_users, num_songs, embedding_dim=16):
        super().__init__()
        self.user_embedding = nn.Embedding(num_users + 1, embedding_dim)
        self.song_embedding = nn.Embedding(num_songs + 1, embedding_dim)
        
        self.fc_layers = nn.Sequential(
            nn.Linear(embedding_dim * 2, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )
        
    def forward(self, user_id, song_id):
        user_vec = self.user_embedding(user_id)
        song_vec = self.song_embedding(song_id)
        x = torch.cat([user_vec, song_vec], dim=-1)
        return self.fc_layers(x).squeeze(-1)

class ListenRequest(BaseModel):
    user_id: int
    song_id: int

# --- API ENDPOINTS ---

@app.get("/api/search")
def search_songs(q: str = ""):
    if not q:
        return []
    conn = get_db()
    cursor = conn.cursor()
    # Case-insensitive partial matching across track names and artists
    query = "SELECT * FROM songs WHERE title LIKE ? OR artist LIKE ? LIMIT 2000"
    cursor.execute(query, (f"%{q}%", f"%{q}%"))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

# 2. Track Interaction: Persistently appends a listen event row to your hard drive database
@app.post("/api/listen")
def log_listen_event(req: ListenRequest):
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify song exists in our library first
    cursor.execute("SELECT id FROM songs WHERE id = ?", (req.song_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Song ID not found in library")
        
    cursor.execute(
        "INSERT INTO listening_history (user_id, song_id, timestamp) VALUES (?, ?, ?)",
        (req.user_id, req.song_id, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Interaction logged directly to disk database."}

# 3. Deep Learning Recommendation Pipeline
@app.get("/api/recommendations/{user_id}")
def get_recommendations(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    
    # Establish matrix sizing constraints dynamically based on your physical database metrics
    cursor.execute("SELECT MAX(user_id) FROM listening_history")
    max_user = max(cursor.fetchone()[0] or 100, user_id)
    cursor.execute("SELECT MAX(id) FROM songs")
    max_song = cursor.fetchone()[0] or 2000
    
    model = NeuralCollaborativeFiltering(num_users=max_user, num_songs=max_song)
    
    model_loaded = False
    if os.path.exists(MODEL_PATH):
        try:
            # Map the trained weight arrays to our current layer structure
            model.load_state_dict(torch.load(MODEL_PATH))
            model.eval()  # Freeze layers into evaluation/inference mode
            model_loaded = True
        except Exception as e:
            print(f"Could not load model.pth weight layers: {e}")
            
    # Extract songs this specific user has already listened to so we don't repeat them
    cursor.execute("SELECT song_id FROM listening_history WHERE user_id = ?", (user_id,))
    heard_ids = [row['song_id'] for row in cursor.fetchall()]
    
    # Pull candidate targets from the global track vector
    cursor.execute("SELECT * FROM songs")
    all_songs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    unheard_songs = [s for s in all_songs if s['id'] not in heard_ids]
    if not unheard_songs:
        return {"recs": [], "engine": "Database Complete"}

    # Run predictions through the network if model.pth was found
    if model_loaded:
        with torch.no_grad():
            for song in unheard_songs:
                # Format indices into long integer tensors for lookups
                user_tensor = torch.tensor([user_id], dtype=torch.long)
                song_tensor = torch.tensor([song['id']], dtype=torch.long)
                
                # Execute matrix dot-product layer equations
                prediction_score = model(user_tensor, song_tensor).item()
                song['predicted_score'] = round(prediction_score * 100, 1)  # Represent as % Match
        engine_label = "Live PyTorch Neural Collaborative Filtering"
    else:
        # Fallback baseline profile if model.pth hasn't been generated yet by train.py
        for song in unheard_songs:
            song['predicted_score'] = round(float(song['popularity'] if 'popularity' in song else 50.0), 1)
        engine_label = "Fallback Baseline (Spotify Popularity Weights)"

    # Sort tracks based on highest computed affinity values
    recommended_songs = sorted(unheard_songs, key=lambda x: x['predicted_score'], reverse=True)
    
    return {
        "recs": recommended_songs[:5],  # Serve the top 5 custom matches
        "engine": engine_label
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)