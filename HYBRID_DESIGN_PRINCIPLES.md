# Hybrid Mode Design Principles

**Why this approach? What makes it robust?**

---

## The Problem We Solved

### Pure Event-Driven Failure Modes

```
❌ Problem 1: "Starving for Signals"
   Market stays calm → No technical events fire
   Result: Bot waits hours, missing opportunities
   Example: Smooth forex trend (0.04% daily move)
   
❌ Problem 2: "All or Nothing"
   System lives/dies on event detection quality
   One broken detector = whole system fails
   Risk: Too much dependency on event logic
   
❌ Problem 3: "Waiting for Perfect Setup"
   Only acts on "clean" technical events
   Valid trades with messy entry → Ignored
   Misses: 60% of profitable moves (rough estimate)
```

### Pure Time-Based Failure Modes

```
❌ Problem 1: "Forced Trading"
   Generates signals on schedule regardless of conditions
   During news, gap opens → Gets whipsawed
   During maintenance, market halted → Useless signals
   
❌ Problem 2: "Alert Fatigue"
   Running every hour × 12 symbols = 12 alerts/hour
   Trader ignores alerts (too many)
   Risk: Miss the ONE good signal in the noise
   
❌ Problem 3: "No Urgency Signal"
   Can't distinguish "rare technical event" from "scheduled scan"
   All signals look the same confidence
   Can't prioritize which signals matter most
```

---

## Our Solution: Hybrid Mode

### Design Principle 1: PRIMARY Event-Driven

**Philosophy**: "Let events speak"
- Technical events are **rare and valuable**
- When market shows clear inflection → Act immediately
- No need to wait for schedule

**Implementation**:
```
Event Monitor (every 5 min)
  ↓
Detects technical event?
  ↓
YES → Generate signal immediately
      (don't wait for schedule)
      
NO  → Continue watching
      (no signal needed yet)
```

**Benefits**:
- ✅ Captures rare high-quality signals
- ✅ No forced trading
- ✅ Natural market response
- ✅ Low-frequency (3-5 signals/day realistic)

---

### Design Principle 2: FALLBACK Time-Based

**Philosophy**: "Ensure coverage"
- After 4 hours of quiet → Run scheduled scan
- Guarantees symbols don't get ignored indefinitely
- But: With confidence cap to show it's "routine"

**Implementation**:
```
Time-Based Fallback (every hour at :15)
  ↓
For each symbol:
  ↓
Last event > 4 hours ago?
  ↓
YES → Generate signal (capped confidence)
      (it's been quiet, but valid setup detected)
      
NO  → Skip (event-driven active, no need)
      (system already attentive to this symbol)
```

**Benefits**:
- ✅ No symbol gets ignored 4+ hours
- ✅ But respects event-driven priority
- ✅ Prevents forced trading on quiet markets
- ✅ Confidence cap = AI knows "this was scheduled"

---

### Design Principle 3: Smart Cooldowns

**Philosophy**: "No spam, but fair"

```
Two layers:

Layer 1: Signal Cooldown (1 hour/symbol)
├─ After signal generated → No new signals for 1h
├─ Purpose: Prevent whipsaws on same setup
└─ Applies to: Both event and fallback signals

Layer 2: Event Fallback Timer (4 hours)
├─ Tracks: When was last event detected?
├─ If no events in 4h → Fallback eligible
├─ Purpose: Switch to fallback if event-driven quiet
└─ Resets on: Any event detection (even if cooled down)
```

**Example**:
```
12:00 Event detected → Signal generated, cooldown=1h
12:05 Another event → Detected (not cooled down yet!)
      Event timer resets: _last_event_time = 12:05
      Signal still cooled down: no new signal
13:00 Signal cooldown expires
      But event timer = 55 min ago (< 4h threshold)
      So: Event-driven mode still active
      If new event → Can generate signal
14:00 Still in event-driven mode (55 + 60 = 115 min since event)
      Wait for event or hit 4-hour threshold
```

**Why this works**:
- ✅ Event detection gets **priority** over scheduled
- ✅ Event timer resets even on suppressed events (keeps system attentive)
- ✅ Signal cooldown prevents rapid fire on one setup
- ✅ 4-hour rule guarantees fallback if truly dormant

---

### Design Principle 4: Confidence Capping

**Philosophy**: "Signal quality = signal source"

```
Confidence levels mean different things:

Event-Driven Signal (0.35 - 0.95):
├─ High confidence = Strong technical event detected
├─ Example: 0.75 = Clear EMA crossover with good separation
└─ AI should: Weight heavily, smaller position OK

Time-Based Fallback (capped at 0.60):
├─ Signal detected but NO special event
├─ Example: Original 0.72 → Capped to 0.60
├─ AI should: Weight lightly, reduce position size
└─ Context: Just scheduled check, not urgent
```

**Why cap?**
1. **Differentiation**: Same confidence = different weight by source
2. **Risk management**: Fallback signals = less confident entry
3. **AI friendly**: Can use source + confidence together
4. **Honest signaling**: Don't pretend fallback = event

**Example Weighting**:
```
Signal: EURUSD Long (Event-Driven, conf: 0.75)
  → AI position size: 100% of normal

Signal: GBPUSD Long (Fallback, conf: 0.60)
  → AI position size: 75% of normal (reduced for fallback)
  
Same confidence could mean:
Event: "Textbook breakout (urgency!)"
Fallback: "Valid setup but routine check (less urgent)"
```

---

## Why This Design Is Robust

### 1. Fault Tolerance
```
If event detector breaks:
  ✅ Fallback takes over (can still trade)
  ✅ System doesn't die
  
If fallback fails:
  ✅ Event-driven still working
  ✅ Won't miss real setups
  
If both work:
  ✅ Maximum coverage (best case)
```

### 2. Natural Market Response
```
Calm market (common in forex):
  ✅ Event monitor: Quiet
  ✅ Fallback: Takes over at 4h boundary
  ✅ Result: Reasonable signal frequency (~1/4h)
  
Volatile market:
  ✅ Event monitor: Firing multiple times
  ✅ Fallback: Likely skipped (event active)
  ✅ Result: High signal frequency (natural!)
```

### 3. AI-Friendly Signals
```
Trader can implement smart rules:

IF signal_source == 'event_monitor':
  Use confidence as-is
  Position size = 100%
  
ELIF signal_source == 'fallback':
  Reduce confidence slightly
  Position size = 70%
  
Result: 
  System generates ALL signals
  AI weights by quality (source matters)
```

### 4. No Forced Trading
```
Compare approaches:

Pure time-based:
  13:00 → Generate signal (schedule says so)
  13:01 → News release (market spikes)
  13:02 → Stop out
  😱 Trading forced by schedule, not market

Hybrid:
  13:00 → No event, no signal needed
  13:01 → News release (market spikes)
  13:02 → Event detected (volatility!)
  13:03 → Signal generated (market-driven)
  😊 Trading driven by market, not schedule
```

---

## Tuning Parameters

If behavior isn't right, adjust these:

### Adjust Event Sensitivity
```python
# In signals/event_monitor.py
EventMonitorConfig(
    min_confidence=0.35,      # Lower = more events
    structure_lookback=15,    # Lower = faster detection
    ...
)

More events needed?
  → Reduce min_confidence to 0.25
  → Reduce structure_lookback to 10

Too many false events?
  → Increase min_confidence to 0.45
  → Increase structure_lookback to 20
```

### Adjust Fallback Frequency
```python
# In async_scheduler.py
self.FALLBACK_HOURS = 4     # Lower = more fallback signals

More fallback signals?
  → Set to 2 (run every 2 hours without events)
  
Less fallback signals?
  → Set to 8 (only run after 8 hours dormant)
```

### Adjust Confidence Capping
```python
# In async_scheduler.py
self.TIME_BASED_MAX_CONFIDENCE = 0.6

To trust fallback more:
  → Set to 0.75 (closer to event confidence)
  
To distrust fallback:
  → Set to 0.40 (much lower)
```

---

## Real-World Behavior

### Scenario 1: Calm Forex Day
```
00:00 - Fetch data
00:05 - Event monitor: No events
00:10 - Event monitor: No events
00:15 - Fallback: First check, generates 5 signals
        (XAUUSD, USDJPY, GBPUSD, EURUSD, AUDUSD)
        
00:20 - Event monitor: No events
...repeat until...

04:00 - Fetch 1h data
04:05 - Event monitor: No events  ← Still nothing
04:15 - Fallback: 4 hours passed, generates 5 more signals

08:00 - Fetch 1h data
...

Result:
- Event monitor: 0 signals (market too calm)
- Fallback: ~6 signals (every 4 hours)
- Total: 6 signals in 24 hours (reasonable!)
```

### Scenario 2: Volatile Day
```
10:00 - Fetch data
10:05 - Event monitor: EMA crossover! Signal (conf: 0.73)
        _last_event_time[EURUSD] = 10:05

10:10 - Event monitor: Another event on EURUSD!
        Cooldown active → Signal suppressed
        But: _last_event_time resets = 10:10

10:15 - Fallback: EURUSD only 5 min ago → Skip (< 4h)
        Other symbols → Check (never had events)
        Generates 4 signals (USDJPY, GBPUSD, XAUUSD, etc)

10:20 - Event monitor: Breakout on GBPUSD!
        Signal (conf: 0.68)
        _last_event_time[GBPUSD] = 10:20

11:05 - Event monitor: EURUSD cooldown expired
        New event detected → Signal (conf: 0.82)
        
Result:
- Event monitor: 3 signals (real events)
- Fallback: 4 signals (routine checks)
- Total: 7 signals in 1 hour (very active market!)
```

---

## Why This Beats Alternatives

### vs. Pure Event-Driven
```
Hybrid WINS because:
  ✅ Never starves on quiet markets
  ✅ Always have backup (fallback)
  ✅ Lower risk of detector failure
  
Pure event-driven WINS when:
  ❌ None really (hybrid covers it)
```

### vs. Pure Time-Based
```
Hybrid WINS because:
  ✅ Doesn't force trades
  ✅ Respects market conditions
  ✅ Can differentiate signal quality
  
Pure time-based WINS when:
  ❌ None really (hybrid covers it)
```

### vs. Weighted Combination
```
Hybrid WINS because:
  ✅ Clear priority (event first)
  ✅ Simpler to understand/tune
  ✅ Doesn't mix signals
  
Weighted combo WINS when:
  ❌ Need super complex weighting
  (But introduces more problems)
```

---

## Future Improvements

### Short-term (Easy)
- [ ] Tune FALLBACK_HOURS based on symbol type (forex vs crypto)
- [ ] Adaptive TIME_BASED_MAX_CONFIDENCE by asset
- [ ] Log fallback skip reasons (for debugging)

### Medium-term (Moderate)
- [ ] Symbol-specific event thresholds
- [ ] Confidence feedback loop (improve capping)
- [ ] Event clustering (group nearby events)

### Long-term (Complex)
- [ ] Machine learning on event effectiveness
- [ ] Dynamic FALLBACK_HOURS (increase if win rate dropping)
- [ ] Multi-timeframe event correlation

---

## Conclusion

**Hybrid mode is the sweet spot:**

```
   Risk       ↑
   │          │
   │      Pure Time ● (High false alarms)
   │              \
   │                 \
   │                    ● Hybrid (Best of both)
   │                   /
   │                  /
   │      Pure Event ● (Misses calm periods)
   │      
   └─────────────────────→ Coverage
   Low            High
```

We get:
- ✅ **High coverage** (events + fallback)
- ✅ **Low false alarms** (event-driven priority)
- ✅ **Natural responses** (market-driven)
- ✅ **Fault tolerance** (dual mode)
- ✅ **AI-friendly** (source + confidence)

This is a **production-grade signal generation system**.

---

**Design Document**: 2025-12-23  
**Implementation**: Complete  
**Status**: ✅ Live on EC2
