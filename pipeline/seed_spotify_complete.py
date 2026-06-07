import os
import random
import sys
import psycopg2
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv()
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL variable not found.")
    sys.exit(1)

auth_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(auth_manager=auth_manager)

KPOP_ARTISTS = [
    "NewJeans", "BTS", "aespa", "Stray Kids", "TWICE", "BLACKPINK", 
    "SEVENTEEN", "IVE", "LE SSERAFIM", "ENHYPEN", "TOMORROW X TOGETHER", "Red Velvet", "NMIXX"
]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def pull_absolute_discographies():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return

    # 🛑 ANTI-DUPLICATE SHIELD: Fetch ALL song titles already in your Supabase DB
    print("🛡️ Checking Supabase for existing songs to prevent duplicates...")
    cursor.execute("SELECT LOWER(TRIM(title)) FROM songs")
    seen_titles = set(row[0] for row in cursor.fetchall() if row[0])
    print(f"✅ Loaded {len(seen_titles)} tracks already saved in cloud.")

    print("\n🚀 Connecting to Spotify API...")
    total_tracks_inserted = 0
    
    ARTIST_ID_OVERRIDES = {
        "BTS": "3Nrfpe0tUJi4K4DXYWgMUX",
        "AESPA": "6YVMFz59CuY7ngCxTxjpxE",
        "TOMORROW X TOGETHER": "0ghlgldX5Dd6720Q3qFyQB",
        "TXT": "0ghlgldX5Dd6720Q3qFyQB"
    }

    for artist_name in KPOP_ARTISTS:
        print(f"\n🎤 Processing artist: {artist_name}...")
        lookup_name = artist_name.strip().upper()
        
        if lookup_name in ARTIST_ID_OVERRIDES:
            artist_id = ARTIST_ID_OVERRIDES[lookup_name]
        else:
            search_results = sp.search(q=f"artist:{artist_name}", type="artist", limit=1)
            if not search_results['artists']['items']:
                continue
            artist_id = search_results['artists']['items'][0]['id']

        for release_type in ['album', 'single']:
            print(f"   📦 Fetching {release_type} collection...")
            try:
                album_url = f"artists/{artist_id}/albums?include_groups={release_type}&market=US"
                results = sp._get(album_url)
                
                for release in results['items']:
                    # 🖼️ FIXED NESTING PATH: Images live straight inside the release object here!
                    album_image_url = ""
                    if 'images' in release and len(release['images']) > 1:
                        album_image_url = release['images'][1]['url'] # 300x300 medium size
                    elif 'album' in release and 'images' in release['album'] and len(release['album']['images']) > 1:
                        album_image_url = release['album']['images'][1]['url']
                    
                    tracks_url = f"albums/{release['id']}/tracks?market=US"
                    tracks_data = sp._get(tracks_url)
                    
                    for track in tracks_data['items']:
                        title = track['name']
                        clean_title = title.lower().strip()
                        
                        # Check against global cloud duplicates AND local run duplicates
                        if clean_title in seen_titles:
                            continue
                        seen_titles.add(clean_title)
                        
                        track_uri = track['uri'].split(':')[-1] if 'uri' in track else ""
                        
                        cursor.execute("""
                            INSERT INTO songs (title, artist, genre, image_url, spotify_uri, last_updated) 
                            VALUES (%s, %s, 'K-Pop', %s, %s, NOW()::text)
                        """, (title, artist_name, album_image_url, track_uri))
                        
                        total_tracks_inserted += 1
                        
                conn.commit() # Commit per album collection phase
            except Exception as api_err:
                print(f"   ⚠️ API/DB Error processing {release_type} for ID {artist_id}: {api_err}")
                conn.rollback()
                continue
                
        print(f"   📊 Finished processing for {artist_name}")
        
    cursor.close()
    conn.close()
    print(f"\n🏁 Complete! Successfully appended {total_tracks_inserted} brand new unique visual tracks.")

if __name__ == "__main__":
    pull_absolute_discographies()