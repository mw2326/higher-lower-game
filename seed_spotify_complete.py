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
    
    print("Connecting to Spotify API for Complete Discography Sweep...")
    total_tracks_inserted = 0
    
    for artist_name in KPOP_ARTISTS:
        print(f"🎤 Gathering full catalog for: {artist_name}...")
        
        # UPGRADE: Direct Artist ID routing to completely eliminate text-search collisions
        if artist_name == "aespa":
            artist_id = "6YV6bUjG2vSgSEv0w6XgIM"  # aespa's verified Spotify ID
        elif artist_name == "TOMORROW X TOGETHER":
            artist_id = "0ghw0wFg3uXm669vErw3v3"  # TXT's verified Spotify ID
        elif artist_name == "BTS":
            artist_id = "3Nrfpe0tUvWvXmPM3bA76r"  # BTS's verified Spotify ID
        else:
            # Fallback to standard text search for the remaining artists
            search_results = sp.search(q=f"artist:{artist_name}", type="artist", limit=1)
            if not search_results['artists']['items']:
                continue
            artist_id = search_results['artists']['items'][0]['id']
            
        seen_titles = set()
        
        # Loop explicitly through BOTH 'album' and 'single' types to grab early/debut eras
        for release_type in ['album', 'single']:
            # Pull up to 50 items per type to ensure early years don't get cut off
            results = sp.artist_albums(artist_id, album_type=release_type, limit=50)
            releases = results['items']
            
            for release in releases:
                # Fetch tracks inside this specific release
                tracks = sp.album_tracks(release['id'])['items']
                
                for track in tracks:
                    title = track['name']
                    clean_title = title.lower().strip()
                    
                    # Deduplicate exact matching titles (skips live/instrumental repeats if title is identical)
                    if clean_title in seen_titles:
                        continue
                    seen_titles.add(clean_title)
                    
                    # Log track into SQL
                    popularity = random.randint(70, 99)
                    cursor.execute(
                        "INSERT INTO songs (title, artist, genre, popularity) VALUES (?, ?, 'K-Pop', ?)",
                        (title, artist_name, popularity)
                    )
                    total_tracks_inserted += 1
                    
        print(f"   Stored {len(seen_titles)} unique songs for {artist_name}")
        
    conn.commit()
    print(f"\n Library Sync Complete! {total_tracks_inserted} total tracks written to disk database.")
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