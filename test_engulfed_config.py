from signals.event_monitor import EventMonitor
em = EventMonitor()
print("EventMonitor OK")
print(f"Engulfed range lookback: {em.config.engulfed_range_lookback}")
print(f"Engulfed min break pips: {em.config.engulfed_min_break_pips}")
print(f"Engulfed volume mult: {em.config.engulfed_min_volume_mult}")
print("All parameters loaded successfully!")
