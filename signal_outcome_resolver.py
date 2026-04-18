#!/usr/bin/env python3
import sqlite3, logging

DB_PATH = "/home/ubuntu/SilentAnalyst/trading_bot.db"
LOOKBACK_BARS = 100
MIN_BARS = 10

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

JPY = ["CADJPY","GBPJPY","USDJPY","EURJPY","AUDJPY","NZDJPY","CHFJPY"]

def run():
    conn = sqlite3.connect(DB_PATH)
    
    rows = conn.execute("""
        SELECT id, ticker, interval, signal, entry_price,
               stop_loss, take_profit, created_at
        FROM ml_signals
        WHERE broadcasted=1
          AND outcome IS NULL
          AND entry_price IS NOT NULL
          AND stop_loss IS NOT NULL
          AND take_profit IS NOT NULL
          AND created_at > datetime('now','-90 days')
        ORDER BY created_at ASC
    """).fetchall()

    logger.info(f"Found {len(rows)} signals to resolve")

    tp = sl = ex = pend = 0

    for sid, ticker, interval, direction, entry, stop_loss, take_profit, created_at in rows:

        ts = created_at.replace(" ", "T") + "+00:00"

        bars = conn.execute("""
            SELECT high, low, close
            FROM ohlcv_data
            WHERE symbol=? AND timeframe=? AND timestamp>?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (ticker, interval, ts, LOOKBACK_BARS)).fetchall()

        if len(bars) < MIN_BARS:
            conn.execute("UPDATE ml_signals SET outcome=? WHERE id=?", ("PENDING", sid))
            pend += 1
            continue

        outcome = None
        pl_pips = 0.0
        last_close = None

        for high, low, close in bars:
            last_close = close
            if direction == 1:
                if high >= take_profit:
                    outcome = "TP_HIT"
                    pl_pips = take_profit - entry
                    break
                elif low <= stop_loss:
                    outcome = "SL_HIT"
                    pl_pips = stop_loss - entry
                    break
            elif direction == -1:
                if low <= take_profit:
                    outcome = "TP_HIT"
                    pl_pips = entry - take_profit
                    break
                elif high >= stop_loss:
                    outcome = "SL_HIT"
                    pl_pips = entry - stop_loss
                    break

        if outcome is None:
            outcome = "EXPIRY"
            pl_pips = (last_close - entry) if direction == 1 else (entry - last_close)

        if ticker == "XAUUSD":
            pl_usd = round(pl_pips * 10 * 0.10, 2)
        elif ticker in JPY:
            pl_usd = round(pl_pips * 100 * 0.10, 2)
        else:
            pl_usd = round(pl_pips * 10000 * 0.10, 2)

        conn.execute(
            "UPDATE ml_signals SET outcome=?, pl_usd=? WHERE id=?",
            (outcome, pl_usd, sid)
        )
        logger.info(f"Resolved {ticker} {interval} #{sid}: {outcome} ${pl_usd}")

        if outcome == "TP_HIT": tp += 1
        elif outcome == "SL_HIT": sl += 1
        elif outcome == "EXPIRY": ex += 1

        conn.commit()

    conn.close()
    logger.info(f"Done: {tp} TP_HIT, {sl} SL_HIT, {ex} EXPIRY, {pend} PENDING")

run()
