from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from datetime import datetime
import torch
import torch.nn as nn
import os
from fastapi.responses import FileResponse
import torch.optim as optim

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

# Exact structural matrices matched to your trained model checkpoint configuration
MAX_USERS_LIMIT = 101
MAX_SONGS_LIMIT = 2146

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

@app.get("/")
def read_root():
    return FileResponse("index.html")

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

# 2. Track Interaction: Persistently appends a listen event row to your database and fine-tunes live
@app.post("/api/listen")
def log_listen_event(req: ListenRequest):
    print(f"\n⚡ Incoming listen event: User {req.user_id} listened to Song {req.song_id}")
    
    # 1. Log the interaction to SQLite instantly
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO listening_history (user_id, song_id, timestamp) VALUES (?, ?, ?)",
            (req.user_id, req.song_id, datetime.utcnow().isoformat())
        )
        conn.commit()
        print("   ✅ Logged to SQLite database.")
        
        # Pull 2 random song IDs to use as negative samples for contrastive learning
        cursor.execute("SELECT id FROM songs WHERE id != ? ORDER BY RANDOM() LIMIT 2", (req.song_id,))
        negative_song_ids = [row[0] for row in cursor.fetchall()]
    except Exception as db_err:
        conn.close()
        print(f"   ❌ SQLite Logging Error: {db_err}")
        raise HTTPException(status_code=500, detail="Database logging failed.")
    conn.close()

    # 2. Live Online Contrastive Fine-Tuning Step
    if not os.path.exists(MODEL_PATH):
        print("   ⚠️ Model file missing. Skipping online adaptation step.")
        return {"status": "success"}

    try:
        model = NeuralCollaborativeFiltering(num_users=MAX_USERS_LIMIT, num_songs=MAX_SONGS_LIMIT)
        model.load_state_dict(torch.load(MODEL_PATH))
        model.train()

        criterion = nn.BCELoss()
        # SAFE MODIFICATION: Dropped LR from 0.1 to 0.005 for gentle optimization updates
        optimizer = optim.Adam(model.parameters(), lr=0.02) 

        # BUILD A CONTRASTIVE MINI-BATCH:
        # Index 0: The clicked song (Positive Target = 1.0)
        # Index 1 & 2: Random songs the user didn't click right now (Negative Target = 0.0)
        user_ids = [req.user_id, req.user_id, req.user_id]
        song_ids = [req.song_id] + negative_song_ids
        labels = [1.0, 0.0, 0.0]

        user_tensor = torch.tensor(user_ids, dtype=torch.long)
        song_tensor = torch.tensor(song_ids, dtype=torch.long)
        target_label = torch.tensor(labels, dtype=torch.float32)

        # Grab predictions prior to backprop step for visual tracking
        with torch.no_grad():
            old_pred = model(torch.tensor([req.user_id]), torch.tensor([req.song_id])).item()

        # SAFE MODIFICATION: Run EXACTLY ONE single backpropagation step per interaction
        optimizer.zero_grad()
        prediction = model(user_tensor, song_tensor)
        loss = criterion(prediction.view_as(target_label), target_label)
        loss.backward()
        optimizer.step()

        # Grab predictions post-backprop step to verify training mechanics shifted
        with torch.no_grad():
            new_pred = model(torch.tensor([req.user_id]), torch.tensor([req.song_id])).item()

        torch.save(model.state_dict(), MODEL_PATH)
        
        print(f"   🔥 PyTorch Live-Tuned with Contrastive Sampling!")
        print(f"      - Clicked Track Affinity: {old_pred:.2%} ──> {new_pred:.2%}")
        print(f"      - Embedding space coordinates updated successfully.")

    except Exception as ai_err:
        print(f"   ❌ PyTorch Fine-Tuning Failed: {ai_err}")
        import traceback
        traceback.print_exc()

    return {"status": "success"}

# 3. Deep Learning Recommendation Pipeline
@app.get("/api/recommendations/{user_id}")
def get_recommendations(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    
    # STRUCTURAL UNIFICATION: Use the exact same global limits to prevent matrix shape errors
    model = NeuralCollaborativeFiltering(num_users=MAX_USERS_LIMIT, num_songs=MAX_SONGS_LIMIT)
    
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