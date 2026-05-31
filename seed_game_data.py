import sqlite3
import random
from datetime import datetime

def migrate_and_seed():
    # Connect to both old and new data spaces
    old_conn = sqlite3.connect("music_v2.db")
    old_cursor = old_conn.cursor()
    
    new_conn = sqlite3.connect("game.db")
    new_cursor = new_conn.cursor()
    
    # Clear out any old records from previous setup tests
    new_cursor.execute("DELETE FROM songs")
    
    try:
        old_cursor.execute("SELECT title, artist, genre FROM songs")
        tracks = old_cursor.fetchall()
        print(f"📦 Extracting {len(tracks)} songs from old database format...")
        
        inserted = 0
        for track in tracks:
            title, artist, genre = track
            
            # Seed them with realistic multi-million stream counts matching MyStreamCount profiles
            simulated_streams = random.randint(5_000_000, 850_000_000)
            
            # Assign system contributors to standard base catalog items
            cur_time = datetime.utcnow().isoformat()
            new_cursor.execute("""
                INSERT INTO songs (title, artist, genre, stream_count, recommended_by, notes, last_updated)
                VALUES (?, ?, ?, ?, 'System Core Seeder', 'Base catalog track', ?)
            """, (title, artist, genre, simulated_streams, cur_time))
            inserted += 1
            
        new_conn.commit()
        print(f"🎉 Successfully seeded {inserted} tracks into game.db with stream fields!")
    except Exception as e:
        print(f"⚠️ Migration note (If old DB wasn't seeded yet): {e}")
    finally:
        old_conn.close()
        new_conn.close()

if __name__ == "__main__":
    migrate_and_seed()