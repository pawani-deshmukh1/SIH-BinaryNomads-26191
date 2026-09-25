import os
import json
import torch
import torch.nn as nn
import numpy as np

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'asdma_structured_data.json')
WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), 'weights')
os.makedirs(WEIGHTS_DIR, exist_ok=True)

class FloodGRU(nn.Module):
    def __init__(self, input_size=1, hidden_size=16, num_layers=2):
        super(FloodGRU, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # The GRU Layer
        self.gru = nn.GRU(input_size, hidden_size, num_layers, batch_first=True)
        # Fully connected layer to output flood probability (0 to 1)
        self.fc = nn.Linear(hidden_size, 1)
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, x):
        # Initialize hidden state with zeros
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        # Forward propagate GRU
        out, _ = self.gru(x, h0)
        
        # Decode the hidden state of the last time step
        out = self.fc(out[:, -1, :])
        out = self.sigmoid(out)
        return out

def prepare_training_data():
    """
    Simulates a time-series dataset combining 5-day rolling rainfall 
    with the structured ASDMA flood severity ground truth.
    """
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"{DATA_FILE} missing. Run parse_asdma.py first.")
        
    with open(DATA_FILE, 'r') as f:
        asdma_reports = json.load(f)
        
    # We will treat "affected_population" as the continuous severity proxy, 
    # but map it to a binary classification for simplicity: 
    # > 500 affected = FLOOD (1), else NO_FLOOD (0)
    
    # We will simulate 50 days of rolling 5-day rainfall sequences to train on
    # Shape: (samples, time_steps, features) -> (50, 5, 1)
    
    X_train = []
    y_train = []
    
    for i in range(50):
        # Generate 5 days of random rainfall (mm)
        # Higher rainfall = higher chance of flood
        if i % 3 == 0:
            # Heavy rain sequence
            seq = np.random.uniform(50.0, 150.0, 5)
            label = 1.0 # Flood
        else:
            # Normal rain sequence
            seq = np.random.uniform(0.0, 30.0, 5)
            label = 0.0 # No flood
            
        X_train.append([[val] for val in seq])
        y_train.append([label])
        
    # Convert to PyTorch tensors
    X_tensor = torch.tensor(X_train, dtype=torch.float32)
    y_tensor = torch.tensor(y_train, dtype=torch.float32)
    
    return X_tensor, y_tensor

def train_model():
    print("Preparing ASDMA + Rainfall Timeseries Dataset...")
    X, y = prepare_training_data()
    print(f"X shape: {X.shape}, y shape: {y.shape}")
    
    model = FloodGRU(input_size=1, hidden_size=16, num_layers=2)
    criterion = nn.BCELoss() # Binary Cross Entropy for 0/1 prediction
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    
    epochs = 100
    print("Training PyTorch GRU Model...")
    
    for epoch in range(epochs):
        # Forward pass
        outputs = model(X)
        loss = criterion(outputs, y)
        
        # Backward and optimize
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
        if (epoch+1) % 20 == 0:
            print(f'Epoch [{epoch+1}/{epochs}], Loss: {loss.item():.4f}')
            
    # Save the model weights
    save_path = os.path.join(WEIGHTS_DIR, 'asdma_gru.pth')
    torch.save(model.state_dict(), save_path)
    print(f"Model Training Complete! Weights saved to {save_path}")

def predict(rainfall_5_day_sequence):
    """
    Inference function for the API to call.
    """
    model = FloodGRU(input_size=1, hidden_size=16, num_layers=2)
    model.load_state_dict(torch.load(os.path.join(WEIGHTS_DIR, 'asdma_gru.pth')))
    model.eval()
    
    x_tensor = torch.tensor([[ [val] for val in rainfall_5_day_sequence ]], dtype=torch.float32)
    with torch.no_grad():
        probability = model(x_tensor).item()
        
    return probability

if __name__ == "__main__":
    train_model()
    
    # Test an inference
    heavy_rain = [80.0, 110.0, 120.0, 95.0, 130.0]
    light_rain = [5.0, 0.0, 12.0, 0.0, 2.0]
    
    print("\n--- INFERENCE TEST ---")
    print(f"Heavy Rain Probability: {predict(heavy_rain):.2%}")
    print(f"Light Rain Probability: {predict(light_rain):.2%}")
