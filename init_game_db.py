import sqlite3

def init_game_db():
    conn = sqlite3.connect("game.db")
    cursor = conn.cursor()
    
    # 1. Main track catalog containing streaming counts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            genre TEXT DEFAULT 'K-Pop',
            stream_count INTEGER DEFAULT 0,
            last_updated TEXT NOT NULL
        )
    """)
    
    # 2. Tracks tracking for "those who recommend it" (contributors/endorsers)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            song_id INTEGER NOT NULL,
            recommended_by TEXT NOT NULL,
            notes TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(song_id) REFERENCES songs(id)
        )
    """)
    
    # 3. Quick high score leaderboard tracker for players
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            username TEXT NOT NULL,
            high_score INTEGER NOT NULL,
            achieved_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()
    print("Game database structures created successfully!")

if __name__ == "__main__":
    init_game_db()