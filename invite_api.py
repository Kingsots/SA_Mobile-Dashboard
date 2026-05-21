from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3, uuid, datetime, requests, os

app = Flask(__name__)
CORS(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
    strategy="fixed-window"
)

BRUTE_FORCE_LIMIT = "10 per minute"
GENERAL_API_LIMIT = "60 per minute"

DB_PATH = "/home/ubuntu/invite_auth.db"
SCHEMA_PATH = "/home/ubuntu/invite_schema.sql"
ADMIN_SECRET = os.environ.get("INVITE_ADMIN_SECRET", "CHANGE_ME")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

def get_geo(ip):
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        d = r.json()
        return d.get("country", ""), d.get("city", "")
    except:
        return "", ""

def require_admin():
    return request.headers.get("X-Admin-Secret", "") == ADMIN_SECRET

MOBILE_AUTH_DB = "/home/ubuntu/SilentAnalyst/mobile_auth.db"

def sync_to_mobile_auth(code, role="beta"):
    """Mirror new invite code into legacy mobile_auth.db."""
    try:
        conn = sqlite3.connect(MOBILE_AUTH_DB)
        conn.execute(
            "INSERT OR IGNORE INTO invite_codes (code, tier, created_at) VALUES (?, ?, ?)",
            (code, role, datetime.datetime.utcnow().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

@app.route("/api/auth/login", methods=["POST"])
@limiter.limit(BRUTE_FORCE_LIMIT)
def login():
    data = request.get_json() or {}
    code = (data.get("code") or "").strip().upper()
    if not code:
        return jsonify({"success": False, "error": "Code required"}), 400

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM invite_codes WHERE code = ? AND is_active = 1", (code,)
    ).fetchone()

    if not row:
        try:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()
            conn.execute(
                "INSERT INTO session_events (session_id, event_type, page, event_data) VALUES (?, 'login_failure', 'auth', ?)",
                ("anonymous", f"code={code[:4]}*** ip={ip}")
            )
            conn.commit()
        except:
            pass
        conn.close()
        return jsonify({"success": False, "error": "Invalid or inactive code"}), 401

    if row["max_uses"] and row["use_count"] >= row["max_uses"]:
        conn.close()
        return jsonify({"success": False, "error": "Code limit reached"}), 403

    if row["expires_at"] and row["expires_at"] < datetime.datetime.utcnow().isoformat():
        conn.close()
        return jsonify({"success": False, "error": "Code expired"}), 403

    session_id = uuid.uuid4().hex
    ip = request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()
    country, city = get_geo(ip)
    ua = request.headers.get("User-Agent", "")
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()

    conn.execute(
        "INSERT INTO code_sessions (session_id, invite_code, ip_address, country, city, user_agent, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session_id, code, ip, country, city, ua, expires_at)
    )
    conn.execute(
        "UPDATE invite_codes SET use_count = use_count + 1 WHERE code = ?", (code,)
    )
    conn.execute(
        "INSERT INTO session_events (session_id, event_type, page) VALUES (?, 'login_success', 'auth')",
        (session_id,)
    )
    conn.commit()
    conn.close()

    return jsonify({"success": True, "session_id": session_id, "role": row["role"], "expires_at": expires_at})


@app.route("/api/auth/validate", methods=["POST"])
@limiter.limit(GENERAL_API_LIMIT)
def validate():
    data = request.get_json() or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"valid": False}), 400

    conn = get_db()
    row = conn.execute(
        """SELECT s.*, c.role FROM code_sessions s
           JOIN invite_codes c ON s.invite_code = c.code
           WHERE s.session_id = ? AND s.is_active = 1""",
        (session_id,)
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"valid": False, "reason": "Session not found"}), 401

    if row["expires_at"] and row["expires_at"] < datetime.datetime.utcnow().isoformat():
        conn.close()
        return jsonify({"valid": False, "reason": "Session expired"}), 401

    conn.execute(
        "UPDATE code_sessions SET last_seen = datetime('now') WHERE session_id = ?", (session_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({"valid": True, "role": row["role"]})


@app.route("/api/auth/event", methods=["POST"])
@limiter.limit(GENERAL_API_LIMIT)
def track_event():
    data = request.get_json() or {}
    session_id = (data.get("session_id") or "").strip()
    event_type = (data.get("event_type") or "").strip()
    if not session_id or not event_type:
        return jsonify({"ok": False}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO session_events (session_id, event_type, page, event_data) VALUES (?, ?, ?, ?)",
        (session_id, event_type, data.get("page", ""), str(data.get("event_data", "")))
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin/gencode", methods=["POST"])
def gen_code():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json() or {}
    prefix = (data.get("prefix") or "BETA").upper()
    code = f"{prefix}-{uuid.uuid4().hex[:4].upper()}"
    conn = get_db()
    conn.execute(
        "INSERT INTO invite_codes (code, role, source_tag, campaign, issued_to, max_uses) VALUES (?, ?, ?, ?, ?, ?)",
        (code, data.get("role", "beta"), data.get("source_tag", ""), data.get("campaign", ""), data.get("issued_to", ""), int(data.get("max_uses", 25)))
    )
    conn.commit()
    conn.close()
    sync_to_mobile_auth(code, data.get("role", "beta"))
    return jsonify({"success": True, "code": code})


@app.route("/api/admin/codes", methods=["GET"])
def list_codes():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    rows = conn.execute(
        "SELECT code, role, use_count, max_uses, is_active, source_tag, issued_to, created_at FROM invite_codes ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/admin/revoke", methods=["POST"])
def revoke():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 403
    data = request.get_json() or {}
    code = (data.get("code") or "").strip().upper()
    conn = get_db()
    conn.execute("UPDATE invite_codes SET is_active = 0 WHERE code = ?", (code,))
    conn.execute("UPDATE code_sessions SET is_active = 0 WHERE invite_code = ?", (code,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "revoked": code})


@app.route("/api/admin/sessions", methods=["GET"])
def list_sessions():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    rows = conn.execute(
        "SELECT session_id, invite_code, created_at, last_seen, country, city, is_active FROM code_sessions ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])



# -- COHORT ANALYTICS ---------------------------------------------------------

@app.route("/api/admin/cohort/summary", methods=["GET"])
def cohort_summary():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()

    rows = conn.execute("""
        SELECT
            c.code,
            c.role,
            c.source_tag,
            c.campaign,
            c.issued_to,
            c.use_count,
            c.max_uses,
            c.is_active,
            c.created_at,
            COUNT(DISTINCT s.session_id)                          AS total_sessions,
            COUNT(DISTINCT CASE
                WHEN s.last_seen > datetime('now', '-7 days')
                THEN s.session_id END)                            AS active_7d,
            COUNT(DISTINCT CASE
                WHEN s.last_seen > datetime('now', '-1 day')
                THEN s.session_id END)                            AS active_24h,
            MAX(s.last_seen)                                      AS last_activity,
            COUNT(e.id)                                           AS total_events,
            COUNT(DISTINCT CASE
                WHEN e.event_type = 'screen_view'
                THEN e.session_id END)                            AS sessions_with_navigation,
            COUNT(DISTINCT CASE
                WHEN e.event_type = 'session_resume'
                THEN e.session_id END)                            AS returning_sessions
        FROM invite_codes c
        LEFT JOIN code_sessions s ON s.invite_code = c.code
        LEFT JOIN session_events e ON e.session_id = s.session_id
        GROUP BY c.code
        ORDER BY total_events DESC
    """).fetchall()

    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/admin/cohort/sessions", methods=["GET"])
def cohort_sessions():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 403

    code = request.args.get("code", "")
    conn = get_db()

    query = """
        SELECT
            s.session_id,
            s.invite_code,
            s.created_at,
            s.last_seen,
            s.country,
            s.city,
            s.is_active,
            COUNT(e.id)                             AS total_events,
            MAX(CASE WHEN e.event_type = 'heartbeat'
                THEN e.ts END)                      AS last_heartbeat,
            COUNT(DISTINCT e.event_type)            AS unique_event_types,
            GROUP_CONCAT(DISTINCT e.event_type)     AS event_types_seen
        FROM code_sessions s
        LEFT JOIN session_events e ON e.session_id = s.session_id
        WHERE (? = '' OR s.invite_code = ?)
        GROUP BY s.session_id
        ORDER BY s.last_seen DESC
        LIMIT 200
    """

    rows = conn.execute(query, (code, code)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/admin/cohort/retention", methods=["GET"])
def cohort_retention():
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()

    rows = conn.execute("""
        SELECT
            c.source_tag,
            c.campaign,
            c.role,
            COUNT(DISTINCT s.session_id)                          AS total_sessions,
            COUNT(DISTINCT CASE
                WHEN s.last_seen > datetime('now', '-1 day')
                THEN s.session_id END)                            AS retained_24h,
            COUNT(DISTINCT CASE
                WHEN s.last_seen > datetime('now', '-7 days')
                THEN s.session_id END)                            AS retained_7d,
            COUNT(DISTINCT CASE
                WHEN s.last_seen > datetime('now', '-30 days')
                THEN s.session_id END)                            AS retained_30d,
            ROUND(
                COUNT(DISTINCT CASE
                    WHEN s.last_seen > datetime('now', '-7 days')
                    THEN s.session_id END) * 100.0 /
                NULLIF(COUNT(DISTINCT s.session_id), 0), 1
            )                                                     AS retention_7d_pct
        FROM invite_codes c
        LEFT JOIN code_sessions s ON s.invite_code = c.code
        GROUP BY c.source_tag, c.campaign, c.role
        ORDER BY retained_7d DESC
    """).fetchall()

    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/admin/cohort/ghosts", methods=["GET"])
def cohort_ghosts():
    """Sessions that logged in once and never returned."""
    if not require_admin():
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()

    rows = conn.execute("""
        SELECT
            s.session_id,
            s.invite_code,
            c.source_tag,
            c.issued_to,
            s.country,
            s.created_at,
            s.last_seen,
            COUNT(e.id) AS total_events
        FROM code_sessions s
        JOIN invite_codes c ON s.invite_code = c.code
        LEFT JOIN session_events e ON e.session_id = s.session_id
        WHERE s.last_seen < datetime('now', '-2 days')
        GROUP BY s.session_id
        HAVING COUNT(DISTINCT CASE
            WHEN e.event_type = 'session_resume'
            THEN e.id END) = 0
        ORDER BY s.created_at DESC
    """).fetchall()

    conn.close()
    return jsonify([dict(r) for r in rows])


@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({
        "success": False,
        "error": "Too many requests â slow down"
    }), 429


@app.route("/api/health", methods=["GET"])
def health():
    try:
        conn = get_db()
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except:
        db_ok = False
    return jsonify({
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "ts": datetime.datetime.utcnow().isoformat()
    })


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5002)
