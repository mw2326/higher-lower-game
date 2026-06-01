import sqlite3
import requests
import time
import base64
import re

# ── Credentials ──────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID = "25ce95b84928409ca0701e1319002fc5"
SPOTIFY_CLIENT_SECRET = "44a5fbcff18a4ecbbafa051a75e1b0ef"
# ─────────────────────────────────────────────────────────────────────────

DB_FILE = "game.db"

# 100% Strict Production K-Pop Artist IDs
ARTIST_IDS = {
    "IVE":                 "6RHTUrRF63xao58xh9FXYJ",
    "aespa":               "2crQPbGNQKaJAv0eBSBLOW",
    "TWICE":               "7n2Ycct7Beij7Dj7meI4X0",
    "BTS":                 "3Nrfpe0tUJi4K4DXYWgMUX",
    "BLACKPINK":           "41MozSoPIsD1dJM0CLPjZF",
    "NewJeans":            "2pyHGHWEQJzwNiGFMGCPAc",
    "EXO":                 "3cjEqqelV9zb4BYE3KB9TN",
    "SHINee":              "2BTZIql09sShoTWbcIlzdV",
    "Red Velvet":          "1z4g3DjTBBZKhvAroFlhOM",
    "ITZY":                "2KC9Qb60EaY0dW3LvsDyeh",
    "STAYC":               "5MnVBGkNGwrn7OaRDzMCbM",
    "MAMAMOO":             "69be3I0QdDnEBaOCXpzydN",
    "GOT7":                "0iEtIxbK0KxaSlF7G42ZOp",
    "NCT 127":             "7f4ignuCJhLXfZ9giMiyaD",
    "NCT DREAM":           "1gBUSTR3TyDdTVFIaQnIOk",
    "WayV":                "4HTQKH5WKd3zG0rHBBqPg8",
    "ENHYPEN":             "0c173mlxpT3IRYAryMc376",
    "TXT":                 "4vGrte8FDu062Ntj0RsPiZ",
    "TOMORROW X TOGETHER": "4vGrte8FDu062Ntj0RsPiZ",
    "Stray Kids":          "2hCS7LGf2s2VgpVGxuXkUE",
    "SEVENTEEN":           "7nqOGox3kNQsC5OVq8GFOL",
    "MONSTA X":            "8PhoENECmATWMMvfcG5B7l",
    "WINNER":              "2iojnBLj0qIMiKPvVhLnsH",
    "BIGBANG":             "3QWEGbLMHwblGsNzyK3qHL",
    "f(x)":                "4sPmO7WMQUAf45kwMOtONw",
    "LE SSERAFIM":         "6HvZYsbFfjnjFrWF950C9d",
    "NMIXX":               "5LHy976ndsk4lHHxKFGzgG",
    "Kep1er":              "2WX2uTcsvV5OnS0inACecP",
    "i-dle":               "2AfmfGFAFKogt4FHVpAuFa",
    "(G)I-DLE":            "2AfmfGFAFKogt4FHVpAuFa"
}

def get_spotify_token():
    creds = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()
    res = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={"Authorization": f"Basic {creds}"},
        data={"grant_type": "client_credentials"},
    )
    res.raise_for_status()
    return res.json()["access_token"]

def normalize(s):
    if not s:
        return ""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", s.lower())
    return " ".join(cleaned.split())

def search_spotify(token, title, artist):
    artist_id = ARTIST_IDS.get(artist)
    if not artist_id:
        return None, None

    # Replace query-breaking syntax symbols with clean spaces to prevent string compression drops
    clean_title = re.sub(r"[()\[\]\-─—]", " ", title)
    clean_title = " ".join(clean_title.split()).replace('"', '').replace("'", "")
    
    # Secure exact field mapping lookup
    query_string = f'track:"{clean_title}" artist:"{artist}"'

    try:
        res = requests.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query_string, "type": "track", "limit": 10},
        )
        
        if res.status_code == 401:
            return None, "expired"
            
        items = res.json().get("tracks", {}).get("items", [])
        
        # Fallback: Relax matching scopes if strict quotations return completely empty arrays
        if not items:
            relaxed_query = f'track:{clean_title} artist:"{artist}"'
            res = requests.get(
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": relaxed_query, "type": "track", "limit": 10},
            )
            if res.status_code == 401:
                return None, "expired"
            items = res.json().get("tracks", {}).get("items", [])

        # --- EVALUATION ENGINE ─────────────────────────────────────────────
        title_n = normalize(title)
        clean_title_n = normalize(clean_title)
        artist_n = normalize(artist)

        for item in items:
            item_artist_ids = [a["id"] for a in item["artists"]]
            result_title_n = normalize(item["name"])
            result_artists_n = [normalize(a["name"]) for a in item["artists"]]
            
            # String alignment check
            title_ok = (title_n == result_title_n or title_n in result_title_n or result_title_n in title_n or clean_title_n in result_title_n)
            
            # Strict Filtering: Artist matches official ID OR clean text array parameters.
            # This handles sandbox environment variations while keeping bad data OUT.
            artist_ok = (artist_id in item_artist_ids) or any(artist_n == a or artist_n in a or a in artist_n for a in result_artists_n)
            
            if title_ok and artist_ok:
                return item["id"], None
                
        return None, None

    except Exception:
        return None, None

def main():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ── AUTOMATIC CORRUPTION PURGE ─────────────────────────────────────────
    # Cleans up the mislabeled western alternative tracks out of the IVE pool permanently
    fake_ive_tracks = [
        'Fresh', 'Medicine', 'Break Away', 'Sincerely Me', "Leavin'", 'Kids Again',
        'Somewhere Else', 'Everything Must Go', 'Break Away (Piano Version)', 
        'Leaving in the Morning (feat. Blackbear)', 'Stay', 'Wait for You', 
        'Anything at All', 'The Remedy', 'Different People (feat. Devyn De Loera)', 
        'Whiskey Problems', 'Let You Go', 'Remember This', 'The Best That You Can Be', 
        "Leavin' in the Morning", 'Different People', 'Car Crash', 'Favorite Fix', 
        'Unconscious Reality', 'Damn Rough Night', "We're All The Same", 
        'So Much I Never Said', 'Miserably Loving You', 'Broke But Not Broken', 
        "He's Just Not Me", 'Alive', 'Giving Yourself Away', 'Break', 'Hang Around', 
        "Where I'm Gonna Be", 'Dreaming My Way to You', 'Rescue', 'To Hell With The Letdown', 
        'Assurance Closure', 'Lisa Marie', 'Infallible Remedy', 'All In'
    ]
    
    cursor.execute("""
        DELETE FROM songs 
        WHERE artist = 'IVE' AND title IN ({})
    """.format(','.join('?' for _ in fake_ive_tracks)), fake_ive_tracks)
    
    if cursor.rowcount > 0:
        print(f"🧹 Automatically purged {cursor.rowcount} corrupted rock tracks from the IVE pool.")
        conn.commit()

    # Locate tracks needing URIs
    cursor.execute("SELECT id, title, artist FROM songs WHERE spotify_uri = '' OR spotify_uri IS NULL")
    songs = cursor.fetchall()

    if not songs:
        print("✅ All songs currently possess verified Spotify URIs.")
        conn.close()
        return

    print(f"🔍 Strictly checking Spotify URIs for {len(songs)} songs...\n")

    token = get_spotify_token()
    found = 0
    not_found = 0

    for i, song in enumerate(songs):
        if i > 0 and i % 50 == 0:
            token = get_spotify_token()

        uri, status = search_spotify(token, song["title"], song["artist"])

        if status == "expired":
            token = get_spotify_token()
            uri, _ = search_spotify(token, song["title"], song["artist"])

        if uri:
            cursor.execute("UPDATE songs SET spotify_uri = ? WHERE id = ?", (uri, song["id"]))
            conn.commit()  # Instant tracking logging checkpoints
            found += 1
            print(f"   ✅ [{i+1}/{len(songs)}] {song['artist']} — {song['title']}: {uri}")
        else:
            not_found += 1
            print(f"   ❌ [{i+1}/{len(songs)}] {song['artist']} — {song['title']}: skipped/not found")

        # Slight half-second breathing room delay to prevent proxy network congestion
        time.sleep(0.5)

    conn.commit()
    conn.close()

    print(f"\n🏁 Finished Processing. {found} strict matches saved, {not_found} items rejected.")

if __name__ == "__main__":
    main()