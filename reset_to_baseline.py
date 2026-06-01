import shutil
import os

BASELINE = "game_baseline.db"
ACTIVE_DB = "game.db"

def reset_game():
    if not os.path.exists(BASELINE):
        print(f"❌ Error: Cannot find backup baseline file '{BASELINE}'!")
        return
        
    print("🔄 Shifting database files...")
    try:
        # Safely overwrite the active database with the pristine Spotify records
        shutil.copyfile(BASELINE, ACTIVE_DB)
        print("✅ Success! Your active game database has been reset to your permanent Spotify data baseline.")
    except Exception as e:
        print(f"❌ Reset failed. Make sure your main.py server is turned off before resetting! Error: {e}")

if __name__ == "__main__":
    reset_game()