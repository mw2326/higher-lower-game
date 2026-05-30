import sqlite3
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np

DB_FILE = "music_v2.db"
MODEL_PATH = "model.pth"

# 1. PYTORCH DATASET LAYER
class KpopInteractionDataset(Dataset):
    def __init__(self, db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Pull all interaction mappings
        cursor.execute("SELECT user_id, song_id FROM listening_history")
        rows = cursor.fetchall()
        conn.close()
        
        # PyTorch needs 0-indexed contiguous integer IDs for Embedding layers.
        # Let's map our SQL IDs to clean matrix indices.
        self.user_ids = np.array([r[0] for r in rows], dtype=np.int64)
        self.song_ids = np.array([r[1] for r in rows], dtype=np.int64)
        
        # Creating a simple target array (all 1.0 since these are tracks they listened to)
        self.targets = np.ones(len(rows), dtype=np.float32)

    def __len__(self):
        return len(self.targets)

    def __getitem__(self, idx):
        return (
            torch.tensor(self.user_ids[idx]),
            torch.tensor(self.song_ids[idx]),
            torch.tensor(self.targets[idx])
        )

# 2. NEURAL NETWORK ARCHITECTURE
class NeuralCollaborativeFiltering(nn.Module):
    def __init__(self, num_users, num_songs, embedding_dim=16):
        super().__init__()
        # Embedding Layers: maps discrete IDs to continuous vectors
        self.user_embedding = nn.Embedding(num_users + 1, embedding_dim)
        self.song_embedding = nn.Embedding(num_songs + 1, embedding_dim)
        
        # Deep Layers to capture complex non-linear combinations of user/song tastes
        self.fc_layers = nn.Sequential(
            nn.Linear(embedding_dim * 2, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()  # Outputs a preference score between 0.0 and 1.0
        )
        
    def forward(self, user_id, song_id):
        user_vec = self.user_embedding(user_id)
        song_vec = self.song_embedding(song_id)
        
        # Concatenate user vector and song vector together
        x = torch.cat([user_vec, song_vec], dim=-1)
        return self.fc_layers(x).squeeze(-1)

# 3. THE TRAINING LOOP
def train_model():
    print("Extracting rows from music_v2.db and formatting tensors...")
    dataset = KpopInteractionDataset(DB_FILE)
    dataloader = DataLoader(dataset, batch_size=64, shuffle=True)
    
    # Dynamically find the upper bounds of our ID spaces
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(user_id) FROM listening_history")
    max_user = cursor.fetchone()[0] or 100
    cursor.execute("SELECT MAX(id) FROM songs")
    max_song = cursor.fetchone()[0] or 2000
    conn.close()
    
    # Instantiate our deep learning model
    model = NeuralCollaborativeFiltering(num_users=max_user, num_songs=max_song)
    criterion = nn.BCELoss() # Binary Cross Entropy Loss for 0-1 classification/matching
    optimizer = optim.Adam(model.parameters(), lr=0.005)
    
    print(f"🏋️ Training neural net on {max_user} users and {max_song} possible track choices...")
    model.train()
    
    for epoch in range(10):  # Run data through network 10 times
        total_loss = 0
        for batch_users, batch_songs, batch_targets in dataloader:
            optimizer.zero_grad()
            
            # Forward Pass: Predict listening probability
            predictions = model(batch_users, batch_songs)
            loss = criterion(predictions, batch_targets)
            
            # Backward Pass: Compute gradients and step optimization weights
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            
        print(f"Epoch {epoch+1}/10 | Loss: {total_loss / len(dataloader):.4f}")
        
    # Save the trained brain parameters to disk
    torch.save(model.state_dict(), MODEL_PATH)
    print(f" Success! Neural weight parameters saved to '{MODEL_PATH}'")

if __name__ == "__main__":
    train_model()