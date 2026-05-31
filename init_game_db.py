import sqlite3

def init_game_db():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()

    # 1. Main track catalog — includes spotify_uri so the hourly scraper
    #    can fetch real stream counts from mystreamcount.com/track/{uri}
    cursor.execute("""
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

    # 2. High-score leaderboard for players
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT    NOT NULL,
            high_score   INTEGER NOT NULL,
            achieved_at  TEXT    NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    print("Game database structures created successfully!")

if __name__ == "__main__":
    init_game_db()
