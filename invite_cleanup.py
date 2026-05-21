import sqlite3, datetime

DB_PATH = "/home/ubuntu/invite_auth.db"

def cleanup():
    conn = sqlite3.connect(DB_PATH)
    now = datetime.datetime.utcnow().isoformat()

    result = conn.execute(
        "UPDATE code_sessions SET is_active = 0 WHERE expires_at < ? AND is_active = 1",
        (now,)
    )
    expired = result.rowcount

    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=90)).isoformat()
    result2 = conn.execute(
        "DELETE FROM session_events WHERE ts < ?",
        (cutoff,)
    )
    pruned = result2.rowcount

    conn.commit()
    conn.close()
    print(f"[cleanup] expired={expired} sessions, pruned={pruned} old events")

if __name__ == "__main__":
    cleanup()
