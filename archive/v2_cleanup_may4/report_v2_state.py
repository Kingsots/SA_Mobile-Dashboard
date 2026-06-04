"""
Report current V2 strategy state (stages 1A→3) and list armed entry windows.

Run: python tools/report_v2_state.py

This script reads the `strategy_state` table from the configured DB and
prints a concise stage summary and the rows where entry windows are armed.
"""
import sqlite3
from datetime import datetime
from core.config import Config


DB_PATH = Config.DB_PATH


def row_stage(row):
    # row is a dict with keys matching strategy_state columns we select
    if row['bull_entry_armed'] or row['bear_entry_armed']:
        return 'Stage 2 (Entry Window - armed)'
    if row['bull_retest_done'] or row['bear_retest_done']:
        return 'Stage 1C (Retest Done)'
    if row['bull_break_bar'] is not None or row['bear_break_bar'] is not None:
        return 'Stage 1B (Break)'
    if row['bull_extreme_visited'] or row['bear_extreme_visited']:
        return 'Stage 1A (Extreme)'
    return 'Scanning'


def fetch_states():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute('''
    SELECT ticker, interval,
           bull_extreme_visited, bear_extreme_visited, extreme_bar,
           bull_break_bar, bear_break_bar,
           bull_retest_done, bear_retest_done, bull_retest_bar, bear_retest_bar,
           bull_entry_armed, bear_entry_armed, bull_entry_window_bar, bear_entry_window_bar,
           last_processed_bar_time, last_updated
    FROM strategy_state
    ''')

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def summarize(rows):
    counts = {}
    stage_rows = {}
    for r in rows:
        stage = row_stage(r)
        counts[stage] = counts.get(stage, 0) + 1
        stage_rows.setdefault(stage, []).append(r)
    return counts, stage_rows


def print_summary(counts):
    print('\nV2 Stage Summary:')
    for stage in ['Stage 2 (Entry Window - armed)', 'Stage 1C (Retest Done)',
                  'Stage 1B (Break)', 'Stage 1A (Extreme)', 'Scanning']:
        print(f"  {stage:30} : {counts.get(stage, 0)}")


def print_armed(stage_rows):
    armed = stage_rows.get('Stage 2 (Entry Window - armed)', [])
    if not armed:
        print('\nNo armed entry windows found.')
        return

    print('\nArmed Entry Windows (Stage 2):')
    for r in armed:
        print(f"  {r['ticker']} {r['interval']:>3}  | bull_armed={bool(r['bull_entry_armed'])}"
              f" bull_window={r['bull_entry_window_bar']} | bear_armed={bool(r['bear_entry_armed'])}"
              f" bear_window={r['bear_entry_window_bar']} | last_updated={r.get('last_updated')}")


def print_detailed(stage_rows, stage_name):
    rows = stage_rows.get(stage_name, [])
    if not rows:
        return
    print(f"\n{stage_name} - examples (up to 10):")
    for r in rows[:10]:
        print(f"  {r['ticker']} {r['interval']:>3}  | extreme={bool(r['bull_extreme_visited'] or r['bear_extreme_visited'])}"
              f" break=(bull:{r['bull_break_bar']}, bear:{r['bear_break_bar']})"
              f" retest=(bull:{bool(r['bull_retest_done'])}, bear:{bool(r['bear_retest_done'])})"
              f" last_updated={r.get('last_updated')}")


def main():
    print('Reading V2 strategy_state from:', DB_PATH)
    rows = fetch_states()
    counts, stage_rows = summarize(rows)

    print_summary(counts)
    print_armed(stage_rows)

    # Print example rows for other stages
    print_detailed(stage_rows, 'Stage 1C (Retest Done)')
    print_detailed(stage_rows, 'Stage 1B (Break)')
    print_detailed(stage_rows, 'Stage 1A (Extreme)')

    # Quick note about symbols monitored
    from core.config import Config
    symbols = Config.get_symbol_list()
    print(f"\nSymbols monitored: {len(symbols)} ({', '.join(symbols)})")


if __name__ == '__main__':
    main()
