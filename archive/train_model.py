# train_model.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler
import pickle
import sqlite3
from datetime import datetime

DB_FILE = "trading_bot.db"
MODEL_FILE = "trading_model.pkl"

def fetch_data(symbol):
    """Try DB first, fall back to CSV if missing"""
    try:
        conn = sqlite3.connect(DB_FILE)
        query = f"""
        SELECT timestamp, open, high, low, close, volume 
        FROM market_data 
        WHERE symbol = '{symbol}' 
        ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        if len(df) < 50:
            raise ValueError("Not enough DB data, fallback to CSV")
        print(f"[DB] Loaded {len(df)} records for {symbol}")
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df.set_index('timestamp')

    except Exception as e:
        try:
            df = pd.read_csv(f"{symbol}_1h.csv")
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            print(f"[CSV] Loaded {len(df)} records for {symbol}")
            return df
        except FileNotFoundError:
            print(f"[ERROR] No data for {symbol} in DB or CSV")
            return None

def calculate_features(df):
    """Calculate advanced features for ML model"""
    if df is None or len(df) < 50:
        return None

    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    df['rsi_slope'] = df['rsi'].diff()
    df['volume_zscore'] = (df['volume'] - df['volume'].rolling(20).mean()) / df['volume'].rolling(20).std()
    df['ema_12'] = df['close'].ewm(span=12).mean()
    df['ema_26'] = df['close'].ewm(span=26).mean()
    df['ema_alignment'] = df['ema_12'] - df['ema_26']
    df['macd'] = df['ema_12'] - df['ema_26']
    df['signal_line'] = df['macd'].ewm(span=9).mean()
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    df['bb_std'] = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + 2 * df['bb_std']
    df['bb_lower'] = df['bb_middle'] - 2 * df['bb_std']
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
    return df.dropna()

# Expanded watchlist
symbols = ["US30", "NAS100", "US500", "XAUUSD", "USDJPY", "GBPUSD", "EURUSD", 
           "AUDUSD", "AUDJPY", "GBPJPY", "CADJPY", "EURJPY", "EURGBP", 
           "USDCAD", "AUDCAD"]

print("Training ML model on watchlist...")
print("=" * 60)

data = {}
for symbol in symbols:
    df = fetch_data(symbol)
    df = calculate_features(df)
    if df is not None:
        data[symbol] = df
    else:
        print(f"[SKIP] {symbol} has insufficient data")

X, y, symbol_labels = [], [], []
for symbol, df in data.items():
    if len(df) > 100:
        buy_signals = df[df['target'] == 1]
        sell_signals = df[df['target'] == 0]

        min_size = min(len(buy_signals), len(sell_signals))
        if min_size > 0:
            balanced_df = pd.concat([
                buy_signals.sample(n=min_size, random_state=42),
                sell_signals.sample(n=min_size, random_state=42)
            ])
            features = balanced_df[['rsi_slope', 'volume_zscore', 'ema_alignment', 
                                    'macd', 'signal_line', 'bb_width']]
            X.append(features)
            y.append(balanced_df['target'])
            symbol_labels.extend([symbol] * len(features))
        else:
            print(f"[SKIP] {symbol} has no balanced signals")

if not X:
    print("[ERROR] No training data available!")
    exit()

X = pd.concat(X)
y = pd.concat(y)

# Scale features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Train/test split
X_train, X_test, y_train, y_test, symbols_train, symbols_test = train_test_split(
    X_scaled, y, symbol_labels, test_size=0.2, random_state=42
)

# Train model
model = RandomForestClassifier(n_estimators=200, max_depth=10, min_samples_split=5, random_state=42)
model.fit(X_train, y_train)

# Evaluate overall
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print("=" * 60)
print(f"Overall Model accuracy: {accuracy:.2%}")
print("=" * 60)

# Per-symbol accuracy
results = pd.DataFrame({
    "symbol": symbols_test,
    "true": y_test,
    "pred": y_pred
})
per_symbol_acc = results.groupby("symbol").apply(lambda df: accuracy_score(df["true"], df["pred"]))
print("Per-Symbol Accuracy:")
print(per_symbol_acc.sort_values(ascending=False).to_string())
print("=" * 60)

# Save model and scaler
with open('trading_model.pkl', 'wb') as f:
    pickle.dump(model, f)
with open('scaler.pkl', 'wb') as f:
    pickle.dump(scaler, f)

print("✅ Model saved to trading_model.pkl")
print("✅ Scaler saved to scaler.pkl")
print("Training complete!")