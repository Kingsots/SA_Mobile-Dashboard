CREATE TABLE IF NOT EXISTS invite_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    max_uses INTEGER DEFAULT 25,
    use_count INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    role TEXT DEFAULT 'beta',
    source_tag TEXT,
    campaign TEXT,
    issued_to TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS code_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    invite_code TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now')),
    expires_at TEXT,
    is_active INTEGER DEFAULT 1,
    ip_address TEXT,
    country TEXT,
    city TEXT,
    user_agent TEXT,
    FOREIGN KEY (invite_code) REFERENCES invite_codes(code)
);

CREATE TABLE IF NOT EXISTS session_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT,
    page TEXT,
    ts TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES code_sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_code ON code_sessions(invite_code);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON code_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_events_session ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON session_events(event_type);
