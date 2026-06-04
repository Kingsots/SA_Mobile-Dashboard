import sqlite3
import pandas as pd
import os

DB_FILE = "trading_bot.db"
SYMBOLS = [
    "US30", "XAUUSD", "USDJPY", "GBPUSD", "EURJPY", "AUDCAD",
    "EURUSD", "AUDUSD", "AUDJPY", "GBPJPY", "CADJPY", "EURGBP", "USDCAD"
]

# Define export base folder
EXPORT_DIR = "exports"
TABLE_NAME = "market_data"   # ✅ make sure this matches your DB table

def export_to_csv():
    """Export only fresh data since last export, organized by timeframe"""
    try:
        conn = sqlite3.connect(DB_FILE)

        # Ensure export folder exists
        if not os.path.exists(EXPORT_DIR):
            os.makedirs(EXPORT_DIR)

        for symbol in SYMBOLS:
            try:
                query = f"SELECT * FROM {TABLE_NAME} WHERE symbol='{symbol}' ORDER BY timestamp"
                df = pd.read_sql_query(query, conn)

                if not df.empty:
                    # Extract timeframe from table if available, else fallback to '1h'
                    if "timeframe" in df.columns:
                        timeframes = df["timeframe"].unique()
                    else:
                        timeframes = ["1h"]

                    for tf in timeframes:
                        df_tf = df if "timeframe" not in df.columns else df[df["timeframe"] == tf]

                        # Create subfolder for timeframe
                        tf_dir = os.path.join(EXPORT_DIR, tf)
                        if not os.path.exists(tf_dir):
                            os.makedirs(tf_dir)

                        csv_path = os.path.join(tf_dir, f"{symbol}.csv")

                        if os.path.exists(csv_path):
                            # Read existing CSV to get last timestamp
                            old_df = pd.read_csv(csv_path)
                            if not old_df.empty and "timestamp" in old_df.columns:
                                last_ts = old_df["timestamp"].max()
                                # Keep only newer rows
                                new_data = df_tf[df_tf["timestamp"] > last_ts]
                            else:
                                new_data = df_tf
                        else:
                            new_data = df_tf

                        if not new_data.empty:
                            # Append if file exists, else create new
                            new_data.to_csv(csv_path, mode="a", header=not os.path.exists(csv_path), index=False)
                            print(f"Added {len(new_data)} new records for {symbol} [{tf}] to {csv_path}")
                        else:
                            print(f"No new data for {symbol} [{tf}]")
                else:
                    print(f"No data for {symbol}")
            except Exception as e:
                print(f"Error exporting {symbol}: {e}")
        conn.close()
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    export_to_csv()
