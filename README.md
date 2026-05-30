# 🎵 Music Recommender

A full-stack music recommendation system powered by **Neural Collaborative Filtering (NCF)**. Users can search for songs, log listening history, and receive personalized song recommendations — all served through a FastAPI backend and a plain HTML/JS frontend.

---

## How It Works

The system learns from user listening history stored in a local SQLite database. A PyTorch neural network maps users and songs into embedding vectors, concatenates them, and passes them through fully connected layers to predict a preference score between 0 and 1. At inference time, the top 5 unheard songs with the highest predicted scores are returned.

If the model hasn't been trained yet, the API falls back to ranking songs by their Spotify popularity score.

---

## Project Structure

```
music-recommender/
├── main.py                   # FastAPI backend — search, listen logging, recommendations
├── train.py                  # PyTorch training script — produces model.pth
├── seed_spotify_complete.py  # Seeds the SQLite database with Spotify track data
├── index.html                # Frontend UI (search, log listens, view recommendations)
├── music_v2.db               # SQLite database (generated at runtime)
└── model.pth                 # Saved model weights (generated after training)
```

---

## Tech Stack

- **Backend:** FastAPI, Uvicorn
- **ML:** PyTorch (Neural Collaborative Filtering)
- **Database:** SQLite
- **Frontend:** HTML / JavaScript
- **Data Source:** Spotify API (via seeding script)

---

## Getting Started

### 1. Install dependencies

```bash
pip install fastapi uvicorn torch pydantic spotipy
```

### 2. Seed the database

Populate the local SQLite database with song data from Spotify:

```bash
python seed_spotify_complete.py
```

### 3. Train the model

Train the NCF model on listening history. This generates `model.pth`:

```bash
python train.py
```

> **Note:** You need some listening history in the database before training is meaningful. Log a few listens via the API or frontend first.

### 4. Start the API server

```bash
python main.py
```

The server runs at `http://127.0.0.1:8000`.

### 5. Open the frontend

Open `index.html` in your browser. Make sure the backend is running first.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/search?q={query}` | Search songs by title or artist |
| `POST` | `/api/listen` | Log a listen event `{ user_id, song_id }` |
| `GET` | `/api/recommendations/{user_id}` | Get top 5 personalized recommendations |

### Example: Log a listen

```bash
curl -X POST http://127.0.0.1:8000/api/listen \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "song_id": 42}'
```

### Example: Get recommendations

```bash
curl http://127.0.0.1:8000/api/recommendations/1
```

Response includes a `recs` array and an `engine` field indicating whether the live PyTorch model or the popularity-based fallback was used.

---

## Model Architecture

The `NeuralCollaborativeFiltering` model consists of:

- **User Embedding** — maps user IDs to 16-dimensional vectors
- **Song Embedding** — maps song IDs to 16-dimensional vectors
- **Fully Connected Layers** — `32 → ReLU → 16 → ReLU → 1 → Sigmoid`

Training uses **Binary Cross Entropy loss** and the **Adam optimizer** over 10 epochs with a batch size of 64.

---

## Notes

- User IDs are arbitrary integers — just pick a consistent ID per user session.
- The database and model file are excluded from version control via `.gitignore`.
- Re-run `train.py` any time to retrain on updated listening history.
