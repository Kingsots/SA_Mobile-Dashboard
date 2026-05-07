#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║     SILENT ANALYST — MOBILE API                                  ║
║     OptiCore Labs · mobile_api.py · Crypto Instance             ║
║     Deploy: OCA EC2 (54.221.93.82) · Port 5001                  ║
╚══════════════════════════════════════════════════════════════════╝

Standalone Flask service. Serves:
  /                      → mobile dashboard HTML (static)
  POST /api/mobile/auth  → validate invite code
  GET  /api/mobile/board → overview KPIs + active signal cards
  GET  /api/mobile/signals → signal log (active + closed)
  GET  /api/mobile/watchlist → per-symbol state grouping
  GET  /api/mobile/asset/<ticker> → deep view per asset
  GET  /api/mobile/stats → profile aggregate stats
  POST /api/mobile/admin/generate → create invite code (admin only)

Deploy:
  pip install flask --break-system-packages
  python3 mobile_api.py

Or register with PM2:
  pm2 start mobile_api.py --name sa-mobile --interpreter python3
"""

import os
import sqlite3
import secrets
import string
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory

# ─────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────

SA_DB_PATH   = os.environ.get("SA_DB_PATH",   "/home/ubuntu/SilentAnalyst/trading_bot.db")
AUTH_DB_PATH = os.environ.get("AUTH_DB_PATH", "/home/ubuntu/SilentAnalyst/mobile_auth.db")
STATIC_DIR   = os.path.dirname(os.path.abspath(__file__))
PORT         = int(os.environ.get("MOBILE_PORT", 5001))
DEBUG        = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

# Hardcoded admin codes — change before production
ADMIN_CODES = {
    "OPTICORE-ADMIN-2026",
    "SA-MASTER-KEY",
}

# Dynamic symbol list is derived from `active_watchlist` at runtime.
# Use `get_active_symbols()` to retrieve the current symbol set.

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger("mobile_api")

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────────
# AUTH DATABASE
# ─────────────────────────────────────────────────────────────────

def get_auth_db():
    conn = sqlite3.connect(AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invite_codes (
            code        TEXT PRIMARY KEY,
            tier        TEXT NOT NULL DEFAULT 'user',
            created_at  TEXT NOT NULL,
            expires_at  TEXT,
            is_active   INTEGER NOT NULL DEFAULT 1,
            label       TEXT
        )
    """)
    conn.commit()
    return conn


def get_sa_db():
    conn = sqlite3.connect(SA_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=3000;")
    return conn


def get_active_symbols():
    """Pull live symbol list from active_watchlist table."""
    try:
        conn = get_sa_db()
        rows = conn.execute(
            "SELECT symbol FROM active_watchlist ORDER BY added_at DESC"
        ).fetchall()
        conn.close()
        syms = [r["symbol"] for r in rows] if rows else []
        # Always keep the four baseline anchors
        for base in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]:
            if base not in syms:
                syms.insert(0, base)
        return syms
    except Exception:
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


def validate_code(code: str) -> dict | None:
    """
    Returns {tier, expires_at} if valid, None if not.
    Admin codes bypass DB — they never expire.
    """
    if not code:
        return None

    code = code.strip().upper()

    if code in ADMIN_CODES:
        return {"tier": "admin", "expires_at": None}

    try:
        conn = get_auth_db()
        row = conn.execute("""
            SELECT tier, expires_at, is_active FROM invite_codes
            WHERE code = ?
        """, (code,)).fetchone()
        conn.close()

        if not row or not row["is_active"]:
            return None

        if row["expires_at"]:
            expiry = datetime.fromisoformat(row["expires_at"])
            if datetime.utcnow() > expiry:
                return None

        return {"tier": row["tier"], "expires_at": row["expires_at"]}
    except Exception as e:
        log.error(f"Auth DB error: {e}")
        return None


def require_auth(f):
    """Decorator — validates X-Invite-Code header on every protected route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        code = request.headers.get("X-Invite-Code", "").strip()
        identity = validate_code(code)
        if not identity:
            return jsonify({"error": "invalid_code", "message": "Invalid or expired invite code"}), 401
        request.identity = identity
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        code = request.headers.get("X-Invite-Code", "").strip()
        identity = validate_code(code)
        if not identity or identity["tier"] != "admin":
            return jsonify({"error": "forbidden"}), 403
        request.identity = identity
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────────────────────────
# CORS — allow all origins for mobile access
# ─────────────────────────────────────────────────────────────────

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Invite-Code"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/api/mobile/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return "", 204


# ─────────────────────────────────────────────────────────────────
# AUTH ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/auth", methods=["POST"])
def auth():
    # Structured logging only: record an auth attempt without raw payloads
    try:
        log.info(f"Auth attempt from {request.remote_addr}")
    except Exception:
        log.info("Auth attempt")

    body = request.get_json(silent=True) or {}
    code = body.get("code", "").strip().upper()
    identity = validate_code(code)
    if not identity:
        log.warning(f"Failed auth attempt for code: {code[:8]}***")
        return jsonify({"valid": False, "message": "Invalid or expired invite code"}), 401
    log.info(f"Auth success  tier={identity['tier']}")
    return jsonify({"valid": True, "tier": identity["tier"], "expires_at": identity["expires_at"]})


@app.route("/api/mobile/admin/generate", methods=["POST"])
@require_admin
def generate_code():
    """Generate a new invite code with configurable expiry."""
    body    = request.get_json(silent=True) or {}
    hours   = int(body.get("expires_hours", 72))
    label   = body.get("label", "")
    tier    = body.get("tier", "user")

    alphabet = string.ascii_uppercase + string.digits
    code = "SA-" + "".join(secrets.choice(alphabet) for _ in range(8))
    now  = datetime.utcnow()
    exp  = (now + timedelta(hours=hours)).isoformat()

    conn = get_auth_db()
    conn.execute("""
        INSERT INTO invite_codes (code, tier, created_at, expires_at, label)
        VALUES (?, ?, ?, ?, ?)
    """, (code, tier, now.isoformat(), exp, label))
    conn.commit()
    conn.close()

    log.info(f"Generated code {code}  tier={tier}  expires={exp}  label={label}")
    return jsonify({"code": code, "tier": tier, "expires_at": exp, "label": label})


# ─────────────────────────────────────────────────────────────────
# HELPERS — query SA DB
# ─────────────────────────────────────────────────────────────────

def _now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _fmt_age(ts_str: str) -> str:
    if not ts_str:
        return "—"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            ts = datetime.strptime(ts_str[:26], fmt)
            delta = _now_utc() - ts
            mins = int(delta.total_seconds() / 60)
            if mins < 60:
                return f"{mins}m ago"
            return f"{mins // 60}h {mins % 60}m ago"
        except ValueError:
            continue
    return "—"

def _direction_label(signal: int) -> str:
    return "BUY" if signal == 1 else "SELL" if signal == -1 else "—"

def _result_pct(entry, exit_price, direction):
    if not entry or entry == 0:
        return 0.0
    if direction == 1:
        return round((exit_price - entry) / entry * 100, 3)
    return round((entry - exit_price) / entry * 100, 3)


def _signal_state(row) -> str:
    """
    Classify a signal row into a watchlist state for the UI.
    TRENDING  = active, TP direction
    EMERGING  = active, not yet decisive
    EXHAUSTED = last outcome SL_HIT
    EXTENDED  = last outcome TP_HIT
    """
    outcome = row["outcome"] if row["outcome"] else ""
    if outcome == "TP_HIT":
        return "EXTENDED"
    if outcome == "SL_HIT":
        return "EXHAUSTED"
    if not outcome:
        return "TRENDING"
    return "EMERGING"


# ─────────────────────────────────────────────────────────────────
# BOARD ENDPOINT
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/board")
@require_auth
def board():
    try:
        conn = get_sa_db()

        # ── KPI stats (last 30 days) ────────────────────────────
        stats = conn.execute("""
            SELECT
                COUNT(CASE WHEN outcome='TP_HIT' THEN 1 END)   AS tp_count,
                COUNT(CASE WHEN outcome='SL_HIT' THEN 1 END)   AS sl_count,
                COUNT(CASE WHEN outcome IS NULL  THEN 1 END)   AS active_count,
                COUNT(*)                                         AS total,
                AVG(CASE WHEN result_pct IS NOT NULL THEN result_pct END) AS avg_pnl
            FROM ml_signals
            WHERE created_at > datetime('now', '-30 days')
        """).fetchone()

        resolved = (stats["tp_count"] or 0) + (stats["sl_count"] or 0)
        win_rate = round(stats["tp_count"] / resolved * 100, 1) if resolved > 0 else 0.0

        # ── Average R:R from open signals ──────────────────────
        rr_row = conn.execute(f"""
            SELECT AVG(
                CASE WHEN signal=1 AND entry_price>0 AND stop_loss>0 AND take_profit>0
                     THEN (take_profit - entry_price) / (entry_price - stop_loss)
                WHEN signal=-1 AND entry_price>0 AND stop_loss>0 AND take_profit>0
                     THEN (entry_price - take_profit) / (stop_loss - entry_price)
                END
            ) AS avg_rr
            FROM ml_signals
            WHERE created_at > datetime('now', '-30 days')
              AND outcome IS NULL
        """).fetchone()

        # ── Active signal cards ─────────────────────────────────
        active_rows = conn.execute("""
            SELECT ticker, interval, signal, entry_price,
                   stop_loss, take_profit, strategy_version, created_at
            FROM ml_signals
            WHERE outcome IS NULL
            ORDER BY created_at DESC
            LIMIT 8
        """).fetchall()

        # ── Latest signal price for "current P&L" estimate ─────
        latest_prices = {}
        for row in active_rows:
            ticker = row["ticker"]
            if ticker not in latest_prices:
                p = conn.execute("""
                    SELECT close FROM ohlcv_data
                    WHERE symbol=? ORDER BY timestamp DESC LIMIT 1
                """, (ticker,)).fetchone()
                if p:
                    latest_prices[ticker] = float(p["close"])

        conn.close()

        active_cards = []
        for r in active_rows:
            latest = latest_prices.get(r["ticker"], r["entry_price"])
            running_pct = _result_pct(r["entry_price"], latest, r["signal"])
            active_cards.append({
                "ticker":    r["ticker"],
                "interval":  r["interval"],
                "direction": _direction_label(r["signal"]),
                "entry":     r["entry_price"],
                "sl":        r["stop_loss"],
                "tp":        r["take_profit"],
                "strategy":  r["strategy_version"] or "v3",
                "age":       _fmt_age(r["created_at"]),
                "running_pct": round(running_pct, 2),
            })

        return jsonify({
            "win_rate":      win_rate,
            "active_count":  stats["active_count"] or 0,
            "resolved":      resolved,
            "avg_pnl":       round(stats["avg_pnl"] or 0, 2),
            "avg_rr":        round(rr_row["avg_rr"] or 0, 2),
            "active_cards":  active_cards,
            "refreshed_at":  _now_utc().strftime("%H:%M:%S UTC"),
        })

    except Exception as e:
        log.error(f"/board error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# SIGNALS ENDPOINT
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/signals")
@require_auth
def signals():
    try:
        conn = get_sa_db()

        active = conn.execute("""
            SELECT id, ticker, interval, signal, entry_price,
                   stop_loss, take_profit, strategy_version, created_at
            FROM ml_signals
            WHERE outcome IS NULL
            ORDER BY created_at DESC
            LIMIT 20
        """).fetchall()

        closed = conn.execute("""
            SELECT id, ticker, interval, signal, entry_price,
                   stop_loss, take_profit, outcome, result_pct,
                   strategy_version, created_at, closed_at
            FROM ml_signals
            WHERE outcome IS NOT NULL AND outcome != ''
            ORDER BY closed_at DESC
            LIMIT 30
        """).fetchall()

        # Latest prices for running P&L on active signals
        tickers = {r["ticker"] for r in active}
        prices  = {}
        for t in tickers:
            p = conn.execute(
                "SELECT close FROM ohlcv_data WHERE symbol=? ORDER BY timestamp DESC LIMIT 1", (t,)
            ).fetchone()
            if p:
                prices[t] = float(p["close"])

        conn.close()

        def fmt_active(r):
            latest = prices.get(r["ticker"], r["entry_price"])
            running = _result_pct(r["entry_price"], latest, r["signal"])
            return {
                "id": r["id"], "ticker": r["ticker"],
                "interval": r["interval"],
                "direction": _direction_label(r["signal"]),
                "entry": r["entry_price"], "sl": r["stop_loss"], "tp": r["take_profit"],
                "running_pct": round(running, 2),
                "strategy": r["strategy_version"] or "v3",
                "age": _fmt_age(r["created_at"]),
                "status": "RUNNING",
            }

        def fmt_closed(r):
            return {
                "id": r["id"], "ticker": r["ticker"],
                "interval": r["interval"],
                "direction": _direction_label(r["signal"]),
                "entry": r["entry_price"], "sl": r["stop_loss"], "tp": r["take_profit"],
                "outcome": r["outcome"],
                "result_pct": round(r["result_pct"] or 0, 2),
                "strategy": r["strategy_version"] or "v3",
                "age": _fmt_age(r["closed_at"] or r["created_at"]),
            }

        return jsonify({
            "active": [fmt_active(r) for r in active],
            "closed": [fmt_closed(r) for r in closed],
        })

    except Exception as e:
        log.error(f"/signals error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# WATCHLIST ENDPOINT
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/watchlist")
@require_auth
def watchlist():
    try:
        conn = get_sa_db()

        groups = {"TRENDING": [], "EMERGING": [], "EXHAUSTED": [], "EXTENDED": []}

        for ticker in get_active_symbols():
            row = conn.execute("""
                SELECT ticker, interval, signal, entry_price,
                       outcome, result_pct, created_at, strategy_version
                FROM ml_signals
                WHERE ticker = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (ticker,)).fetchone()

            if not row:
                continue

            state = _signal_state(row)
            groups[state].append({
                "ticker":    ticker,
                "direction": _direction_label(row["signal"]),
                "interval":  row["interval"],
                "result_pct": round(row["result_pct"] or 0, 2) if row["result_pct"] else None,
                "age":       _fmt_age(row["created_at"]),
                "strategy":  row["strategy_version"] or "v3",
            })

        conn.close()
        return jsonify(groups)

    except Exception as e:
        log.error(f"/watchlist error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/mobile/context/<ticker>")
@require_auth
def asset_context(ticker):
    """Latest context_log entry for a ticker — feeds deep view intel panel."""
    try:
        conn = get_sa_db()
        row = conn.execute("""
            SELECT ticker, interval, timestamp,
                   compression_score, expansion_pressure,
                   rsi_stage, liquidity_type, distance_to_liquidity,
                   liquidity_sweep, created_at
            FROM context_log
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (ticker.upper(),)).fetchone()
        conn.close()
        if not row:
            return jsonify({"context": None})
        return jsonify({"context": dict(row)})
    except Exception as e:
        log.error(f"/context/{ticker} error: {e}")
        return jsonify({"context": None}), 500


# ─────────────────────────────────────────────────────────────────
# ASSET DEEP VIEW
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/asset/<ticker>")
@require_auth
def asset(ticker):
    ticker = ticker.upper()
    if ticker not in get_active_symbols():
        return jsonify({"error": "unknown_ticker"}), 404

    try:
        conn = get_sa_db()

        # Latest signal
        sig = conn.execute("""
            SELECT id, ticker, interval, signal, entry_price, stop_loss,
                   take_profit, outcome, result_pct, strategy_version,
                   created_at, closed_at
            FROM ml_signals
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (ticker,)).fetchone()

        # Latest price
        price_row = conn.execute("""
            SELECT close FROM ohlcv_data WHERE symbol=? ORDER BY timestamp DESC LIMIT 1
        """, (ticker,)).fetchone()
        latest_close = float(price_row["close"]) if price_row else None

        # Forensics (V3 context metrics)
        try:
            forensics = conn.execute("""
                SELECT confluence_score, ema21, rsi14, compression,
                       sl_distance_pips, tp_distance_pips, adx_slope_ok
                FROM signal_forensics
                WHERE ticker = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (ticker,)).fetchone()
        except sqlite3.OperationalError as oe:
            log.warning(f"/asset/{ticker} forensics query missing column or table: {oe}")
            forensics = None

        # Signal history (last 5 resolved)
        history = conn.execute("""
            SELECT interval, signal, result_pct, outcome, created_at
            FROM ml_signals
            WHERE ticker=? AND outcome IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 5
        """, (ticker,)).fetchall()

        conn.close()

        running_pct = None
        if sig and not sig["outcome"] and latest_close and sig["entry_price"]:
            running_pct = round(_result_pct(sig["entry_price"], latest_close, sig["signal"]), 2)

        return jsonify({
            "ticker": ticker,
            "latest_close": latest_close,
            "signal": {
                "direction":  _direction_label(sig["signal"]) if sig else None,
                "interval":   sig["interval"] if sig else None,
                "entry":      sig["entry_price"] if sig else None,
                "sl":         sig["stop_loss"] if sig else None,
                "tp":         sig["take_profit"] if sig else None,
                "outcome":    sig["outcome"] if sig else None,
                "result_pct": round(sig["result_pct"] or 0, 2) if sig and sig["result_pct"] else running_pct,
                "strategy":   sig["strategy_version"] if sig else None,
                "age":        _fmt_age(sig["created_at"]) if sig else None,
                "status":     sig["outcome"] or "RUNNING",
            } if sig else None,
            "forensics": {
                "confluence":    forensics["confluence_score"] if forensics else None,
                "ema21":         round(forensics["ema21"], 4) if forensics and forensics["ema21"] else None,
                "rsi14":         round(forensics["rsi14"], 1) if forensics and forensics["rsi14"] else None,
                "compression":   round(forensics["compression"], 3) if forensics and forensics["compression"] else None,
                "sl_pips":       forensics["sl_distance_pips"] if forensics else None,
                "tp_pips":       forensics["tp_distance_pips"] if forensics else None,
                "adx_ok":        bool(forensics["adx_slope_ok"]) if forensics else None,
            } if forensics else None,
            "history": [
                {
                    "interval":   r["interval"],
                    "direction":  _direction_label(r["signal"]),
                    "result_pct": round(r["result_pct"] or 0, 2),
                    "outcome":    r["outcome"],
                    "age":        _fmt_age(r["created_at"]),
                } for r in history
            ],
        })

    except Exception as e:
        log.error(f"/asset/{ticker} error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# STATS (Profile screen)
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/stats")
@require_auth
def stats():
    try:
        conn = get_sa_db()

        row = conn.execute("""
            SELECT
                COUNT(*)  AS total,
                COUNT(CASE WHEN outcome='TP_HIT' THEN 1 END) AS wins,
                COUNT(CASE WHEN outcome='SL_HIT' THEN 1 END) AS losses,
                COUNT(CASE WHEN outcome IS NULL  THEN 1 END) AS active,
                AVG(CASE WHEN result_pct IS NOT NULL THEN result_pct END) AS avg_pnl,
                MAX(CASE WHEN outcome='TP_HIT' THEN result_pct END) AS best_trade
            FROM ml_signals
        """).fetchone()

        resolved = (row["wins"] or 0) + (row["losses"] or 0)
        win_rate = round(row["wins"] / resolved * 100, 1) if resolved > 0 else 0

        conn.close()

        return jsonify({
            "total_signals": row["total"] or 0,
            "win_rate":      win_rate,
            "active":        row["active"] or 0,
            "wins":          row["wins"] or 0,
            "losses":        row["losses"] or 0,
            "avg_pnl":       round(row["avg_pnl"] or 0, 2),
            "best_trade":    round(row["best_trade"] or 0, 2),
            "engine":        "SA·3",
            "version":       "Build 0506.26",
        })

    except Exception as e:
        log.error(f"/stats error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# DATA CONTRACTS  ← single source of truth for all endpoint shapes
# Frontend reads /api/mobile/contracts and validates against these.
# Any field added to an endpoint MUST be added here first.
# ─────────────────────────────────────────────────────────────────

CONTRACTS = {
    "version": "1.0.0",
    "generated": "2026-05-06",
    "endpoints": {

        "POST /api/mobile/auth": {
            "request":  {"code": "string"},
            "response": {
                "valid":      "boolean",
                "tier":       "string: 'admin' | 'user'",
                "expires_at": "string | null  — ISO UTC",
            },
        },

        "GET /api/mobile/board": {
            "auth": "X-Invite-Code header required",
            "response": {
                "win_rate":     "number  — % of TP_HIT vs resolved, 0–100",
                "active_count": "number  — signals with outcome=null",
                "resolved":     "number  — TP_HIT + SL_HIT count",
                "avg_pnl":      "number  — mean result_pct across resolved signals",
                "avg_rr":       "number  — mean risk:reward of open signals",
                "refreshed_at": "string  — HH:MM:SS UTC display label",
                "active_cards": {
                    "_type":       "array",
                    "_item": {
                        "ticker":      "string",
                        "interval":    "string: '30m'|'1h'|'2h'|'4h'",
                        "direction":   "string: 'BUY'|'SELL'",
                        "entry":       "number",
                        "sl":          "number",
                        "tp":          "number",
                        "running_pct": "number  — live P&L % from entry",
                        "strategy":    "string: 'v1'|'v2'|'v3'",
                        "age":         "string  — display label e.g. '14m ago'",
                    },
                },
            },
        },

        "GET /api/mobile/signals": {
            "auth": "X-Invite-Code header required",
            "response": {
                "active": {
                    "_type": "array",
                    "_item": {
                        "id":          "number",
                        "ticker":      "string",
                        "interval":    "string",
                        "direction":   "string: 'BUY'|'SELL'",
                        "entry":       "number",
                        "sl":          "number",
                        "tp":          "number",
                        "running_pct": "number",
                        "strategy":    "string",
                        "age":         "string",
                        "status":      "string: 'RUNNING'",
                    },
                },
                "closed": {
                    "_type": "array",
                    "_item": {
                        "id":         "number",
                        "ticker":     "string",
                        "interval":   "string",
                        "direction":  "string: 'BUY'|'SELL'",
                        "entry":      "number",
                        "sl":         "number",
                        "tp":         "number",
                        "outcome":    "string: 'TP_HIT'|'SL_HIT'|'EXPIRY'",
                        "result_pct": "number  — negative = loss",
                        "strategy":   "string",
                        "age":        "string",
                    },
                },
            },
        },

        "GET /api/mobile/watchlist": {
            "auth": "X-Invite-Code header required",
            "response": {
                "TRENDING":  "_watchlist_group",
                "EMERGING":  "_watchlist_group",
                "EXHAUSTED": "_watchlist_group",
                "EXTENDED":  "_watchlist_group",
                "_watchlist_group": {
                    "_type": "array",
                    "_item": {
                        "ticker":     "string",
                        "direction":  "string: 'BUY'|'SELL'",
                        "interval":   "string",
                        "result_pct": "number | null",
                        "age":        "string",
                        "strategy":   "string",
                    },
                },
            },
        },

        "GET /api/mobile/asset/<ticker>": {
            "auth": "X-Invite-Code header required",
            "response": {
                "ticker":       "string",
                "latest_close": "number | null",
                "signal": {
                    "_nullable": True,
                    "direction":  "string: 'BUY'|'SELL'",
                    "interval":   "string",
                    "entry":      "number",
                    "sl":         "number",
                    "tp":         "number",
                    "outcome":    "string | null",
                    "result_pct": "number | null",
                    "strategy":   "string",
                    "age":        "string",
                    "status":     "string: 'RUNNING'|'TP_HIT'|'SL_HIT'|'EXPIRY'",
                },
                "forensics": {
                    "_nullable": True,
                    "confluence":  "number | null  — V3 confluence score",
                    "ema21":       "number | null",
                    "rsi14":       "number | null",
                    "compression": "number | null  — ATR compression ratio",
                    "sl_pips":     "number | null",
                    "tp_pips":     "number | null",
                    "adx_ok":      "boolean | null",
                },
                "history": {
                    "_type": "array",
                    "_item": {
                        "interval":   "string",
                        "direction":  "string",
                        "result_pct": "number",
                        "outcome":    "string",
                        "age":        "string",
                    },
                },
            },
        },

        "GET /api/mobile/stats": {
            "auth": "X-Invite-Code header required",
            "response": {
                "total_signals": "number",
                "win_rate":      "number  — 0 to 100",
                "active":        "number",
                "wins":          "number",
                "losses":        "number",
                "avg_pnl":       "number",
                "best_trade":    "number",
                "engine":        "string  — display label",
                "version":       "string  — build label",
            },
        },

        "GET /api/mobile/system/context": {
            "auth": "X-Invite-Code header required",
            "response": {
                "total":        "number — active watchlist symbol count",
                "state_counts": "object — {TRENDING: n, EMERGING: n, ...}",
                "refreshed_at": "string",
                "assets": {
                    "_type": "array",
                    "_item": {
                        "symbol":       "string",
                        "direction":    "string: 'long'|'short'|'baseline'",
                        "change_pct":   "number",
                        "atr_pct":      "number",
                        "market_state": "string: TRENDING|EMERGING|COMPRESSION|EXHAUSTED|NEUTRAL",
                        "context": {
                            "_nullable":    True,
                            "compression":  "number|null — 0.0 to 1.2+",
                            "expansion":    "number|null — 0.0 to 1.0",
                            "rsi_stage":    "string|null — NEUTRAL|1A|1B|etc",
                            "sweep":        "boolean",
                            "scanned_at":   "string — ISO UTC",
                        },
                        "signal": "_signal_item | null",
                    },
                },
            },
        },

        "GET /api/mobile/resolver/feed": {
            "auth": "X-Invite-Code header required",
            "response": {
                "feed": {
                    "_type": "array",
                    "_item": {
                        "ticker":     "string",
                        "interval":   "string",
                        "direction":  "string: 'BUY'|'SELL'",
                        "outcome":    "string: 'TP_HIT'|'SL_HIT'|'EXPIRY'",
                        "result_pct": "number — negative for losses",
                        "duration":   "string — hold time display e.g. '4h 20m'",
                        "age":        "string — time since closed",
                    },
                },
                "stats": {
                    "win_rate":   "number 0-100",
                    "total":      "number",
                    "wins":       "number",
                    "losses":     "number",
                    "best_trade": "number",
                    "avg_result": "number",
                },
            },
        },

        "GET /api/mobile/watchlist/live": {
            "auth": "X-Invite-Code header required",
            "response": {
                "total":   "number",
                "counts":  "object — state group counts",
                "groups": {
                    "TRENDING":    "_watchlist_asset_array",
                    "EMERGING":    "_watchlist_asset_array",
                    "COMPRESSION": "_watchlist_asset_array",
                    "EXHAUSTED":   "_watchlist_asset_array",
                    "NEUTRAL":     "_watchlist_asset_array",
                },
            },
        },

        "GET /api/mobile/audit/system": {
            "auth": "Admin X-Invite-Code required",
            "response": {
                "status":    "string: 'PASS'|'WARN'|'FAIL'",
                "timestamp": "string  — ISO UTC",
                "summary":   {"pass": "number", "warn": "number", "fail": "number"},
                "checks": {
                    "_type": "array",
                    "_item": {
                        "name":        "string",
                        "status":      "string: 'PASS'|'WARN'|'FAIL'",
                        "value":       "string | number | null",
                        "detail":      "string",
                        "age_minutes": "number | null  — raw integer for logic",
                        "age_label":   "string | null  — display string",
                    },
                },
            },
        },

        "GET /api/mobile/audit/data": {
            "auth": "Admin X-Invite-Code required",
            "note": "Per-ticker OHLCV freshness. age_minutes is always an integer.",
        },

        "GET /api/mobile/audit/engines": {
            "auth": "Admin X-Invite-Code required",
            "note": "Per-engine signal counts, fire recency, win rates.",
        },

        "GET /api/mobile/audit/integrity": {
            "auth": "Admin X-Invite-Code required",
            "note": "DB integrity: UNIQUE INDEX, duplicates, null trade levels.",
        },
    },
}


@app.route("/api/mobile/contracts")
@require_auth
def contracts():
    return jsonify(CONTRACTS)


# ─────────────────────────────────────────────────────────────────
# AUDIT HELPERS
# ─────────────────────────────────────────────────────────────────

def _age_fields(ts_str: str | None) -> dict:
    """
    Returns both age_minutes (int, usable in logic) and
    age_label (string, usable in display). Never conflate them.
    """
    if not ts_str:
        return {"age_minutes": None, "age_label": "—"}
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            ts = datetime.strptime(ts_str[:26], fmt)
            mins = int((_now_utc() - ts).total_seconds() / 60)
            if mins < 60:
                label = f"{mins}m ago"
            else:
                label = f"{mins // 60}h {mins % 60}m ago"
            return {"age_minutes": mins, "age_label": label}
        except ValueError:
            continue
    return {"age_minutes": None, "age_label": "parse error"}


def _check(name: str, status: str, value, detail: str = "",
           age_minutes: int | None = None,
           age_label: str | None = None) -> dict:
    return {
        "name":        name,
        "status":      status,  # PASS | WARN | FAIL
        "value":       value,
        "detail":      detail,
        "age_minutes": age_minutes,
        "age_label":   age_label,
    }


def _audit_envelope(checks: list) -> dict:
    summary = {
        "pass": sum(1 for c in checks if c["status"] == "PASS"),
        "warn": sum(1 for c in checks if c["status"] == "WARN"),
        "fail": sum(1 for c in checks if c["status"] == "FAIL"),
    }
    overall = "FAIL" if summary["fail"] > 0 else "WARN" if summary["warn"] > 0 else "PASS"
    return {
        "status":    overall,
        "timestamp": _now_utc().isoformat(),
        "summary":   summary,
        "checks":    checks,
    }


# ─────────────────────────────────────────────────────────────────
# AUDIT — SYSTEM  (tables, DB health, signal flow, engine mix)
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/audit/system")
@require_admin
def audit_system():
    try:
        conn = get_sa_db()
        checks = []

        # 1. Required tables present
        existing = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        required = {"ml_signals", "ohlcv_data", "signal_forensics",
                    "strategy_state_v2", "strategy_state_v3"}
        missing  = required - existing
        checks.append(_check(
            "required_tables",
            "PASS" if not missing else "FAIL",
            f"{len(required) - len(missing)}/{len(required)} present",
            f"Missing: {sorted(missing)}" if missing else "All required tables confirmed",
        ))

        # 2. DB integrity
        integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        checks.append(_check(
            "db_integrity",
            "PASS" if integrity == "ok" else "FAIL",
            integrity,
            "SQLite PRAGMA integrity_check result",
        ))

        # 3. Signal flow health
        sig = conn.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN outcome IS NULL THEN 1 END) as active,
                   COUNT(CASE WHEN outcome='TP_HIT' THEN 1 END) as wins,
                   COUNT(CASE WHEN outcome='SL_HIT' THEN 1 END) as losses,
                   MAX(created_at) as last_ts
            FROM ml_signals
        """).fetchone()
        age = _age_fields(sig["last_ts"])
        checks.append(_check(
            "signal_flow",
            "PASS" if (sig["total"] or 0) > 0 else "FAIL",
            f"total={sig['total']} active={sig['active']} wins={sig['wins']} losses={sig['losses']}",
            f"Last signal: {sig['last_ts']}",
            age_minutes=age["age_minutes"],
            age_label=age["age_label"],
        ))

        # 4. Last signal staleness
        mins = age["age_minutes"]
        if mins is None:
            stale_status = "FAIL"
        elif mins < 120:
            stale_status = "PASS"
        elif mins < 360:
            stale_status = "WARN"
        else:
            stale_status = "FAIL"
        checks.append(_check(
            "signal_staleness",
            stale_status,
            age["age_label"],
            "WARN > 2h, FAIL > 6h since last signal",
            age_minutes=mins,
            age_label=age["age_label"],
        ))

        # 5. Engine distribution
        engines = conn.execute("""
            SELECT strategy_version, COUNT(*) as cnt
            FROM ml_signals GROUP BY strategy_version
        """).fetchall()
        engine_summary = {r["strategy_version"]: r["cnt"] for r in engines}
        checks.append(_check(
            "engine_distribution",
            "PASS",
            str(engine_summary),
            "Signal counts by strategy_version",
        ))

        # 6. Event-only invariant
        violations = conn.execute("""
            SELECT COUNT(*) as cnt FROM ml_signals
            WHERE created_at > datetime('now', '-24 hours')
              AND triggered_by IS NOT NULL
              AND LOWER(triggered_by) NOT IN ('event','event_monitor','eventmonitor')
        """).fetchone()["cnt"]
        checks.append(_check(
            "event_only_invariant",
            "PASS" if violations == 0 else "FAIL",
            f"{violations} violation(s) in last 24h",
            "FAIL = time-based signals present — architectural violation",
        ))

        # 7. OHLCV row count (sanity)
        ohlcv_total = conn.execute(
            "SELECT COUNT(*) as cnt FROM ohlcv_data"
        ).fetchone()["cnt"]
        checks.append(_check(
            "ohlcv_row_count",
            "PASS" if ohlcv_total > 1000 else "WARN",
            f"{ohlcv_total:,} rows",
            "WARN < 1000 rows — data may be incomplete",
        ))

        # 8. signal_forensics population
        forensics_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM signal_forensics"
        ).fetchone()["cnt"]
        checks.append(_check(
            "forensics_coverage",
            "PASS" if forensics_count > 0 else "WARN",
            f"{forensics_count} forensic snapshots",
            "WARN = 0 rows means V3 forensics write path is broken",
        ))

        conn.close()
        return jsonify(_audit_envelope(checks))

    except Exception as e:
        log.error(f"/audit/system error: {e}")
        return jsonify({"status": "ERROR", "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# AUDIT — DATA  (OHLCV freshness per ticker, signal recency)
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/audit/data")
@require_admin
def audit_data():
    try:
        conn = get_sa_db()
        checks = []

        # Per-ticker OHLCV freshness
        for ticker in get_active_symbols():
            row = conn.execute("""
                SELECT MAX(timestamp) as last_ts, COUNT(*) as rows
                FROM ohlcv_data WHERE symbol=?
            """, (ticker,)).fetchone()

            if not row or not row["last_ts"]:
                checks.append(_check(
                    f"ohlcv_{ticker}",
                    "FAIL",
                    "no data",
                    f"{ticker} has no OHLCV rows at all",
                    age_minutes=None,
                    age_label="—",
                ))
                continue

            age  = _age_fields(row["last_ts"])
            mins = age["age_minutes"]

            if mins is None:
                status = "WARN"
            elif mins < 60:
                status = "PASS"
            elif mins < 180:
                status = "WARN"
            else:
                status = "FAIL"

            checks.append(_check(
                f"ohlcv_{ticker}",
                status,
                f"{row['rows']:,} rows",
                f"Last bar: {row['last_ts']}",
                age_minutes=mins,
                age_label=age["age_label"],
            ))

        # Signal coverage per ticker
        no_signals = []
        for ticker in get_active_symbols():
            cnt = conn.execute(
                "SELECT COUNT(*) as cnt FROM ml_signals WHERE ticker=?", (ticker,)
            ).fetchone()["cnt"]
            if cnt == 0:
                no_signals.append(ticker)

        checks.append(_check(
            "signal_coverage",
            "PASS" if not no_signals else "WARN",
            f"{len(CRYPTO_SYMBOLS) - len(no_signals)}/{len(CRYPTO_SYMBOLS)} symbols have signals",
            f"No signals: {no_signals}" if no_signals else "All symbols have at least one signal",
        ))

        # Overall stale ticker count
        stale  = sum(1 for c in checks if c["status"] == "FAIL" and c["name"].startswith("ohlcv_"))
        warned = sum(1 for c in checks if c["status"] == "WARN" and c["name"].startswith("ohlcv_"))
        checks.append(_check(
            "ohlcv_health_summary",
            "FAIL" if stale > 3 else "WARN" if stale > 0 or warned > 3 else "PASS",
            f"{stale} tickers stale  {warned} tickers warned",
            "Stale = no data or > 3h old",
        ))

        conn.close()
        return jsonify(_audit_envelope(checks))

    except Exception as e:
        log.error(f"/audit/data error: {e}")
        return jsonify({"status": "ERROR", "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# AUDIT — ENGINES  (V1/V2/V3 activity, win rates, last fire)
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/audit/engines")
@require_admin
def audit_engines():
    try:
        conn = get_sa_db()
        checks = []

        for version in ["v1", "v2", "v3"]:
            row = conn.execute("""
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN outcome='TP_HIT' THEN 1 END) as wins,
                       COUNT(CASE WHEN outcome='SL_HIT' THEN 1 END) as losses,
                       COUNT(CASE WHEN outcome IS NULL  THEN 1 END) as active,
                       MAX(created_at) as last_fire
                FROM ml_signals
                WHERE strategy_version=?
            """, (version,)).fetchone()

            total    = row["total"] or 0
            resolved = (row["wins"] or 0) + (row["losses"] or 0)
            win_rate = round(row["wins"] / resolved * 100, 1) if resolved > 0 else None
            age      = _age_fields(row["last_fire"])

            status = "PASS" if total > 0 else "WARN"
            # V1 and V3 should be actively firing
            if version in ("v1", "v3") and (age["age_minutes"] or 9999) > 360:
                status = "WARN"

            checks.append(_check(
                f"engine_{version}",
                status,
                f"total={total}  active={row['active']}  "
                f"win_rate={win_rate}%  last={age['age_label']}",
                f"Strategy version: {version}",
                age_minutes=age["age_minutes"],
                age_label=age["age_label"],
            ))

        # 24h engine activity breakdown
        recent = conn.execute("""
            SELECT strategy_version, COUNT(*) as cnt
            FROM ml_signals
            WHERE created_at > datetime('now', '-24 hours')
            GROUP BY strategy_version
        """).fetchall()
        recent_map = {r["strategy_version"]: r["cnt"] for r in recent}
        checks.append(_check(
            "engine_24h_activity",
            "PASS" if sum(recent_map.values()) > 0 else "WARN",
            str(recent_map),
            "Signals generated in the last 24 hours, by engine",
        ))

        # V3 forensics activity
        forensics_24h = conn.execute("""
            SELECT COUNT(*) as cnt FROM signal_forensics
            WHERE timestamp > datetime('now', '-24 hours')
        """).fetchone()["cnt"]
        checks.append(_check(
            "v3_forensics_24h",
            "PASS" if forensics_24h > 0 else "WARN",
            f"{forensics_24h} forensic snapshots in last 24h",
            "WARN = V3 write path may be broken if V3 signals exist but forensics are empty",
        ))

        # V2 state machine health
        try:
            v2_rows = conn.execute(
                "SELECT COUNT(*) as cnt FROM strategy_state_v2"
            ).fetchone()["cnt"]
            checks.append(_check(
                "v2_state_machine",
                "PASS" if v2_rows > 0 else "WARN",
                f"{v2_rows} state rows (V2 on intentional hold)",
                "V2 is stable and paused — state rows confirm persistence is intact",
            ))
        except Exception:
            checks.append(_check("v2_state_machine", "WARN", "table missing", "strategy_state_v2 not found"))

        conn.close()
        return jsonify(_audit_envelope(checks))

    except Exception as e:
        log.error(f"/audit/engines error: {e}")
        return jsonify({"status": "ERROR", "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# AUDIT — INTEGRITY  (dedup, UNIQUE INDEX, null trade levels)
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/audit/integrity")
@require_admin
def audit_integrity():
    try:
        conn = get_sa_db()
        checks = []

        # 1. UNIQUE INDEX on ml_signals (3-layer dedup Layer 1)
        indexes = conn.execute("""
            SELECT name, sql FROM sqlite_master
            WHERE type='index' AND tbl_name='ml_signals'
        """).fetchall()
        unique_found = any(
            "UNIQUE" in (idx["sql"] or "").upper()
            and "TICKER" in (idx["sql"] or "").upper()
            for idx in indexes
        )
        checks.append(_check(
            "unique_index_ml_signals",
            "PASS" if unique_found else "FAIL",
            "present" if unique_found else "MISSING",
            "FAIL = Layer 1 dedup broken. Duplicates can reach Telegram. "
            "Fix: CREATE UNIQUE INDEX idx_ml_signals_dedup ON ml_signals(ticker,interval,timestamp)",
        ))

        # 2. Duplicate rows
        dupes = conn.execute("""
            SELECT COUNT(*) as cnt FROM (
                SELECT ticker, interval, timestamp
                FROM ml_signals
                GROUP BY ticker, interval, timestamp
                HAVING COUNT(*) > 1
            )
        """).fetchone()["cnt"]
        checks.append(_check(
            "duplicate_signals",
            "PASS" if dupes == 0 else "FAIL",
            f"{dupes} duplicate group(s)",
            "Duplicates present despite no UNIQUE INDEX — dedup layers 2/3 also failing" if dupes > 0 else "",
        ))

        # 3. Signals missing required trade levels
        missing_levels = conn.execute("""
            SELECT COUNT(*) as cnt FROM ml_signals
            WHERE (entry_price IS NULL OR entry_price = 0)
               OR (stop_loss   IS NULL OR stop_loss   = 0)
               OR (take_profit IS NULL OR take_profit = 0)
        """).fetchone()["cnt"]
        checks.append(_check(
            "trade_levels_complete",
            "PASS" if missing_levels == 0 else "WARN",
            f"{missing_levels} signal(s) missing entry/SL/TP",
            "These signals cannot be resolved by signal_outcome_resolver",
        ))

        # 4. Broadcasted flag integrity
        total = conn.execute("SELECT COUNT(*) as cnt FROM ml_signals").fetchone()["cnt"]
        unset = conn.execute("""
            SELECT COUNT(*) as cnt FROM ml_signals
            WHERE broadcasted IS NULL OR broadcasted = 0
        """).fetchone()["cnt"]
        pct_set = round((total - unset) / total * 100, 1) if total > 0 else 0
        checks.append(_check(
            "broadcasted_flag",
            "PASS" if unset == 0 else "WARN",
            f"{pct_set}% set  ({total - unset}/{total})",
            "Known open bug: flag not always written after Telegram send. "
            "Dedup pre-send guard (Layer 2) compensates but root cause is unresolved.",
        ))

        # 5. Resolved signals missing closed_at
        orphaned = conn.execute("""
            SELECT COUNT(*) as cnt FROM ml_signals
            WHERE outcome IS NOT NULL AND outcome != ''
              AND (closed_at IS NULL OR closed_at = '')
        """).fetchone()["cnt"]
        checks.append(_check(
            "resolved_have_closed_at",
            "PASS" if orphaned == 0 else "WARN",
            f"{orphaned} resolved signal(s) missing closed_at",
            "These were resolved before closed_at column was added — resolver will not re-process",
        ))

        # 6. Signals stuck open > max expiry (7 days)
        ancient = conn.execute("""
            SELECT COUNT(*) as cnt FROM ml_signals
            WHERE outcome IS NULL
              AND created_at < datetime('now', '-7 days')
        """).fetchone()["cnt"]
        checks.append(_check(
            "open_signals_beyond_expiry",
            "PASS" if ancient == 0 else "WARN",
            f"{ancient} open signal(s) older than 7 days",
            "Resolver should have expired these. Run resolver with --verbose to investigate.",
        ))

        # 7. DB page count / size estimate
        page_count = conn.execute("PRAGMA page_count;").fetchone()[0]
        page_size  = conn.execute("PRAGMA page_size;").fetchone()[0]
        size_mb    = round(page_count * page_size / 1024 / 1024, 1)
        checks.append(_check(
            "db_size",
            "PASS" if size_mb < 200 else "WARN",
            f"{size_mb} MB",
            "WARN > 200 MB — consider archiving old ohlcv_data rows",
        ))

        conn.close()
        return jsonify(_audit_envelope(checks))

    except Exception as e:
        log.error(f"/audit/integrity error: {e}")
        return jsonify({"status": "ERROR", "error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# SERVE MOBILE HTML
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# SYSTEM CONTEXT  (full market intelligence per active symbol)
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/system/context")
@require_auth
def system_context():
    try:
        conn = get_sa_db()
        results = []

        # Get all active watchlist symbols
        watchlist = conn.execute("""
            SELECT symbol, direction, change_from_open_pct,
                   atr_14_pct, expires_at
            FROM active_watchlist
            ORDER BY added_at DESC
        """
        ).fetchall()

        for row in watchlist:
            symbol = row["symbol"]

            # Latest context_log entry for this symbol
            ctx = conn.execute("""
                SELECT * FROM context_log
                WHERE ticker = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (symbol,)).fetchone()

            # Latest signal state for this symbol
            sig = conn.execute("""
                SELECT signal, interval, entry_price,
                       outcome, result_pct, created_at,
                       stop_loss, take_profit, strategy_version
                FROM ml_signals
                WHERE ticker = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (symbol,)).fetchone()

            # Build context payload
            ctx_payload = None
            if ctx:
                ctx_payload = dict(ctx)

            # Determine market state from context
            market_state = _derive_market_state(ctx_payload)

            # Running P&L if active signal
            running_pct = None
            if sig and not sig["outcome"]:
                price_row = conn.execute("""
                    SELECT close FROM ohlcv_data
                    WHERE symbol = ?
                    ORDER BY timestamp DESC LIMIT 1
                """, (symbol,)).fetchone()
                if price_row and sig["entry_price"]:
                    running_pct = round(
                        _result_pct(
                            sig["entry_price"],
                            float(price_row["close"]),
                            sig["signal"]
                        ), 2
                    )

            results.append({
                "symbol":            symbol,
                "direction":         row["direction"],
                "change_pct":        round(row["change_from_open_pct"] or 0, 4),
                "atr_pct":           round(row["atr_14_pct"] or 0, 4),
                "expires_at":        row["expires_at"],
                "market_state":      market_state,
                "context": ctx_payload,
                "signal": {
                    "direction":  _direction_label(sig["signal"]) if sig else None,
                    "interval":   sig["interval"] if sig else None,
                    "entry":      sig["entry_price"] if sig else None,
                    "sl":         sig["stop_loss"] if sig else None,
                    "tp":         sig["take_profit"] if sig else None,
                    "outcome":    sig["outcome"] if sig else None,
                    "result_pct": round(sig["result_pct"] or 0, 2) if sig and sig["result_pct"] else running_pct,
                    "strategy":   sig["strategy_version"] if sig else None,
                    "age":        _fmt_age(sig["created_at"]) if sig else None,
                    "status":     sig["outcome"] or "RUNNING" if sig else None,
                } if sig else None,
                "refreshed_at": _now_utc_str(),
            })

        conn.close()

        # Summary counts by market state
        state_counts = {}
        for r in results:
            s = r["market_state"]
            state_counts[s] = state_counts.get(s, 0) + 1

        return jsonify({
            "total":        len(results),
            "state_counts": state_counts,
            "assets":       results,
            "refreshed_at": _now_utc_str(),
        })

    except Exception as e:
        log.error(f"/system/context error: {e}")
        return jsonify({"error": str(e)}), 500


def _derive_market_state(ctx: dict | None) -> str:
    """
    Derive a human-readable market state from context_log fields.
    Falls back gracefully if context is missing.
    """
    if not ctx:
        return "NEUTRAL"

    comp = None
    exp  = None

    for comp_key in ["compression_score", "compression", "comp_score"]:
        if comp_key in ctx:
            comp = ctx[comp_key]
            break

    for exp_key in ["expansion_pressure", "expansion", "exp_pressure"]:
        if exp_key in ctx:
            exp = ctx[exp_key]
            break

    if comp is None or exp is None:
        return "NEUTRAL"

    try:
        comp = float(comp)
        exp  = float(exp)
    except (TypeError, ValueError):
        return "NEUTRAL"

    if comp >= 0.85:
        return "COMPRESSION"
    if exp >= 0.60:
        return "TRENDING"
    if exp >= 0.35:
        return "EMERGING"
    if comp < 0.40 and exp < 0.25:
        return "EXHAUSTED"
    return "NEUTRAL"


def _now_utc_str() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _parse_ts(ts_str: str):
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(ts_str[:26], fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        return None


@app.route("/api/mobile/resolver/feed")
@require_auth
def resolver_feed():
    try:
        conn = get_sa_db()

        # Last 10 resolved signals
        resolved = conn.execute("""
            SELECT ticker, interval, signal, entry_price,
                   stop_loss, take_profit, outcome, result_pct,
                   strategy_version, created_at, closed_at
            FROM ml_signals
            WHERE outcome IS NOT NULL AND outcome != ''
              AND outcome != 'NO_FILL'
            ORDER BY closed_at DESC
            LIMIT 10
        """).fetchall()

        # Aggregate stats
        all_resolved = conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN outcome='TP_HIT' THEN 1 END) as wins,
                COUNT(CASE WHEN outcome='SL_HIT' THEN 1 END) as losses,
                MAX(result_pct) as best_result,
                AVG(CASE WHEN result_pct IS NOT NULL THEN result_pct END) as avg_result
            FROM ml_signals
            WHERE outcome IN ('TP_HIT','SL_HIT')
        """).fetchone()

        total_res  = (all_resolved["wins"] or 0) + (all_resolved["losses"] or 0)
        win_rate   = round(
            (all_resolved["wins"] or 0) / total_res * 100, 1
        ) if total_res > 0 else 0

        feed = []
        for r in resolved:
            # Calculate hold duration
            duration_label = "—"
            created = _parse_ts(r["created_at"])
            closed  = _parse_ts(r["closed_at"])
            if created and closed:
                delta_mins = int((closed - created).total_seconds() / 60)
                if delta_mins < 60:
                    duration_label = f"{delta_mins}m"
                else:
                    duration_label = f"{delta_mins // 60}h {delta_mins % 60}m"

            feed.append({
                "ticker":    r["ticker"],
                "interval":  r["interval"],
                "direction": _direction_label(r["signal"]),
                "entry":     r["entry_price"],
                "outcome":   r["outcome"],
                "result_pct": round(r["result_pct"] or 0, 2),
                "strategy":  r["strategy_version"] or "v3",
                "duration":  duration_label,
                "closed_at": r["closed_at"],
                "age":       _fmt_age(r["closed_at"] or r["created_at"]),
            })

        conn.close()

        return jsonify({
            "feed":       feed,
            "stats": {
                "win_rate":   win_rate,
                "total":      total_res,
                "wins":       all_resolved["wins"] or 0,
                "losses":     all_resolved["losses"] or 0,
                "best_trade": round(all_resolved["best_result"] or 0, 2),
                "avg_result": round(all_resolved["avg_result"] or 0, 2),
            },
            "refreshed_at": _now_utc_str(),
        })

    except Exception as e:
        log.error(f"/resolver/feed error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api.js')
def serve_api_js():
    """Serve the frontend `api.js` from the static directory."""
    return send_from_directory(STATIC_DIR, "api.js")


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "sa_mobile.html")


@app.route("/api/mobile/watchlist/live")
@require_auth
def watchlist_live():
    try:
        conn = get_sa_db()

        # All active watchlist symbols (not expired)
        symbols = conn.execute("""
            SELECT symbol, direction, change_from_open_pct,
                   atr_14_pct, volume_24h, expires_at, added_at
            FROM active_watchlist
            ORDER BY added_at DESC
        """).fetchall()

        groups = {
            "TRENDING":    [],
            "EMERGING":    [],
            "COMPRESSION": [],
            "EXHAUSTED":   [],
            "NEUTRAL":     [],
        }

        for row in symbols:
            symbol = row["symbol"]

            # Latest context for this symbol
            ctx = conn.execute("""
                SELECT * FROM context_log
                WHERE ticker = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (symbol,)).fetchone()

            ctx_dict = dict(ctx) if ctx else None
            state    = _derive_market_state(ctx_dict)

            # Latest signal
            sig = conn.execute("""
                SELECT signal, interval, outcome,
                       result_pct, created_at, entry_price,
                       stop_loss, take_profit
                FROM ml_signals
                WHERE ticker = ?
                ORDER BY created_at DESC LIMIT 1
            """, (symbol,)).fetchone()

            # Extract key context metrics for display
            ctx_summary = None
            if ctx_dict:
                comp = ctx_dict.get("compression_score",
                       ctx_dict.get("compression", None))
                exp  = ctx_dict.get("expansion_pressure",
                       ctx_dict.get("expansion", None))
                rsi  = ctx_dict.get("rsi_stage",
                       ctx_dict.get("rsi", None))
                sweep = ctx_dict.get("sweep_detected",
                        ctx_dict.get("liquidity_sweep", None))
                ctx_summary = {
                    "compression": round(float(comp), 3) if comp is not None else None,
                    "expansion":   round(float(exp), 3) if exp is not None else None,
                    "rsi_stage":   str(rsi) if rsi is not None else None,
                    "sweep":       bool(int(sweep)) if sweep is not None else False,
                    "scanned_at":  ctx_dict.get("timestamp",
                                   ctx_dict.get("created_at", None)),
                }

            asset = {
                "symbol":      symbol,
                "direction":   row["direction"],
                "change_pct":  round(row["change_from_open_pct"] or 0, 4),
                "atr_pct":     round(row["atr_14_pct"] or 0, 4),
                "volume_24h":  row["volume_24h"],
                "market_state": state,
                "context":     ctx_summary,
                "signal": {
                    "direction": _direction_label(sig["signal"]) if sig else None,
                    "interval":  sig["interval"] if sig else None,
                    "outcome":   sig["outcome"] if sig else None,
                    "result_pct": round(sig["result_pct"] or 0, 2) if sig and sig["result_pct"] else None,
                    "age":       _fmt_age(sig["created_at"]) if sig else None,
                } if sig else None,
            }

            state_key = state if state in groups else "NEUTRAL"
            groups[state_key].append(asset)

        conn.close()

        # Summary counts
        counts = {k: len(v) for k, v in groups.items()}

        return jsonify({
            "total":        len(symbols),
            "counts":       counts,
            "groups":       groups,
            "refreshed_at": _now_utc_str(),
        })

    except Exception as e:
        log.error(f"/watchlist/live error: {e}")
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"SA Mobile API starting on port {PORT}")
    log.info(f"SA DB:   {SA_DB_PATH}")
    log.info(f"Auth DB: {AUTH_DB_PATH}")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
