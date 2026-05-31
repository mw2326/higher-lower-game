import sqlite3
import random
from datetime import datetime


def migrate_and_seed():
    # ------------------------------------------------------------------ #
    # 1. Prepare the destination game.db                                  #
    # ------------------------------------------------------------------ #
    new_conn = sqlite3.connect("game.db")
    new_cursor = new_conn.cursor()

    new_cursor.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT    NOT NULL,
            artist           TEXT    NOT NULL,
            genre            TEXT    DEFAULT 'K-Pop',
            spotify_uri      TEXT    DEFAULT '',
            stream_count     INTEGER DEFAULT 0,
            recommended_by   TEXT    DEFAULT 'System Core',
            notes            TEXT    DEFAULT '',
            last_updated     TEXT    NOT NULL
        )
    """)

    new_cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    NOT NULL,
            high_score   INTEGER NOT NULL,
            achieved_at  TEXT    NOT NULL
        )
    """)

    new_cursor.execute("DELETE FROM songs")
    new_conn.commit()

    # ------------------------------------------------------------------ #
    # 2. Pull tracks from music_v2.db (if it exists)                     #
    # ------------------------------------------------------------------ #
    try:
        old_conn = sqlite3.connect("music_v2.db")
        old_cursor = old_conn.cursor()

        # Grab every column that exists; spotify_uri may or may not be present
        old_cursor.execute("PRAGMA table_info(songs)")
        columns = [row[1] for row in old_cursor.fetchall()]

        has_uri = "spotify_uri" in columns
        select_cols = "title, artist, genre" + (", spotify_uri" if has_uri else "")
        old_cursor.execute(f"SELECT {select_cols} FROM songs")
        tracks = old_cursor.fetchall()
        old_conn.close()

        print(f"📦 Extracting {len(tracks)} songs from music_v2.db...")

        inserted = 0
        for track in tracks:
            title, artist, genre = track[0], track[1], track[2]
            spotify_uri = track[3] if has_uri and len(track) > 3 else ""

            # Use a simulated count for now; the hourly scraper will replace
            # these with real figures once valid spotify_uri values are present.
            simulated_streams = random.randint(5_000_000, 850_000_000)
            cur_time = datetime.utcnow().isoformat()

            new_cursor.execute("""
                INSERT INTO songs
                    (title, artist, genre, spotify_uri, stream_count,
                     recommended_by, notes, last_updated)
                VALUES (?, ?, ?, ?, ?, 'System Core Seeder', 'Base catalog track', ?)
            """, (title, artist, genre, spotify_uri, simulated_streams, cur_time))
            inserted += 1

        new_conn.commit()
        print(f"🎉 Successfully seeded {inserted} tracks into game.db!")

    except Exception as e:
        print(f"⚠️  Migration failed: {e}")
        print("   Tip: make sure music_v2.db exists in the same directory, or")
        print("   add songs manually via the /api/game/recommend endpoint.")

    finally:
        new_conn.close()


if __name__ == "__main__":
    migrate_and_seed()
