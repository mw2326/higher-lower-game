import os
import re
import sys
import time
import random
import requests
import psycopg2
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load local environment configurations
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL variable not found.")
    sys.exit(1)

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def scrape_backfill_covers():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return

    # 🎯 Isolate rows where the image url column is null or empty
    cursor.execute("""
        SELECT id, spotify_uri, title, artist 
        FROM songs 
        WHERE spotify_uri IS NOT NULL AND spotify_uri != '' 
          AND (image_url IS NULL OR image_url = '')
    """)
    songs_to_fix = cursor.fetchall()

    if not songs_to_fix:
        print("✅ Excellent! Every single track in your database already features an active album cover link.")
        cursor.close()
        conn.close()
        return

    print(f"🚀 Found {len(songs_to_fix)} tracks missing artwork.")
    print("🎯 Extracting artwork links directly from stream source pages to bypass Spotify API blocks...\n")
    
    updated_count = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }

    for i, song in enumerate(songs_to_fix):
        db_id, spotify_uri, title, artist = song
        
        # Ensure we only check the clean 22-character track code ID string
        clean_track_id = spotify_uri.split(":")[-1].strip()
        url = f"https://www.mystreamcount.com/track/{clean_track_id}"
        
        print(f"⏳ [{i+1}/{len(songs_to_fix)}] Scanning cover for: {artist} — {title}...")
        
        try:
            res = requests.get(url, headers=headers, timeout=10)
            
            if res.status_code == 429:
                print("   ⚠️ Rate limited by web server! Taking an extended defensive break...")
                time.sleep(10)
                continue
                
            if res.status_code != 200:
                print(f"   ❌ Web page returned error status code: {res.status_code}")
                continue
                
            soup = BeautifulSoup(res.text, "html.parser")
            album_image_url = ""
            
            # 🖼️ Look for the image tag containing the Spotify image delivery domain link
            img_match = soup.find('img', src=re.compile(r'(i\.scdn\.co/image|scdn\.co)'))
            if img_match:
                album_image_url = img_match['src']
            else:
                # Secondary fallback scanner loop inside the HTML elements
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    if 'ab67616d' in src or 'image/' in src:
                        album_image_url = src
                        break
            
            if album_image_url:
                # Update the target row inside your Supabase cluster table
                cursor.execute("""
                    UPDATE songs 
                    SET image_url = %s 
                    WHERE id = %s
                """, (album_image_url, db_id))
                conn.commit()
                updated_count += 1
                print(f"   ✅ Linked artwork link: {album_image_url}")
            else:
                print("   ⚠️ Webpage loaded successfully, but no embedded artwork element was found.")

        except Exception as e:
            print(f"   ❌ Network error processing this track: {e}")
            conn.rollback()

        # Brief delay to keep web scraper request volumes organic
        time.sleep(1.2 + random.uniform(0.3, 0.8))

    cursor.close()
    conn.close()
    print(f"\n🏁 Backfill complete! Successfully populated {updated_count} album covers straight into Supabase!")

if __name__ == "__main__":
    scrape_backfill_covers()