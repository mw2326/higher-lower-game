import sqlite3

DB_FILE = "game.db"

def check_uris():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query for tracks where a Spotify URI was successfully filled in
    cursor.execute("""
        SELECT title, artist, spotify_uri, stream_count 
        FROM songs 
        WHERE spotify_uri IS NOT NULL AND spotify_uri != '' 
        LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()
    
    print(f"📊 Checking '{DB_FILE}' content...\n")
    if not rows:
        print("❌ No Spotify URIs found in this database file yet.")
        return
        
    print(f"✅ Success! Found filled rows:")
    for row in rows:
        print(f" ── {row['artist']} - {row['title']}")
        print(f"    🔗 URI: {row['spotify_uri']}")
        print(f"    🎵 Streams: {row['stream_count']:,}\n")

if __name__ == "__main__":
    check_uris()