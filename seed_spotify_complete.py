import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import sqlite3
import random
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

auth_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(auth_manager=auth_manager)

# The target group list to extract absolute histories for
KPOP_ARTISTS = [
    "NewJeans", "BTS", "aespa", "Stray Kids", "TWICE", "BLACKPINK", 
    "SEVENTEEN", "IVE", "LE SSERAFIM", "ENHYPEN", "TOMORROW X TOGETHER", "Red Velvet", "NMIXX"
]

DB_FILE = "music_v2.db"

def rebuild_clean_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS songs")
    cursor.execute("DROP TABLE IF EXISTS listening_history")
    
    cursor.execute('''
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            genre TEXT NOT NULL,
            popularity INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE listening_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            song_id INTEGER NOT NULL,
            rating REAL DEFAULT 1.0,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def pull_absolute_discographies():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    print("🚀 Connecting to Spotify API for Complete Discography Sweep...")
    total_tracks_inserted = 0
    
    # Direct dictionary mapping to guarantee exact alphanumeric IDs for problematic artists
    # FIX: Corrected case-sensitive alphanumeric Spotify IDs
    ARTIST_ID_OVERRIDES = {
        "BTS": "3Nrfpe0tUJi4K4DXYWgMUX",
        "AESPA": "6YVMFz59CuY7ngCxTxjpxE",
        "TOMORROW X TOGETHER": "0ghlgldX5Dd6720Q3qFyQB",
        "TXT": "0ghlgldX5Dd6720Q3qFyQB"
    }

    for artist_name in KPOP_ARTISTS:
        print(f"\n🎤 Processing artist: {artist_name}...")
        
        # Normalize the name to check against overrides
        lookup_name = artist_name.strip().upper()
        
        if lookup_name in ARTIST_ID_OVERRIDES:
            artist_id = ARTIST_ID_OVERRIDES[lookup_name]
            print(f"   🎯 Override matched! Using hardcoded ID: {artist_id}")
        else:
            # Fallback to standard search API for other groups
            print(f"   🔍 Searching Spotify API for artist string...")
            search_results = sp.search(q=f"artist:{artist_name}", type="artist", limit=1)
            if not search_results['artists']['items']:
                print(f"   ⚠️ Could not find any profile for {artist_name}, skipping.")
                continue
            artist_id = search_results['artists']['items'][0]['id']
            print(f"   ✅ Found ID via search: {artist_id}")

        # SANITY CHECK CATCH: Ensure the ID is a valid format before making requests
        if not artist_id or not isinstance(artist_id, str) or " " in artist_id:
            print(f"   ❌ CRITICAL ERROR: Malformed artist_id discovered: '{artist_id}'. Skipping to protect pipeline.")
            continue

        seen_titles = set()
        
        for release_type in ['album', 'single']:
            print(f"   📦 Fetching {release_type} collection...")
            try:
                results = sp.artist_albums(artist_id, album_type=release_type, limit=50)
                for release in results['items']:
                    tracks = sp.album_tracks(release['id'])['items']
                    for track in tracks:
                        title = track['name']
                        clean_title = title.lower().strip()
                        
                        if clean_title in seen_titles:
                            continue
                        seen_titles.add(clean_title)
                        
                        popularity = random.randint(70, 99)
                        cursor.execute(
                            "INSERT INTO songs (title, artist, genre, popularity) VALUES (?, ?, 'K-Pop', ?)",
                            (title, artist_name, popularity)
                        )
                        total_tracks_inserted += 1
            except Exception as api_err:
                print(f"   ⚠️ API Error processing {release_type} for ID {artist_id}: {api_err}")
                continue
                
        print(f"   📊 Current database progress: Added {len(seen_titles)} tracks for {artist_name}")
        
    conn.commit()
    print(f"\n🎉 Library Sync Complete! Total {total_tracks_inserted} unique tracks successfully written.")
    conn.close()

def seed_matching_interaction_matrix():
    print("\n⚡ Generating matching 5,000+ interaction rows for the PyTorch engine...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM songs")
    song_ids = [row[0] for row in cursor.fetchall()]
    
    if not song_ids:
        print("Error: No songs found. Run the extraction engine first.")
        return
        
    dummy_interactions = []
    # Build 100 power-user profiles to establish dense correlation lines for deep learning
    for user_id in range(1, 101):
        num_favs = random.randint(15, 45)
        user_favorites = random.sample(song_ids, min(num_favs, len(song_ids)))
        
        for song_id in user_favorites:
            listen_count = random.randint(1, 4)
            for _ in range(listen_count):
                timestamp = datetime.utcnow().isoformat()
                dummy_interactions.append((user_id, song_id, timestamp))
                
    cursor.executemany("INSERT INTO listening_history (user_id, song_id, timestamp) VALUES (?, ?, ?)", dummy_interactions)
    conn.commit()
    print(f"✅ Generated {len(dummy_interactions)} historical dataset vector coordinates.")
    conn.close()

if __name__ == "__main__":
    rebuild_clean_database()
    pull_absolute_discographies()
    seed_matching_interaction_matrix()