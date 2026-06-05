import sqlite3

DB_FILE = "game.db"

def audit_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. Total number of tracks in the table
    cursor.execute("SELECT COUNT(*) FROM songs")
    total_songs = cursor.fetchone()[0]
    
    # 2. Tracks that have a real, valid stream count populated
    cursor.execute("""
        SELECT COUNT(*) FROM songs 
        WHERE stream_count IS NOT NULL 
          AND stream_count != 0 
          AND stream_count != ''
    """)
    filled_streams = cursor.fetchone()[0]
    
    # 3. Tracks that have a valid Spotify URI populated
    cursor.execute("""
        SELECT COUNT(*) FROM songs 
        WHERE spotify_uri IS NOT NULL 
          AND spotify_uri != ''
    """)
    filled_uris = cursor.fetchone()[0]
    
    # 4. Grab a few examples of recently saved tracks with real numbers
    cursor.execute("""
        SELECT artist, title, stream_count, spotify_uri FROM songs 
        WHERE stream_count > 0 
        ORDER BY id DESC 
        LIMIT 5
    """)
    recent_samples = cursor.fetchall()
    
    conn.close()
    
    # ── Print Dashboard ──────────────────────────────────────────────────
    print("\n📊 ═══ GAME DATABASE AUDIT REPORT ═══")
    print(f"Total Song Slots in DB:      {total_songs:,}")
    print(f"✅ Songs with Stream Counts:  {filled_streams:,} / {total_songs:,} ({filled_streams/total_songs*100:.1f}%)")
    print(f"✅ Songs with Spotify URIs:   {filled_uris:,} / {total_songs:,} ({filled_uris/total_songs*100:.1f}%)")
    print(f"❌ Missing/Incomplete Data:  {total_songs - filled_streams:,} tracks left to scrape")
    
    if recent_samples:
        print("\n🎵 Recent Snapshot of Permanently Saved Tracks:")
        for artist, title, streams, uri in recent_samples:
            print(f" ── {artist} — {title}")
            print(f"    Stream Count: {streams:,} | URI: {uri}")
    print("═════════════════════════════════════\n")

if __name__ == "__main__":
    audit_database()