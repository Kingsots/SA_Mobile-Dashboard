# Hybrid Mode Logic Flow

## Decision Tree: When Do We Generate Signals?

```
Start Event Monitor Sweep (every 5 min)
│
├─ Load OHLCV data for symbol
│  │
│  ├─ NO DATA? → Skip symbol
│  │
│  ├─ Analyze for events
│  │  ├─ NO EVENTS? 
│  │  │  └─ Wait for next sweep
│  │  │
│  │  └─ EVENTS DETECTED?
│  │     ├─ Record: _last_event_time[symbol] = now
│  │     │
│  │     ├─ Check cooldown
│  │     │  ├─ IN COOLDOWN? 
│  │     │  │  └─ Skip (suppress spam)
│  │     │  │
│  │     │  └─ NO COOLDOWN? → Proceed
│  │     │
│  │     └─ Generate ML signal from event
│  │        ├─ Signal confidence inherited from event
│  │        ├─ Record: _last_signal_time[symbol] = now
│  │        ├─ Record: cooldown = 1 hour
│  │        └─ Send alert (🟢/🔴 emoji)
│
└─ Repeat for all symbols


Start Time-Based Fallback Job (every hour at :15)
│
├─ For each symbol in watchlist
│  │
│  ├─ Check: Last event time for this symbol?
│  │  │
│  │  ├─ NEVER had event? → Allow fallback
│  │  │
│  │  ├─ Had event < FALLBACK_HOURS (4h) ago?
│  │  │  └─ SKIP → Event-driven is active
│  │  │
│  │  └─ Had event >= 4h ago (or no recent)?
│  │     └─ ALLOW → Run time-based fallback
│  │
│  ├─ [For allowed symbols] Generate ML signal
│  │  ├─ Original model confidence: X%
│  │  ├─ CAP at: min(X, 60%)
│  │  ├─ Record: _last_signal_time[symbol] = now
│  │  └─ Send alert (🟡/🟠 emoji)
│  │
│  └─ [For skipped symbols] 
│     └─ Waiting for event or 4h+ quiet period
│
└─ All symbols checked
```

## State Transitions Per Symbol

```
SYMBOL: EURUSD (with events) vs GBPUSD (no events)
─────────────────────────────────────────────────

TIME  EVENT_MONITOR    EURUSD STATE              GBPUSD STATE
──────────────────────────────────────────────────────────────
00:00 Scan all         [Event detected]         [No event]
      ↓                _last_event_time=00:00   _last_event_time=null
      Signal gen       Cooldown=1h
      
00:05 Scan all         [Event detected]         [No event]
      ↓                Event logged             
      Skip signal      (in cooldown)
      
00:15 Fallback job     [Too recent]             [First time]
      ↓                Skip                     → Generate signal!
                       (cooldown=55min left)    _last_signal_time=00:15
                                                confidence capped at 60%
      
01:05 Scan all         [Event detected]         [No event]
      ↓                Event logged             
      Signal gen!      (cooldown expired)
      Cooldown=1h
      
02:15 Fallback job     [Too recent]             [Only 1h since signal]
      ↓                Skip                     Generate again? No!
                       (cooldown=50min left)    (signal cooldown active)
                                                Wait...
      
04:15 Fallback job     [Event 3h ago]           [Event 4h ago]
      ↓                Skip (< 4h rule)         → Generate signal!
                                                (4h threshold met)
                       
06:00 Scan all         [Event 5h+ ago]          [Event 6h+ ago]  
      ↓                → Allow fallback         [Too recent from 04:15]
      (no events)      at 06:15 if enabled      Wait for 06:15 fallback
```

## Confidence Capping Logic

```
Original Model Confidence
         │
         ├─ Event-Driven Signal
         │  └─ Use as-is (0.35 - 0.95)
         │     ├─ High confidence = likely breakout/crossover
         │     └─ Send as 🟢/🔴 alert
         │
         └─ Time-Based Fallback Signal
            └─ CAP at 60%
               ├─ If original > 60%: Cap to 60% (confidence -= margin)
               │  └─ Send as 🟡/🟠 alert (different treatment)
               │
               └─ If original <= 60%: Use as-is
                  └─ Send as 🟡/🟠 alert
```

## Cooldown Strategy

```
Symbol Cooldown: 1 hour (prevents same symbol bombarding)
─────────────────────────────────────────────────────────
If signal generated at 12:00:
  12:00-13:00  → No new signals for this symbol
  13:01        → Can generate signal again
  
Fallback Hours: 4 hours (decides when time-based runs)
──────────────────────────────────────────────────
If last event at 12:00:
  12:00-16:00  → Time-based skips (event within 4h)
  16:01+       → Time-based can run (4h elapsed)
```

## Decision Matrix

```
                    Event Detected?    Cooldown OK?    Result
                    ───────────────    ────────────    ──────
Path 1: EVENT       Yes                Yes             ✅ Signal (high conf)
                                                       Emoji: 🟢/🔴

Path 2: EVENT       Yes                No              ⏳ Skip (cooldown)
SUPPRESSED                                             Event timer resets

Path 3: FALLBACK    No in 4h            Yes            ✅ Signal (capped 60%)
ALLOWED                                                Emoji: 🟡/🟠

Path 4: FALLBACK    No in <4h           N/A            ⏳ Skip (too recent)
SKIPPED                                                Event active

Path 5: FALLBACK    Never had event     Yes            ✅ Signal (first time)
FIRST TIME                                             Emoji: 🟡/🟠
```

## Timing Diagram (1 hour cycle)

```
Minute  :00       :05       :10       :15       :20       :25
        │         │         │         │         │         │
Fetch   X────────→│         │         │         │         │
Data    [fetch_1h runs]     │         │         │         │
        │         │         │         │         │         │
Event   X────────→X────────→X────────→X────────→X────────→X
Monitor │         │         │         │         │         │
        [Scans every 5 min for events]          │         │
        │         │         │         │         │         │
Time    │         │         │         │         │         │
Based   │         │         │         X────────→│         │
        │         │         │         [Fallback]│         │
        │         │         │         │         │         │
        └─────────┴─────────┴─────────┴─────────┴─────────┘
        
Legend:
X = Job runs
→ = Data/signals flow
```

## Example: Real Market Scenario

```
SCENARIO: December 23, 2025 - 12:00 UTC Start

EURUSD (Good volatility):
  12:00  fetch_1h → 1,546 candles loaded
  12:05  event_monitor → EMA crossover detected!
         → Signal generated (conf: 0.75)
         → Cooldown: 1 hour
  12:10  event_monitor → Another crossover event
         → Event logged, signal suppressed (cooldown)
         → Timer reset: _last_event_time = 12:10
  12:15  time_based_fallback → Skip (event 5 min ago)
  13:15  time_based_fallback → Skip (event 65 min ago... wait, only 1h05m since LAST event)

GBPUSD (Smooth/quiet):
  12:00  fetch_1h → 1,546 candles loaded
  12:05  event_monitor → No events
  12:10  event_monitor → No events
  12:15  time_based_fallback → First time! Generate signal
         → Confidence: 0.68 → Capped to 0.60
         → Alert sent (🟡 emoji)
         → Cooldown: 1 hour on signal
  13:15  time_based_fallback → Cooldown active, skip
  14:15  time_based_fallback → Cooldown expired, but 4h timer not reached yet
         → Skip (no events detected yet)
  16:15  time_based_fallback → 4h since we last checked → Generate signal
         → New opportunity found via fallback!
```

---

This hybrid approach ensures:
✅ EVENT signals = Rare, high-confidence, technical inflections
✅ FALLBACK signals = Regular coverage for smooth market periods  
✅ NO signal spam = Cooldowns + confidence capping  
✅ FAIR to all symbols = Quiet symbols get fallback attention
