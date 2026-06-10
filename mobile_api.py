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
import boto3
import json

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
_bedrock     = boto3.client("bedrock-runtime", region_name="ap-southeast-1")
_intel_cache = {"brief": None, "generated_at": None}

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


def get_volume_metrics(ticker, interval, db_path, lookback=20):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT open, high, low, close, volume, timestamp
            FROM ohlcv_data
            WHERE symbol = ?
              AND LOWER(timeframe) = LOWER(?)
              AND volume > 0
            ORDER BY timestamp DESC
            LIMIT ?
        """, (ticker, interval, lookback + 3)).fetchall()
        conn.close()
        if not rows or len(rows) < 3:
            return None
        latest     = rows[0]
        raw_volume = float(latest["volume"])
        hist_vols  = [float(r["volume"]) for r in rows[1:lookback+1]]
        avg_volume = sum(hist_vols) / len(hist_vols) if hist_vols else 0
        rvol = round(raw_volume / avg_volume, 2) if avg_volume > 0 else 0
        surge = rvol >= 2.0
        price_direction = "up" if float(latest["close"]) >= float(latest["open"]) else "down"
        vol_direction   = "up" if len(rows) > 1 and raw_volume > float(rows[1]["volume"]) else "down"
        divergence = price_direction != vol_direction
        v0 = float(rows[0]["volume"])
        v1 = float(rows[1]["volume"])
        v2 = float(rows[2]["volume"])
        slope = (v0 - v2) / 2
        if slope > avg_volume * 0.1:
            vol_trend = "RISING"
        elif slope < -avg_volume * 0.1:
            vol_trend = "FALLING"
        else:
            vol_trend = "FLAT"
        return {
            "raw_volume":    round(raw_volume, 2),
            "avg_volume_20": round(avg_volume, 2),
            "rvol":          rvol,
            "volume_surge":  surge,
            "divergence":    divergence,
            "vol_trend":     vol_trend,
            "price_dir":     price_direction,
            "vol_dir":       vol_direction,
        }
    except Exception:
        return None


def log_volume_metrics(ticker, interval, vol, db_path, bar_ts=None):
    if not vol:
        return
    try:
        ts = bar_ts or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            INSERT OR IGNORE INTO volume_log
              (ticker, interval, ts, raw_volume, avg_volume_20,
               rvol, volume_surge, divergence, vol_trend,
               price_dir, vol_dir)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker,
            interval.lower(),
            ts,
            vol["raw_volume"],
            vol["avg_volume_20"],
            vol["rvol"],
            1 if vol["volume_surge"] else 0,
            1 if vol["divergence"] else 0,
            vol["vol_trend"],
            vol["price_dir"],
            vol["vol_dir"],
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────
# CORS — allow all origins for mobile access
# ─────────────────────────────────────────────────────────────────
# INTELLIGENCE FEED — SNAPSHOT + LLM BRIEF
# ─────────────────────────────────────────────────────────────────

def _build_intel_snapshot() -> dict:
    """
    Aggregates context_log and ml_signals into a compact
    intelligence snapshot. This is the ONLY input to the LLM.
    Raw rows are never sent to the model.
    """
    try:
        conn = get_sa_db()

        state_row = conn.execute("""
            SELECT
              COUNT(DISTINCT ticker)                             AS total_assets,
              SUM(CASE WHEN compression_score < 0.60
                       THEN 1 ELSE 0 END)                      AS compression_assets,
              SUM(CASE WHEN expansion_pressure >= 0.60
                       THEN 1 ELSE 0 END)                      AS trending_assets,
              SUM(CASE WHEN expansion_pressure >= 0.35
                        AND expansion_pressure < 0.60
                       THEN 1 ELSE 0 END)                      AS emerging_assets,
              SUM(CASE WHEN liquidity_sweep = 1
                       THEN 1 ELSE 0 END)                      AS sweep_confirmed,
              SUM(CASE WHEN sweep_probability >= 0.70
                       THEN 1 ELSE 0 END)                      AS high_sweep_prob,
              ROUND(AVG(rejection_strength), 3)                AS avg_rejection,
              ROUND(AVG(breakout_quality), 3)                  AS avg_breakout_quality
            FROM context_log
            WHERE timestamp > datetime('now', '-1 hours')
              AND ticker != ''
        """).fetchone()

        pressure_rows = conn.execute("""
            SELECT
              cl.ticker,
              cl.compression_score,
              cl.expansion_pressure,
              cl.rsi_stage,
              cl.sweep_probability
            FROM context_log cl
            INNER JOIN (
              SELECT ticker, MAX(created_at) AS max_ts
              FROM context_log
              WHERE timestamp > datetime('now', '-1 hours')
              GROUP BY ticker
            ) latest ON cl.ticker = latest.ticker
                     AND cl.created_at = latest.max_ts
            ORDER BY cl.compression_score ASC
            LIMIT 5
        """).fetchall()

        top_pressure = [
            {
                "ticker":      r["ticker"],
                "compression": round(r["compression_score"] or 0, 3),
                "expansion":   round(r["expansion_pressure"] or 0, 3),
                "rsi_stage":   r["rsi_stage"] or "NEUTRAL",
                "sweep_prob":  round(r["sweep_probability"] or 0, 3)
                               if r["sweep_probability"] is not None else None,
            }
            for r in pressure_rows
        ]

        outcome_rows = conn.execute("""
            SELECT strategy_version, outcome, result_pct
            FROM ml_signals
            WHERE outcome IN ('TP_HIT', 'SL_HIT')
              AND signal_quality = 'live'
            ORDER BY closed_at DESC
            LIMIT 10
        """).fetchall()

        v1_outcomes = [r for r in outcome_rows if r["strategy_version"] == "v1"]
        v3_outcomes = [r for r in outcome_rows if r["strategy_version"] == "v3"]

        def win_rate(rows):
            if not rows: return None
            wins = sum(1 for r in rows if r["outcome"] == "TP_HIT")
            return round(wins / len(rows) * 100, 1)

        last_5 = [r["outcome"] for r in outcome_rows[:5]]

        active_row = conn.execute("""
            SELECT COUNT(*) AS cnt FROM ml_signals
            WHERE (outcome IS NULL OR outcome = 'PENDING') AND signal_quality = 'live'
        """).fetchone()

        conn.close()

        # Layer 2 — Aggregate volume signals across active ticker/interval pairs
        volume_intel = None
        try:
            vol_conn = sqlite3.connect(SA_DB_PATH)
            vol_conn.row_factory = sqlite3.Row
            pairs = vol_conn.execute("""
                SELECT DISTINCT symbol, timeframe
                FROM ohlcv_data
                WHERE volume > 0
                  AND timestamp > datetime('now', '-2 hours')
            """).fetchall()
            vol_conn.close()
            surge_count      = 0
            divergence_count = 0
            rising_count     = 0
            total_pairs      = len(pairs)
            for pair in pairs:
                vm = get_volume_metrics(pair["symbol"], pair["timeframe"], SA_DB_PATH)
                if vm:
                    if vm["volume_surge"]:           surge_count += 1
                    if vm["divergence"]:             divergence_count += 1
                    if vm["vol_trend"] == "RISING":  rising_count += 1
            volume_intel = {
                "pairs_analysed":   total_pairs,
                "surge_count":      surge_count,
                "divergence_count": divergence_count,
                "rising_vol_count": rising_count,
                "surge_pct":        round(surge_count / total_pairs * 100, 1) if total_pairs else 0,
            }
        except Exception:
            pass

        # ── Layer 3: VOLUME_BREAKOUT events (last 2 hours) ──
        volume_breakout_intel = {
            'event_count':  0,
            'assets':       [],
            'states':       [],
            'window_hours': 2,
        }
        try:
            pal_conn = get_sa_db()
            vb_rows = pal_conn.execute("""
                SELECT ticker, interval, pressure_state, alerted_at
                FROM pressure_alert_log
                WHERE alert_type = 'VOLUME_BREAKOUT'
                  AND alerted_at >= datetime('now', '-2 hours')
                ORDER BY alerted_at DESC
            """).fetchall()
            volume_breakout_intel['event_count'] = len(vb_rows)
            volume_breakout_intel['assets'] = list({r[0] for r in vb_rows})
            volume_breakout_intel['states'] = list({r[2] for r in vb_rows})
            pal_conn.close()
        except Exception as _e:
            log.warning(f"[INTEL] vb query failed: {_e}")

        # ── Layer 4: Pressure escalations (last 2 hours) ─────
        pressure_escalation_intel = {
            'escalation_count': 0,
            'extreme_count':    0,
            'high_count':       0,
            'escalated_assets': [],
        }
        try:
            pe_conn = get_sa_db()
            pe_rows = pe_conn.execute("""
                SELECT ticker, pressure_state, pressure_score, alerted_at
                FROM pressure_alert_log
                WHERE alert_type = 'PRESSURE_TRANSITION'
                  AND pressure_state IN ('HIGH', 'EXTREME')
                  AND alerted_at >= datetime('now', '-2 hours')
                ORDER BY pressure_score DESC
            """).fetchall()
            pressure_escalation_intel['escalation_count'] = len(pe_rows)
            pressure_escalation_intel['extreme_count'] = sum(
                1 for r in pe_rows if r[1] == 'EXTREME'
            )
            pressure_escalation_intel['high_count'] = sum(
                1 for r in pe_rows if r[1] == 'HIGH'
            )
            pressure_escalation_intel['escalated_assets'] = [
                {'ticker': r[0], 'state': r[1], 'score': r[2]}
                for r in pe_rows
            ]
            pe_conn.close()
        except Exception as _e:
            log.warning(f"[INTEL] pressure escalation query failed: {_e}")

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "market_state": {
                "total_assets":         state_row["total_assets"] or 0,
                "compression_assets":   state_row["compression_assets"] or 0,
                "trending_assets":      state_row["trending_assets"] or 0,
                "emerging_assets":      state_row["emerging_assets"] or 0,
                "sweep_confirmed":      state_row["sweep_confirmed"] or 0,
                "high_sweep_prob":      state_row["high_sweep_prob"] or 0,
                "avg_rejection":        state_row["avg_rejection"],
                "avg_breakout_quality": state_row["avg_breakout_quality"],
            },
            "top_pressure_assets": top_pressure,
            "signal_outcomes": {
                "pulse_win_rate":  win_rate(v1_outcomes),
                "rift_win_rate":   win_rate(v3_outcomes),
                "last_5_outcomes": last_5,
                "active_signals":  active_row["cnt"] or 0,
            },
            "volume_intelligence":        volume_intel,
            "volume_breakout_intel":      volume_breakout_intel,
            "pressure_escalation_intel":  pressure_escalation_intel,
        }

    except Exception as e:
        log.error(f"_build_intel_snapshot error: {e}")
        return {}


INTEL_BRIEF_SYSTEM = """You are the Silent Analyst intelligence layer — a market structure
intelligence system built by OptiCore Labs.

Your role is to scan aggregated market state data and surface only
the conditions that materially matter right now.

You do not narrate the market.
You identify pressure, imbalance, transition, expansion risk,
and structural anomalies before they fully express.

Rules:
- Output ONLY a valid JSON array containing 4–6 observations.
- No markdown. No prose outside JSON.
- Every observation must reference specific values or counts from
  the supplied snapshot.
- Never generate generic commentary that could apply to any session.
- Prioritise structural shifts, clustering behaviour, sweep activity,
  compression concentration, and abnormal expansion conditions.
- Every observation must explain WHY the condition matters now.
- Observations should feel operational, not journalistic.
- Avoid hype, emotional language, or prediction framing.
- Never use:
  "market conditions", "traders should watch", "it appears",
  "worth noting", "bullish sentiment", "bearish sentiment".

Categories allowed:
COMPRESSION | EXPANSION | PRESSURE | SWEEP | SIGNAL | VOLUME | SYSTEM

Weights allowed:
HIGH | MEDIUM | LOW

Sort observations by structural significance descending.

Output format — strict JSON array only:
[
  {
    "category": "PRESSURE",
    "text": "Expansion pressure accelerated above 0.35 on 11 assets simultaneously, with 6 already transitioning into RSI Stage 1C — early expansion clustering forming across the board.",
    "weight": "HIGH"
  }
]

New data available in snapshot:
volume_breakout_intel: counts assets where real exchange volume
  exceeded 2x the 20-bar average within the last 2 hours, filtered
  to assets already showing structural pressure (RISING/HIGH/EXTREME
  state). event_count=0 means no volume spikes detected. assets[] lists
  the specific tickers. Use VOLUME category for observations from this.
  A VOLUME observation is only warranted when event_count > 0.
pressure_escalation_intel: counts assets that escalated to HIGH or
  EXTREME pressure state in the last 2 hours. escalated_assets lists
  each as {ticker, state, score}. Use PRESSURE category for these.
  Reference specific asset names and counts in observations.
"""

def _generate_intel_brief(snapshot: dict) -> list:
    """
    Calls Bedrock Claude Haiku with a compressed snapshot.
    Returns list of {category, text} observation dicts.
    LLM never sees raw DB rows — only the aggregated snapshot.
    """
    if not snapshot:
        return [{"category": "SYSTEM",
                 "text": "Intelligence snapshot unavailable."}]
    try:
        user_content = (
            f"Market system snapshot — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\n\n"
            + json.dumps(snapshot, indent=2)
            + "\n\nGenerate the intelligence brief.\n"
            "Lead with the highest structural significance observation.\n"
            "Every observation must be grounded in specific values from the snapshot above.\n"
            "Do not produce observations that could apply to any session.\n\n"
            "REQUIRED JSON KEYS — use exactly these, no others:\n"
            "  category: one of COMPRESSION|EXPANSION|PRESSURE|SWEEP|SIGNAL|SYSTEM\n"
            "  text: your observation string\n"
            "  weight: HIGH, MEDIUM, or LOW\n"
            "Output ONLY the JSON array. No explanation."
        )

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 512,
            "system": INTEL_BRIEF_SYSTEM,
            "messages": [{"role": "user", "content": user_content}]
        })

        response = _bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=body,
            contentType="application/json",
            accept="application/json"
        )

        raw  = json.loads(response["body"].read())
        text = raw["content"][0]["text"].strip()

        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        observations = json.loads(text)

        valid_categories = {
            "COMPRESSION", "EXPANSION", "PRESSURE",
            "SWEEP", "SIGNAL", "SYSTEM"
        }
        result = []
        for obs in observations:
            if isinstance(obs, dict) and "category" in obs:
                cat = obs["category"].upper()
                if cat not in valid_categories:
                    cat = "SYSTEM"
                text = obs.get("observation") or obs.get("text") or ""
                _weight_map = {"COMPRESSION": "HIGH", "SWEEP": "HIGH",
                               "PRESSURE": "HIGH", "EXPANSION": "MEDIUM",
                               "SIGNAL": "MEDIUM", "SYSTEM": "LOW"}
                weight = obs.get("weight") or _weight_map.get(cat, "MEDIUM")
                result.append({"category": cat, "text": str(text), "weight": weight})

        return result if result else [
            {"category": "SYSTEM", "text": "No observations generated."}
        ]

    except Exception as e:
        log.error(f"_generate_intel_brief error: {e}")
        return [{"category": "SYSTEM",
                 "text": "Intelligence generation unavailable."}]


CONTEXT_SYSTEM = """You are the Silent Analyst context engine — a real-time market
structure interpreter built by OptiCore Labs.

Your role is to read structural pressure conditions for a single
asset and describe what the system is actually detecting beneath
price movement.

Rules:
- Write EXACTLY 3 sentences.
- No markdown. No headers. Plain text only.

Sentence structure is mandatory:

Sentence 1:
Identify the dominant structural condition using the single most
important metric in the dataset. Include the exact value.

Sentence 2:
Describe the confirming or conflicting secondary conditions that
either strengthen or weaken the primary structure.

Sentence 3:
State the structural implication. Focus on pressure transition,
failed expansion risk, sweep vulnerability, or expansion continuation.

Additional rules:
- Prioritise anomalies over summaries.
- Do not list metrics mechanically.
- Do not explain trading concepts.
- Do not force directional bias unless structurally justified.
- Never use:
  "it appears", "potentially", "worth noting",
  "market conditions", "traders should", "possibly".

Tone:
Detached. Precise. Operational.
Written like an internal intelligence system, not a trading educator."""


CONTEXT_READING_PROMPT = """Asset: {ticker}
Timeframe: {interval}
Timestamp: {ts} UTC

STRUCTURAL DATA:
- Compression score:      {compression} {compression_signal}
- Expansion pressure:     {expansion}
- RSI stage:              {rsi_stage}
- Pressure state:         {pressure_state} (score: {pressure_score})
- Body commitment:        {body_commitment}
- Breakout quality:       {breakout_quality}

LIQUIDITY DATA:
- Liquidity type:         {liquidity_type}
- Distance to liquidity:  {distance_pct}%
- Sweep detected:         {sweep}
- Rejection signal:       {rejection}
- Sweep probability:      {sweep_probability}

VOLUME DATA:
- Raw volume:           {vol_raw}
- Avg volume (20-bar):  {vol_avg}
- Relative volume:      {vol_rvol}x
- Volume surge:         {vol_surge}
- Volume divergence:    {vol_divergence}
- Volume trend:         {vol_trend}

Prioritise the most anomalous or decisive metric across
structure, liquidity, AND volume. If volume surge or
divergence is present, it must be addressed in the reading.
Write the 3-sentence structural reading now."""

def _generate_context_reading(ctx: dict, symbol: str) -> str:
    """Calls Bedrock Haiku with context metrics; returns a plain-text narrative reading."""
    try:
        comp = round(ctx.get("compression_score") or 0, 3)
        compression_signal = "(compressed)" if comp < 0.6 else "(expanding)" if comp > 1.2 else "(neutral)"
        vol_data = ctx.get("volume") or {}
        prompt = CONTEXT_SYSTEM + "\n\n" + CONTEXT_READING_PROMPT.format(
            ticker=symbol,
            interval=ctx.get("timeframe") or ctx.get("interval") or "—",
            ts=datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
            compression=comp,
            compression_signal=compression_signal,
            expansion=round(ctx.get("expansion_pressure") or 0, 3),
            rsi_stage=ctx.get("rsi_stage") or "—",
            liquidity_type=ctx.get("liquidity_type") or "—",
            distance_pct=round(ctx.get("distance_to_liquidity_pct") or 0, 2),
            sweep=ctx.get("liquidity_sweep") or "—",
            rejection=round(ctx.get("rejection_strength") or 0, 3),
            breakout_quality=round(ctx.get("breakout_quality") or 0, 3),
            body_commitment=round(ctx.get("body_commitment") or 0, 3),
            sweep_probability=round(ctx.get("sweep_probability") or 0, 3),
            pressure_state=ctx.get("pressure_state") or "—",
            pressure_score=ctx.get("pressure_score") or 0,
            vol_raw=vol_data.get("raw_volume", "N/A"),
            vol_avg=vol_data.get("avg_volume_20", "N/A"),
            vol_rvol=vol_data.get("rvol", "N/A"),
            vol_surge=vol_data.get("volume_surge", False),
            vol_divergence=vol_data.get("divergence", False),
            vol_trend=vol_data.get("vol_trend", "N/A"),
        )

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 450,
            "messages": [{"role": "user", "content": prompt}]
        })

        response = _bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=body,
            contentType="application/json",
            accept="application/json"
        )

        raw = json.loads(response["body"].read())
        return raw["content"][0]["text"].strip()

    except Exception as e:
        log.error(f"_generate_context_reading error: {e}")
        return "Context reading unavailable at this time."


INTEL_CACHE_TTL_SECONDS = 480  # 8 minutes


@app.route("/api/gate")
def gate_state():
    """Public — no auth required. Frontend reads this before login context exists."""
    try:
        with open("/home/ubuntu/sa_gate.json") as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({"open": False})


@app.route("/api/mobile/intel/brief")
@require_auth
def intel_brief():
    """
    Returns AI-generated market intelligence observations.
    Cached server-side for 8 minutes. Force-refresh with ?refresh=1.
    LLM input: compressed snapshot only — never raw DB rows.
    """
    global _intel_cache

    force = request.args.get("refresh") == "1"
    now   = datetime.utcnow()

    if (not force
            and _intel_cache["brief"] is not None
            and _intel_cache["generated_at"] is not None):
        age = (now - _intel_cache["generated_at"]).total_seconds()
        if age < INTEL_CACHE_TTL_SECONDS:
            return jsonify({
                "observations": _intel_cache["brief"],
                "generated_at": _intel_cache["generated_at"].isoformat(),
                "cached":       True,
                "age_seconds":  int(age),
            })

    snapshot     = _build_intel_snapshot()
    observations = _generate_intel_brief(snapshot)

    _intel_cache["brief"]        = observations
    _intel_cache["generated_at"] = now

    return jsonify({
        "observations": observations,
        "generated_at": now.isoformat(),
        "cached":       False,
        "age_seconds":  0,
    })


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



def _strategy_display_label(strategy_version: str) -> str:
    "Map internal strategy_version to display label."
    if not strategy_version:
        return "Unknown"
    v = strategy_version.lower()
    if v == "v1":
        return "Pulse"
    if v == "v3":
        return "Rift"
    if v == "v2":
        return "V2"
    return strategy_version

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
                COUNT(CASE WHEN (outcome IS NULL OR outcome = 'PENDING')  THEN 1 END)   AS active_count,
                COUNT(*)                                         AS total,
                AVG(CASE WHEN result_pct IS NOT NULL THEN result_pct END) AS avg_pnl
            FROM ml_signals
            WHERE created_at > datetime('now', '-30 days')
              AND signal_quality = 'live'
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
              AND (outcome IS NULL OR outcome = 'PENDING')
              AND signal_quality = 'live'
        """).fetchone()

        # ── Active signal cards ─────────────────────────────────
        active_rows = conn.execute("""
            SELECT ticker, interval, signal, entry_price,
                   stop_loss, take_profit, strategy_version, created_at
            FROM ml_signals
            WHERE (outcome IS NULL OR outcome = 'PENDING')
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
                "interval":  (r["interval"] or "").lower() or None,
                "direction": _direction_label(r["signal"]),
                "entry":     r["entry_price"],
                "sl":        r["stop_loss"],
                "tp":        r["take_profit"],
                "strategy":     _strategy_display_label(r["strategy_version"]),
                "strategy_raw": r["strategy_version"] or "v3",
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

        engine = request.args.get('engine')  # 'v1' | 'v3' | None

        eng_filter = "AND strategy_version = ?" if engine else ""
        eng_params = (engine,) if engine else ()

        active = conn.execute(
            "SELECT id, ticker, interval, signal, entry_price,"
            " stop_loss, take_profit, strategy_version, timestamp as created_at,"
            " compression_at_fire, expansion_at_fire, rsi_stage_at_fire, sweep_at_fire,"
            " rejection_at_fire, breakout_quality_at_fire, body_commitment_at_fire, sweep_probability_at_fire"
            " FROM ml_signals"
            " WHERE (outcome IS NULL OR outcome = 'PENDING') "
            f" {eng_filter}"
            " ORDER BY timestamp DESC LIMIT 20",
            eng_params
        ).fetchall()

        closed = conn.execute(
            "SELECT id, ticker, interval, signal, entry_price,"
            " stop_loss, take_profit, outcome, result_pct,"
            " strategy_version, created_at, closed_at,"
            " compression_at_fire, expansion_at_fire, rsi_stage_at_fire, sweep_at_fire,"
            " rejection_at_fire, breakout_quality_at_fire, body_commitment_at_fire, sweep_probability_at_fire"
            " FROM ml_signals"
            " WHERE outcome IS NOT NULL AND outcome != '' AND outcome != 'PENDING' "
            f" {eng_filter}"
            " ORDER BY closed_at DESC LIMIT 30",
            eng_params
        ).fetchall()

        # All-time per-engine stats from full DB
        stats_row = conn.execute(
            "SELECT"
            " COUNT(*) FILTER (WHERE outcome IN ('TP_HIT','SL_HIT')) AS resolved,"
            " COUNT(*) FILTER (WHERE outcome = 'TP_HIT') AS wins,"
            " COUNT(*) FILTER (WHERE outcome = 'SL_HIT') AS losses,"
            " COUNT(*) FILTER (WHERE (outcome IS NULL OR outcome = 'PENDING')) AS active_count,"
            " ROUND(AVG(CASE WHEN outcome = 'TP_HIT' AND result_pct IS NOT NULL"
            "           THEN result_pct END), 2) AS avg_win_pct,"
            " ROUND(AVG(CASE WHEN outcome = 'SL_HIT' AND result_pct IS NOT NULL"
            "           THEN result_pct END), 2) AS avg_loss_pct"
            " FROM ml_signals"
            " WHERE signal_quality = 'live' "
            f" {eng_filter}",
            eng_params
        ).fetchone()

        resolved  = stats_row['resolved'] or 0
        wins      = stats_row['wins'] or 0
        win_rate  = round(wins / resolved * 100, 1) if resolved > 0 else 0.0
        avg_win   = stats_row['avg_win_pct'] or 0.0
        avg_loss  = stats_row['avg_loss_pct'] or 0.0
        net_pnl   = round((wins * avg_win) + ((resolved - wins) * avg_loss), 2) \
                    if resolved > 0 else 0.0

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
                "interval": (r["interval"] or "").lower() or None,
                "direction": _direction_label(r["signal"]),
                "entry": r["entry_price"], "sl": r["stop_loss"], "tp": r["take_profit"],
                "running_pct": round(running, 2),
                "strategy":     _strategy_display_label(r["strategy_version"]),
                "strategy_raw": r["strategy_version"] or "v3",
                "age": _fmt_age(r["created_at"]),
                "status": "RUNNING",
                "ctx_compression":    r["compression_at_fire"],
                "ctx_expansion":      r["expansion_at_fire"],
                "ctx_rsi_stage":      r["rsi_stage_at_fire"],
                "ctx_sweep":          r["sweep_at_fire"],
                "ctx_rejection":      r["rejection_at_fire"],
                "ctx_breakout":       r["breakout_quality_at_fire"],
                "ctx_body":           r["body_commitment_at_fire"],
                "ctx_sweep_prob":     r["sweep_probability_at_fire"],
                "ctx_pressure_state": _compute_pressure_state({
                    "compression": r["compression_at_fire"],
                    "expansion":   r["expansion_at_fire"],
                    "rsi_stage":   r["rsi_stage_at_fire"],
                }),
            }

        def fmt_closed(r):
            return {
                "id": r["id"], "ticker": r["ticker"],
                "interval": (r["interval"] or "").lower() or None,
                "direction": _direction_label(r["signal"]),
                "entry": r["entry_price"], "sl": r["stop_loss"], "tp": r["take_profit"],
                "outcome": r["outcome"],
                "result_pct": round(r["result_pct"] or 0, 2),
                "strategy":     _strategy_display_label(r["strategy_version"]),
                "strategy_raw": r["strategy_version"] or "v3",
                "age": _fmt_age(r["closed_at"] or r["created_at"]),
                "ctx_compression":    r["compression_at_fire"],
                "ctx_expansion":      r["expansion_at_fire"],
                "ctx_rsi_stage":      r["rsi_stage_at_fire"],
                "ctx_sweep":          r["sweep_at_fire"],
                "ctx_rejection":      r["rejection_at_fire"],
                "ctx_breakout":       r["breakout_quality_at_fire"],
                "ctx_body":           r["body_commitment_at_fire"],
                "ctx_sweep_prob":     r["sweep_probability_at_fire"],
                "ctx_pressure_state": _compute_pressure_state({
                    "compression": r["compression_at_fire"],
                    "expansion":   r["expansion_at_fire"],
                    "rsi_stage":   r["rsi_stage_at_fire"],
                }),
            }

        return jsonify({
            "active": [fmt_active(r) for r in active],
            "closed": [fmt_closed(r) for r in closed],
            "stats": {
                "win_rate":  win_rate,
                "net_pnl":   net_pnl,
                "total":     resolved + (stats_row['active_count'] or 0),
                "wins":      wins,
                "losses":    stats_row['losses'] or 0,
                "resolved":  resolved,
                "scope":     "all-time",
            },
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
                       outcome, result_pct, timestamp as created_at, strategy_version
                FROM ml_signals
                WHERE ticker = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (ticker,)).fetchone()

            if not row:
                continue

            state = _signal_state(row)
            groups[state].append({
                "ticker":    ticker,
                "direction": _direction_label(row["signal"]),
                "interval":  (row["interval"] or "").lower() or None,
                "result_pct": round(row["result_pct"] or 0, 2) if row["result_pct"] else None,
                "age":       _fmt_age(row["created_at"]),
                "strategy":     _strategy_display_label(row["strategy_version"]),
                "strategy_raw": row["strategy_version"] or "v3",
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
                   liquidity_sweep, created_at,
                   distance_to_liquidity_pct, rejection_strength,
                   breakout_quality, body_commitment, sweep_probability
            FROM context_log
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (ticker.upper(),)).fetchone()
        if not row:
            conn.close()
            return jsonify({"context": None})
        ctx = dict(row)
        ctx["market_state"]   = _derive_market_state(ctx)
        ctx["pressure_state"] = _compute_pressure_state(ctx)
        ctx["pressure_score"] = _compute_pressure_score(ctx)

        sf_row = None
        try:
            sf_row = conn.execute("""
                SELECT ema21, ema100_4h, rsi14, atr_at_fire, sl_distance_pct,
                       strategy_version, created_at
                FROM signal_forensics
                WHERE ticker = ?
                ORDER BY created_at DESC LIMIT 1
            """, (ticker.upper(),)).fetchone()
        except Exception as _e:
            log.warning(f"[DEEPVIEW] forensics query {ticker}: {_e}")

        vb_active, vb_fired_at = False, None
        try:
            vb_row = conn.execute("""
                SELECT alerted_at FROM pressure_alert_log
                WHERE ticker = ?
                  AND alert_type = 'VOLUME_BREAKOUT'
                  AND alerted_at >= datetime('now', '-4 hours')
                ORDER BY alerted_at DESC LIMIT 1
            """, (ticker.upper(),)).fetchone()
            if vb_row:
                vb_active   = True
                vb_fired_at = vb_row['alerted_at']
        except Exception as _e:
            log.warning(f"[DEEPVIEW] vb query {ticker}: {_e}")

        outcomes = {}
        try:
            for oc in conn.execute("""
                SELECT strategy_version, outcome,
                       ROUND(ABS(entry_price - stop_loss)
                             / entry_price * 100, 3) AS sl_pct,
                       created_at
                FROM ml_signals
                WHERE ticker = ?
                  AND outcome IS NOT NULL
                  AND outcome != 'NO_FILL'
                ORDER BY created_at DESC LIMIT 6
            """, (ticker.upper(),)).fetchall():
                sv = oc['strategy_version']
                if sv not in outcomes:
                    outcomes[sv] = {
                        'outcome':    oc['outcome'],
                        'sl_pct':     oc['sl_pct'],
                        'created_at': oc['created_at'],
                    }
        except Exception as _e:
            log.warning(f"[DEEPVIEW] outcomes query {ticker}: {_e}")

        conn.close()

        return jsonify({
            "context": ctx,
            "indicators": {
                "ema21":       float(sf_row['ema21'])           if sf_row and sf_row['ema21']           else None,
                "ema100":      float(sf_row['ema100_4h'])       if sf_row and sf_row['ema100_4h']       else None,
                "rsi14":       float(sf_row['rsi14'])           if sf_row and sf_row['rsi14']           else None,
                "atr_at_fire": float(sf_row['atr_at_fire'])     if sf_row and sf_row['atr_at_fire']     else None,
                "sl_pct":      float(sf_row['sl_distance_pct']) if sf_row and sf_row['sl_distance_pct'] else None,
                "engine":      sf_row['strategy_version']       if sf_row else None,
                "as_of":       sf_row['created_at']             if sf_row else None,
            },
            "volume_breakout": {
                "active":   vb_active,
                "fired_at": vb_fired_at,
            },
            "recent_outcomes": outcomes,
        })
    except Exception as e:
        log.error(f"/context/{ticker} error: {e}")
        return jsonify({"context": None}), 500


@app.route("/api/mobile/context-reading/<ticker>")
@require_auth
def context_reading(ticker):
    """Returns a Bedrock-generated plain-text contextual market state reading."""
    try:
        conn = get_sa_db()
        row = conn.execute("""
            SELECT compression_score, expansion_pressure,
                   rsi_stage, liquidity_type, distance_to_liquidity_pct,
                   liquidity_sweep, rejection_strength, breakout_quality,
                   body_commitment, sweep_probability, interval
            FROM context_log
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (ticker.upper(),)).fetchone()
        conn.close()
        if not row:
            return jsonify({"reading": "No context data available for this asset."})
        ctx = dict(row)
        ctx["pressure_state"] = _compute_pressure_state(ctx)
        ctx["pressure_score"] = _compute_pressure_score(ctx)
        vol = get_volume_metrics(
            ticker.upper(),
            ctx.get("interval") or "1h",
            SA_DB_PATH,
            lookback=20
        )
        ctx["volume"] = {
            "raw_volume":    vol["raw_volume"],
            "avg_volume_20": vol["avg_volume_20"],
            "rvol":          vol["rvol"],
            "volume_surge":  vol["volume_surge"],
            "divergence":    vol["divergence"],
            "vol_trend":     vol["vol_trend"],
        } if vol else None
        if vol:
            log_volume_metrics(
                ticker.upper(),
                ctx.get("interval") or "1h",
                vol,
                SA_DB_PATH,
            )
        reading = _generate_context_reading(ctx, ticker.upper())
        return jsonify({"reading": reading, "volume": ctx["volume"]})
    except Exception as e:
        log.error(f"/context-reading/{ticker} error: {e}")
        return jsonify({"reading": "Context reading unavailable at this time."}), 500


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
                   timestamp as created_at, closed_at
            FROM ml_signals
            WHERE ticker = ?
            ORDER BY timestamp DESC
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
                "strategy":     _strategy_display_label(sig["strategy_version"]) if sig else None,
                "strategy_raw": sig["strategy_version"] if sig else None,
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
                    "interval":   (r["interval"] or "").lower() or None,
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
                COUNT(CASE WHEN (outcome IS NULL OR outcome = 'PENDING')  THEN 1 END) AS active,
                AVG(CASE WHEN result_pct IS NOT NULL THEN result_pct END) AS avg_pnl,
                MAX(CASE WHEN outcome='TP_HIT' THEN result_pct END) AS best_trade,
                AVG(CASE WHEN rr_ratio > 0 THEN rr_ratio END) AS avg_rr
            FROM ml_signals
            WHERE signal_quality = 'live'
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
            "avg_rr":        round(row["avg_rr"] or 0, 2),
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
                    "strategy_state"}
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
                   COUNT(CASE WHEN (outcome IS NULL OR outcome = 'PENDING') THEN 1 END) as active,
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
              AND LOWER(triggered_by) NOT IN (
                  'time','v2_persistence','telegram_recovery','v3_structure',
                  'event','event_monitor','eventmonitor'
              )
        """).fetchone()["cnt"]
        checks.append(_check(
            "signal_write_path",
            "PASS" if violations == 0 else "FAIL",
            f"{violations} unknown-source signal(s) in last 24h",
            "FAIL = signal written by unrecognised trigger source — investigate write path",
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
                       COUNT(CASE WHEN (outcome IS NULL OR outcome = 'PENDING')  THEN 1 END) as active,
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
        v2_rows = conn.execute(
            "SELECT COUNT(*) as cnt FROM strategy_state"
        ).fetchone()["cnt"]
        checks.append(_check(
            "v2_state_machine",
            "PASS" if v2_rows > 0 else "WARN",
            f"{v2_rows} state rows",
            "WARN = strategy_state empty — V2 state machine persistence broken",
        ))

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
                SELECT ticker, LOWER(interval) AS interval, timestamp
                FROM ml_signals
                GROUP BY ticker, LOWER(interval), timestamp
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
            WHERE outcome IS NOT NULL AND outcome != '' AND outcome != 'PENDING'
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
            WHERE (outcome IS NULL OR outcome = 'PENDING')
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
                "context": {
                    "compression": ctx_payload.get("compression_score") if ctx_payload else None,
                    "expansion":   ctx_payload.get("expansion_pressure") if ctx_payload else None,
                    "rsi_stage":   ctx_payload.get("rsi_stage") if ctx_payload else None,
                    "sweep":       bool(int(ctx_payload.get("liquidity_sweep") or 0)) if ctx_payload else False,
                } if ctx_payload else None,
                "signal": {
                    "direction":  _direction_label(sig["signal"]) if sig else None,
                    "interval":   (sig["interval"] or "").lower() or None if sig else None,
                    "entry":      sig["entry_price"] if sig else None,
                    "sl":         sig["stop_loss"] if sig else None,
                    "tp":         sig["take_profit"] if sig else None,
                    "outcome":    sig["outcome"] if sig else None,
                    "result_pct": round(sig["result_pct"] or 0, 2) if sig and sig["result_pct"] else running_pct,
                    "strategy":     _strategy_display_label(sig["strategy_version"]) if sig else None,
                    "strategy_raw": sig["strategy_version"] if sig else None,
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

    if exp >= 0.60:
        return "TRENDING"
    if exp >= 0.35:
        return "EMERGING"
    if comp < 0.80:
        return "COMPRESSION"
    if comp > 1.20 and exp < 0.25:
        return "EXHAUSTED"
    return "NEUTRAL"

def _compute_pressure_state(ctx: dict | None) -> str:
    """
    Compute pressure_readiness_score from context fields.
    Returns: 'EXTREME' | 'HIGH' | 'RISING' | 'LOW'

    Scoring:
      compression < 0.60 → +2
      compression < 0.80 → +1  (two-tier — more gradient across compression band)
      expansion   > 0.30 → +2
      rsi_stage in [1A, 1B, 1C] → +1
      Max score: 5

    State bands:
      5   → EXTREME
      4   → HIGH
      2-3 → RISING
      0-1 → LOW
    """
    if not ctx:
        return 'LOW'

    # Resolve compression — accept both key aliases
    comp = None
    for k in ['compression_score', 'compression', 'comp_score']:
        if k in ctx and ctx[k] is not None:
            comp = ctx[k]
            break

    # Resolve expansion — accept both key aliases
    exp = None
    for k in ['expansion_pressure', 'expansion', 'exp_pressure']:
        if k in ctx and ctx[k] is not None:
            exp = ctx[k]
            break

    # Resolve rsi_stage
    rsi = ctx.get('rsi_stage', '') or ''

    try:
        comp = float(comp) if comp is not None else 1.0
        exp  = float(exp)  if exp  is not None else 0.0
    except (TypeError, ValueError):
        return 'LOW'

    score = 0

    if   comp < 0.60: score += 2
    elif comp < 0.80: score += 1

    if exp > 0.30:
        score += 2

    if rsi in ('1A', '1B', '1C'):
        score += 1

    # Sweep probability discount — graduated, not binary
    # Requires sweep_probability in ctx (Phase 3 field)
    sweep_prob = None
    for k in ['sweep_probability']:
        if k in ctx and ctx[k] is not None:
            try:
                sweep_prob = float(ctx[k])
            except (TypeError, ValueError):
                sweep_prob = None
            break

    if sweep_prob is not None and sweep_prob >= 0.70 and score >= 3:
        score = max(0, score - 1)

    if score >= 5: return 'EXTREME'
    if score >= 4: return 'HIGH'
    if score >= 2: return 'RISING'
    return 'LOW'

def _compute_pressure_score(ctx: dict | None) -> int:
    """
    Returns raw pressure readiness score 0–5.
    Used for ranked sorting and the 5-segment visual bar.
    Mirrors _compute_pressure_state() scoring exactly.
    """
    if not ctx:
        return 0

    comp = None
    for k in ['compression_score', 'compression', 'comp_score']:
        if k in ctx and ctx[k] is not None:
            comp = ctx[k]
            break

    exp = None
    for k in ['expansion_pressure', 'expansion', 'exp_pressure']:
        if k in ctx and ctx[k] is not None:
            exp = ctx[k]
            break

    rsi = ctx.get('rsi_stage', '') or ''

    try:
        comp = float(comp) if comp is not None else 1.0
        exp  = float(exp)  if exp  is not None else 0.0
    except (TypeError, ValueError):
        return 0

    score = 0
    if   comp < 0.60: score += 2
    elif comp < 0.80: score += 1
    if exp > 0.30:    score += 2
    if rsi in ('1A', '1B', '1C'): score += 1

    # Mirror sweep discount from _compute_pressure_state()
    sweep_prob = None
    try:
        sp = ctx.get('sweep_probability') if ctx else None
        if sp is not None:
            sweep_prob = float(sp)
    except (TypeError, ValueError):
        sweep_prob = None

    if sweep_prob is not None and sweep_prob >= 0.70 and score >= 3:
        score = max(0, score - 1)

    return score


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
              AND outcome != 'PENDING'
              AND signal_quality = 'live'
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
              AND signal_quality = 'live'
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
                "interval":  (r["interval"] or "").lower() or None,
                "direction": _direction_label(r["signal"]),
                "entry":     r["entry_price"],
                "outcome":   r["outcome"],
                "result_pct": round(r["result_pct"] or 0, 2),
                "strategy":     _strategy_display_label(r["strategy_version"]),
                "strategy_raw": r["strategy_version"] or "v3",
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



# ─────────────────────────────────────────────────────────────────
# USER PREFERENCES
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/preferences", methods=["GET"])
@require_auth
def get_preferences():
    from mobile_preferences import get_all_preferences
    return jsonify(get_all_preferences())


@app.route("/api/mobile/preferences", methods=["POST"])
@require_auth
def update_preferences():
    from mobile_preferences import set_preference
    data = request.get_json() or {}
    ALLOWED = {"pressure_watch_alerts", "pulse_telegram_alerts", "rift_telegram_alerts"}
    updated = {}
    for key in ALLOWED:
        if key in data and isinstance(data[key], bool):
            set_preference(key, data[key])
            updated[key] = data[key]
    return jsonify({"updated": updated})


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
                    "rejection_strength": ctx_dict.get("rejection_strength"),
                    "breakout_quality":   ctx_dict.get("breakout_quality"),
                    "body_commitment":    ctx_dict.get("body_commitment"),
                    "sweep_probability":  ctx_dict.get("sweep_probability"),
                }

            # VOLUME_BREAKOUT -- check for recent event within last 4 hours
            volume_breakout_active = False
            try:
                vb_row = conn.execute(
                    "SELECT alerted_at FROM pressure_alert_log "
                    "WHERE ticker = ? AND alert_type = 'VOLUME_BREAKOUT' "
                    "AND alerted_at >= datetime('now', '-4 hours') "
                    "ORDER BY alerted_at DESC LIMIT 1",
                    (symbol,)
                ).fetchone()
                if vb_row:
                    volume_breakout_active = True
            except Exception:
                pass

            asset = {
                "symbol":      symbol,
                "direction":   row["direction"],
                "change_pct":  round(row["change_from_open_pct"] or 0, 4),
                "atr_pct":     round(row["atr_14_pct"] or 0, 4),
                "volume_24h":  row["volume_24h"],
                "market_state":   state,
            "pressure_state": _compute_pressure_state(ctx_summary),
            "pressure_score": _compute_pressure_score(ctx_summary),
                "volume_breakout": volume_breakout_active,
                "context":     ctx_summary,
                "signal": {
                    "direction": _direction_label(sig["signal"]) if sig else None,
                    "interval":  (sig["interval"] or "").lower() or None if sig else None,
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


@app.route("/api/mobile/volume/history/<ticker>", methods=["GET"])
@require_auth
def volume_history(ticker):
    interval = request.args.get("interval", "1h")
    limit    = min(int(request.args.get("limit", 48)), 200)
    try:
        conn = sqlite3.connect(SA_DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT ticker, interval, ts, raw_volume,
                   avg_volume_20, rvol, volume_surge,
                   divergence, vol_trend
            FROM volume_log
            WHERE ticker = ?
              AND LOWER(interval) = LOWER(?)
            ORDER BY ts DESC
            LIMIT ?
        """, (ticker.upper(), interval, limit)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mobile/volume/surges", methods=["GET"])
@require_auth
def volume_surges():
    """Recent surge events across all assets — last 24h."""
    try:
        conn = sqlite3.connect(SA_DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT ticker, interval, ts, rvol, vol_trend,
                   divergence
            FROM volume_log
            WHERE volume_surge = 1
              AND ts > datetime('now', '-24 hours')
            ORDER BY rvol DESC
            LIMIT 50
        """).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        return jsonify({"error": str(e)}), 500



# ─────────────────────────────────────────────────────────────────
# FLOW ENGINE ENDPOINTS
# ─────────────────────────────────────────────────────────────────

@app.route("/api/mobile/flow/candidates")
@require_auth
def flow_candidates_list():
    state_filter = request.args.get("state")
    try:
        limit  = min(int(request.args.get("limit",  50)), 200)
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid limit/offset"}), 400

    valid_states = {
        "DETECTED", "SWEEP_FOUND", "RETEST_PENDING",
        "ACCEPTANCE_BUILDING", "ACCEPTANCE_CONFIRMED", "EXPIRED"
    }
    if state_filter and state_filter not in valid_states:
        return jsonify({"error": "invalid state filter"}), 400

    try:
        conn = get_sa_db()
        join   = " LEFT JOIN ml_signals ms ON ms.id = fc.signal_id"
        conds  = (["fc.state = ?"] if state_filter else [])
        conds.append(
            "NOT (fc.state = 'DETECTED'"
            " AND ms.outcome IS NOT NULL"
            " AND ms.outcome NOT IN ('PENDING', ''))"
        )
        where  = "WHERE " + " AND ".join(conds)
        params = ([state_filter] if state_filter else [])

        total = conn.execute(
            "SELECT COUNT(*) FROM flow_candidates fc" + join + " " + where, params
        ).fetchone()[0]

        rows = conn.execute(
            "SELECT fc.id, fc.ticker, fc.direction, fc.state,"
            "       fc.current_score, fc.score_body, fc.score_cascade,"
            "       fc.score_rsi, fc.sweep_bonus, fc.sweep_type,"
            "       fc.sweep_wick_depth_pct, fc.sweep_volume_ratio,"
            "       fc.structural_level, fc.entry_price, fc.sl_price,"
            "       fc.tp_target, fc.detected_at, fc.sweep_candle_time,"
            "       fc.confirmed_at, fc.expires_at, fc.expiry_reason,"
            "       fc.created_at, fc.updated_at,"
            "       CASE"
            "         WHEN fc.state = 'ACCEPTANCE_CONFIRMED' THEN ms.outcome"
            "         WHEN fc.state = 'EXPIRED' THEN fc.expiry_reason"
            "         ELSE NULL"
            "       END AS outcome"
            " FROM flow_candidates fc"
            " LEFT JOIN ml_signals ms ON ms.id = fc.signal_id "
            + where +
            " ORDER BY fc.id DESC"
            " LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
        conn.close()

        return jsonify({
            "candidates": [dict(r) for r in rows],
            "total":  total,
            "limit":  limit,
            "offset": offset,
        })
    except Exception as e:
        log.error("[FLOW] /candidates error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/mobile/flow/candidate/<int:candidate_id>/log")
@require_auth
def flow_candidate_log(candidate_id):
    try:
        conn = get_sa_db()

        cand = conn.execute(
            "SELECT id, ticker, direction FROM flow_candidates WHERE id = ?",
            [candidate_id]
        ).fetchone()
        if not cand:
            conn.close()
            return jsonify({"error": "candidate not found"}), 404

        rows = conn.execute(
            "SELECT id, from_state, to_state, score_at_transition,"
            "       eval_time, notes"
            " FROM flow_state_log"
            " WHERE candidate_id = ?"
            " ORDER BY id ASC",
            [candidate_id]
        ).fetchall()
        conn.close()

        return jsonify({
            "candidate_id": cand["id"],
            "ticker":       cand["ticker"],
            "direction":    cand["direction"],
            "transitions":  [dict(r) for r in rows],
        })
    except Exception as e:
        log.error("[FLOW] /candidate/%s/log error: %s", candidate_id, e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/mobile/flow/aggregate")
@require_auth
def flow_aggregate():
    try:
        conn = get_sa_db()

        funnel = {s: 0 for s in [
            "DETECTED", "SWEEP_FOUND", "RETEST_PENDING",
            "ACCEPTANCE_BUILDING", "ACCEPTANCE_CONFIRMED", "EXPIRED"
        ]}
        for r in conn.execute(
            "SELECT state, COUNT(*) as cnt FROM flow_candidates GROUP BY state"
        ).fetchall():
            if r["state"] in funnel:
                funnel[r["state"]] = r["cnt"]

        oc_row = conn.execute(
            "SELECT"
            " SUM(CASE WHEN fc.flow_outcome = 'TP_HIT'  THEN 1 ELSE 0 END) as tp_hit,"
            " SUM(CASE WHEN fc.flow_outcome = 'SL_HIT'  THEN 1 ELSE 0 END) as sl_hit,"
            " SUM(CASE WHEN fc.flow_outcome = 'EXPIRY'  THEN 1 ELSE 0 END) as expiry,"
            " SUM(CASE WHEN fc.flow_outcome IS NULL     THEN 1 ELSE 0 END) as running,"
            " COUNT(fc.id) as ever_confirmed"
            " FROM flow_candidates fc"
            " WHERE fc.confirmed_at IS NOT NULL"
        ).fetchone()
        outcomes = {
            "TP_HIT":  oc_row["tp_hit"]  or 0,
            "SL_HIT":  oc_row["sl_hit"]  or 0,
            "EXPIRY":  oc_row["expiry"]  or 0,
            "RUNNING": oc_row["running"] or 0,
        }
        ever_confirmed = oc_row["ever_confirmed"] or 0

        time_rows = conn.execute(
            "SELECT detected_at, confirmed_at"
            " FROM flow_candidates"
            " WHERE confirmed_at IS NOT NULL"
            " AND detected_at IS NOT NULL"
        ).fetchall()
        conn.close()

        total = sum(funnel.values())
        confirmation_rate = round(ever_confirmed / total * 100, 1) if total > 0 else 0.0

        resolved_count = outcomes["TP_HIT"] + outcomes["SL_HIT"] + outcomes["EXPIRY"]
        tp = outcomes["TP_HIT"]
        sl = outcomes["SL_HIT"]
        win_rate = round(tp / (tp + sl) * 100, 1) if (tp + sl) >= 3 else None

        avg_confirm_hours = None
        if time_rows:
            deltas = []
            for r in time_rows:
                try:
                    det  = datetime.fromisoformat(r["detected_at"])
                    conf = datetime.fromisoformat(r["confirmed_at"])
                    if det.tzinfo is None:
                        det = det.replace(tzinfo=timezone.utc)
                    if conf.tzinfo is None:
                        conf = conf.replace(tzinfo=timezone.utc)
                    hrs = (conf - det).total_seconds() / 3600
                    if hrs >= 0:
                        deltas.append(hrs)
                except Exception:
                    pass
            if deltas:
                avg_confirm_hours = round(sum(deltas) / len(deltas), 1)

        return jsonify({
            "funnel":         funnel,
            "ever_confirmed": ever_confirmed,
            "outcomes":       outcomes,
            "metrics": {
                "total_candidates":           total,
                "confirmation_rate_pct":      confirmation_rate,
                "win_rate_pct":               win_rate,
                "avg_time_to_confirm_hours":  avg_confirm_hours,
                "resolved_count":             resolved_count,
                "ever_confirmed":             ever_confirmed,
            },
        })
    except Exception as e:
        log.error("[FLOW] /aggregate error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/mobile/flow/watchlist")
@require_auth
def flow_watchlist():
    try:
        conn = get_sa_db()
        rows = conn.execute(
            "SELECT fc.id, fc.ticker, fc.direction, fc.state,"
            "       fc.current_score, fc.detected_at, fc.expires_at,"
            "       fc.sweep_type, ms.outcome"
            " FROM flow_candidates fc"
            " LEFT JOIN ml_signals ms ON ms.id = fc.signal_id"
            " WHERE fc.state != 'EXPIRED'"
            " AND NOT (fc.state = 'ACCEPTANCE_CONFIRMED' AND ms.outcome IS NOT NULL)"
            " ORDER BY fc.id DESC"
        ).fetchall()
        conn.close()

        now = datetime.now(timezone.utc)
        open_candidates = []
        for r in rows:
            age_hours = None
            try:
                det = datetime.fromisoformat(r["detected_at"])
                if det.tzinfo is None:
                    det = det.replace(tzinfo=timezone.utc)
                age_hours = round((now - det).total_seconds() / 3600, 1)
            except Exception:
                pass
            c = dict(r)
            c["age_hours"] = age_hours
            c.pop("outcome", None)
            open_candidates.append(c)

        return jsonify({
            "open_candidates": open_candidates,
            "count": len(open_candidates),
        })
    except Exception as e:
        log.error("[FLOW] /watchlist error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/mobile/flow/funnel/<state>")
@require_auth
def flow_funnel_state(state):
    valid_states = {
        "DETECTED", "SWEEP_FOUND", "RETEST_PENDING",
        "ACCEPTANCE_BUILDING", "ACCEPTANCE_CONFIRMED", "EXPIRED"
    }
    if state not in valid_states:
        return jsonify({"error": "invalid state"}), 400

    try:
        limit  = min(int(request.args.get("limit",  50)), 200)
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid limit/offset"}), 400

    try:
        conn   = get_sa_db()
        join   = " LEFT JOIN ml_signals ms ON ms.id = fc.signal_id"
        conds  = ["fc.state = ?"]
        params = [state]
        if state == "DETECTED":
            conds.append(
                "NOT (ms.outcome IS NOT NULL"
                " AND ms.outcome NOT IN ('PENDING', ''))"
            )
        where = "WHERE " + " AND ".join(conds)

        count = conn.execute(
            "SELECT COUNT(*) FROM flow_candidates fc" + join + " " + where, params
        ).fetchone()[0]

        rows = conn.execute(
            "SELECT fc.id, fc.ticker, fc.direction, fc.state,"
            "       fc.current_score, fc.detected_at, fc.sweep_candle_time,"
            "       fc.sweep_type, fc.sweep_wick_depth_pct,"
            "       fc.entry_price, fc.sl_price, fc.tp_target,"
            "       fc.expiry_reason,"
            "       CASE"
            "         WHEN fc.state = 'ACCEPTANCE_CONFIRMED' THEN ms.outcome"
            "         WHEN fc.state = 'EXPIRED' THEN fc.expiry_reason"
            "         ELSE NULL"
            "       END AS outcome"
            " FROM flow_candidates fc"
            + join + " " + where +
            " ORDER BY fc.id DESC"
            " LIMIT ? OFFSET ?",
            params + [limit, offset]
        ).fetchall()
        conn.close()

        now = datetime.now(timezone.utc)
        candidates = []
        for r in rows:
            c = dict(r)
            age_hours = None
            try:
                det = datetime.fromisoformat(r["detected_at"])
                if det.tzinfo is None:
                    det = det.replace(tzinfo=timezone.utc)
                age_hours = round((now - det).total_seconds() / 3600, 1)
            except Exception:
                pass
            c["age_hours"] = age_hours
            candidates.append(c)

        return jsonify({
            "state":      state,
            "count":      count,
            "candidates": candidates,
        })
    except Exception as e:
        log.error("[FLOW] /funnel/%s error: %s", state, e, exc_info=True)
        return jsonify({"error": str(e)}), 500



@app.route("/api/mobile/flow/confirmed")
@require_auth
def flow_confirmed():
    try:
        limit  = min(int(request.args.get("limit",  50)), 200)
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid limit/offset"}), 400

    try:
        conn = get_sa_db()

        total = conn.execute(
            "SELECT COUNT(*) FROM flow_candidates WHERE confirmed_at IS NOT NULL"
        ).fetchone()[0]

        rows = conn.execute(
            "SELECT fc.id, fc.ticker, fc.direction, fc.state,"
            "       fc.current_score,"
            "       fc.score_body, fc.score_cascade, fc.score_rsi, fc.sweep_bonus,"
            "       fc.sweep_type, fc.sweep_wick_depth_pct, fc.sweep_volume_ratio,"
            "       fc.detected_at, fc.sweep_candle_time, fc.confirmed_at,"
            "       fc.entry_price, fc.sl_price, fc.tp_target,"
            "       fc.expiry_reason,"
            "       COALESCE(fc.flow_outcome, ms.outcome) AS outcome,"
            "       fc.flow_outcome,"
            "       fc.flow_resolved_at,"
            "       CASE"
            "         WHEN fc.flow_outcome IS NOT NULL THEN 'FLOW'"
            "         WHEN ms.outcome     IS NOT NULL THEN 'SIGNAL'"
            "         ELSE NULL"
            "       END AS outcome_source"
            " FROM flow_candidates fc"
            " LEFT JOIN ml_signals ms ON ms.id = fc.signal_id"
            " WHERE fc.confirmed_at IS NOT NULL"
            " ORDER BY fc.confirmed_at DESC"
            " LIMIT ? OFFSET ?",
            [limit, offset]
        ).fetchall()
        conn.close()

        tp   = sum(1 for r in rows if r["outcome"] == "TP_HIT")
        sl   = sum(1 for r in rows if r["outcome"] == "SL_HIT")
        run  = sum(1 for r in rows if not r["outcome"] or r["outcome"] == "PENDING")
        win_rate = round(tp / (tp + sl) * 100, 1) if (tp + sl) >= 3 else None

        return jsonify({
            "confirmed_plays": [dict(r) for r in rows],
            "total":  total,
            "limit":  limit,
            "offset": offset,
            "summary": {
                "tp_hit":       tp,
                "sl_hit":       sl,
                "running":      run,
                "win_rate_pct": win_rate,
            },
        })
    except Exception as e:
        log.error("[FLOW] /confirmed error: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info(f"SA Mobile API starting on port {PORT}")
    log.info(f"SA DB:   {SA_DB_PATH}")
    log.info(f"Auth DB: {AUTH_DB_PATH}")
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
