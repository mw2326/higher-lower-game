import sqlite3
import requests
import time
import re
import random
import sys
from bs4 import BeautifulSoup

DB_FILE = "game.db"

def fetch_stream_count(uri):
    """
    Parses the full HTML page response.
    Returns a tuple: (stream_count_or_None, hit_hard_429_boolean)
    """
    url = f"https://www.mystreamcount.com/track/{uri}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    }
    
    delay = 2
    
    for attempt in range(5):
        try:
            res = requests.get(url, headers=headers, timeout=10)
            
            if res.status_code == 429:
                print(f"   ⚠️ Rate limited (429). Internal retry cooldown... Waiting {delay}s...")
                time.sleep(delay)
                delay *= 2
                continue
                
            if res.status_code != 200:
                return None, False
                
            soup = BeautifulSoup(res.text, "html.parser")
            page_text = soup.get_text()
            
            numbers = re.findall(r'\b\d{1,3}(?:,\d{3})+\b|\b\d{5,}\b', page_text)
            valid_counts = [int(num.replace(',', '')) for num in numbers]
            
            if valid_counts:
                return max(valid_counts), False
                
            return 0, False
            
        except Exception as e:
            print(f"   ⚠️ Network exception on attempt {attempt+1}: {e}")
            time.sleep(1)
            continue
            
    # Hit a sticky 429 lock all 5 times
    return None, True

def main():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, artist, spotify_uri FROM songs 
        WHERE spotify_uri IS NOT NULL AND spotify_uri != '' 
          AND (stream_count = 0 OR stream_count IS NULL OR stream_count = '')
    """)
    songs = cursor.fetchall()

    if not songs:
        print("✅ No missing stream counts found—your active catalog is fully complete!")
        conn.close()
        return

    print(f"🚀 Safely harvesting stream counts for {len(songs)} songs...\n")
    found = 0

    for i, song in enumerate(songs):
        streams, hit_hard_429 = fetch_stream_count(song["spotify_uri"])

        if hit_hard_429:
            print(f"\n🚨 [HARD LOCKOUT] Server has completely blocked our IP address at track {i+1}.")
            print("🛑 Shutting down gracefully to protect data integrity and prevent false skips.")
            print("💡 Action Item: Wait 15–30 minutes for the server's window to reset, then run me again!")
            conn.close()
            sys.exit(0)

        if streams is not None:
            cursor.execute("UPDATE songs SET stream_count = ? WHERE id = ?", (streams, song["id"]))
            conn.commit()  
            found += 1
            print(f"   ✅ [{i+1}/{len(songs)}] {song['artist']} — {song['title']}: {streams:,} streams")
        else:
            print(f"   ❌ [{i+1}/{len(songs)}] {song['artist']} — {song['title']}: permanent server 404 bypass")

        # Generous base delay + randomized jitter to mimic organic human browsing patterns
        time.sleep(2.5 + random.uniform(0.5, 2.0))

    conn.close()
    print(f"\n🏁 Stream integration finished! Successfully populated {found} tracks.")

if __name__ == "__main__":
    main()