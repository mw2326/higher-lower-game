import sqlite3

def add_spotify_column():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    try:
        # Safely inject the missing column into your existing game table
        cursor.execute("ALTER TABLE songs ADD COLUMN spotify_uri TEXT DEFAULT ''")
        conn.commit()
        print("✅ Successfully patched game.db! 'spotify_uri' column added.")
    except sqlite3.OperationalError:
        print("ℹ️ Column 'spotify_uri' already exists.")
    finally:
        conn.close()

if __name__ == "__main__":
    add_spotify_column()