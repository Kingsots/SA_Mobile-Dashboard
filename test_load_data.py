import sys
sys.path.insert(0, '/home/ubuntu/SilentAnalyst')
from core.database import DatabaseManager

engine = DatabaseManager("/home/ubuntu/SilentAnalyst/trading_bot.db")
df = engine.load_ohlcv_data("EURUSD", "30m")
print(len(df))
