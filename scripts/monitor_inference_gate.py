#!/usr/bin/env python3
"""
Real-time monitoring script for inference gate diagnostics
Monitors signal_debug.log for [DEBUG], [NaN_TRAP], and [INFERENCE_GATE] markers
"""

import os
import re
import sys
import time
import platform
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import json

# For Windows compatibility
if platform.system() == "Windows":
    import colorama
    colorama.init()


class DiagnosticMonitor:
    """Monitor inference gate and NaN trap patterns in logs"""
    
    MARKERS = {
        'DEBUG': r'\[DEBUG\]',
        'NaN_TRAP': r'\[NaN_TRAP\]',
        'INFERENCE_GATE': r'\[INFERENCE_GATE\]',
    }
    
    def __init__(self, log_file='logs/signal_debug.log', lookback_hours=1):
        self.log_file = Path(log_file)
        self.lookback_hours = lookback_hours
        self.last_position = 0
        self.stats = defaultdict(int)
        self.gate_rejections = defaultdict(list)
        self.nan_traps = []
        self.last_report_time = datetime.now()
        
    def read_new_lines(self):
        """Read new lines from log file since last position"""
        if not self.log_file.exists():
            print(f"⚠️  Log file not found: {self.log_file}")
            return []
        
        try:
            with open(self.log_file, 'r') as f:
                f.seek(self.last_position)
                lines = f.readlines()
                self.last_position = f.tell()
                return lines
        except Exception as e:
            print(f"❌ Error reading log: {e}")
            return []
    
    def parse_line(self, line):
        """Extract marker info from log line"""
        results = []
        
        for marker_name, pattern in self.MARKERS.items():
            if re.search(pattern, line):
                results.append({
                    'marker': marker_name,
                    'line': line.strip(),
                    'timestamp': datetime.now(),
                })
                self.stats[marker_name] += 1
                
                # Extract gate rejection details
                if marker_name == 'INFERENCE_GATE':
                    gate_match = re.search(
                        r'INFERENCE_GATE.*?(?:for\s+(\w+)|\s+(\w+)\s+\d+[mhd])',
                        line
                    )
                    if gate_match:
                        symbol = gate_match.group(1) or gate_match.group(2)
                        if symbol:
                            self.gate_rejections[symbol].append(
                                {
                                    'timestamp': datetime.now(),
                                    'line': line.strip(),
                                }
                            )
                
                # Track NaN traps
                if marker_name == 'NaN_TRAP':
                    self.nan_traps.append(
                        {
                            'timestamp': datetime.now(),
                            'line': line.strip(),
                        }
                    )
        
        return results
    
    def monitor_once(self, verbose=True):
        """Read logs once and process new lines"""
        new_lines = self.read_new_lines()
        
        for line in new_lines:
            matches = self.parse_line(line)
            if matches and verbose:
                for match in matches:
                    self.print_marker(match)
    
    def print_marker(self, match):
        """Print a marker with formatting"""
        marker = match['marker']
        line = match['line']
        
        if marker == 'INFERENCE_GATE':
            color = '\033[93m'  # Yellow
            icon = '⏸️ '
        elif marker == 'NaN_TRAP':
            color = '\033[91m'  # Red
            icon = '⚠️ '
        elif marker == 'DEBUG':
            color = '\033[94m'  # Blue
            icon = '🔧'
        else:
            color = '\033[0m'  # Reset
            icon = '•'
        
        reset = '\033[0m'
        timestamp = match['timestamp'].strftime('%H:%M:%S')
        print(f"{icon} {color}[{timestamp}]{reset} {line}")
    
    def print_summary(self):
        """Print statistics summary"""
        print("\n" + "="*70)
        print(f"📊 DIAGNOSTIC SUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # Marker counts
        print("\nMarker Counts:")
        for marker in ['INFERENCE_GATE', 'NaN_TRAP', 'DEBUG']:
            count = self.stats[marker]
            icon = '✅' if count > 0 or marker != 'NaN_TRAP' else '❌'
            print(f"  {icon} {marker:20} : {count:5}")
        
        # Gate rejections by symbol
        if self.gate_rejections:
            print("\nInference Gate Rejections by Symbol:")
            for symbol in sorted(self.gate_rejections.keys()):
                count = len(self.gate_rejections[symbol])
                print(f"  ⏸️  {symbol:12} : {count:3} rejections")
        
        # NaN trap details
        if self.nan_traps:
            print(f"\n⚠️  NaN Trap Warnings ({len(self.nan_traps)}):")
            for trap in self.nan_traps[-5:]:  # Last 5
                print(f"  → {trap['line'][:80]}")
            if len(self.nan_traps) > 5:
                print(f"  ... and {len(self.nan_traps) - 5} more")
        else:
            print(f"\n✅ No NaN Trap warnings (gate is working!)")
        
        print("="*70 + "\n")
    
    def export_json(self, output_file='logs/diagnostic_summary.json'):
        """Export summary to JSON"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'lookback_hours': self.lookback_hours,
            'stats': dict(self.stats),
            'gate_rejections_by_symbol': {
                symbol: len(rejections)
                for symbol, rejections in self.gate_rejections.items()
            },
            'nan_trap_count': len(self.nan_traps),
            'nan_trap_total_per_symbol': self._count_nan_traps_by_symbol(),
        }
        
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            print(f"✅ Summary exported to {output_file}")
        except Exception as e:
            print(f"❌ Error exporting summary: {e}")
    
    def _count_nan_traps_by_symbol(self):
        """Count NaN traps by extracting symbol from line"""
        counts = defaultdict(int)
        for trap in self.nan_traps:
            # Try to extract symbol from NaN_TRAP line
            match = re.search(r'NaN.*?(\w{3,6})\s', trap['line'])
            if match:
                symbol = match.group(1)
                counts[symbol] += 1
        return dict(counts)


def main():
    """Main monitoring loop"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Monitor inference gate and diagnostic markers'
    )
    parser.add_argument(
        '--log-file',
        default='logs/signal_debug.log',
        help='Path to signal debug log (default: logs/signal_debug.log)',
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Update interval in seconds (default: 5)',
    )
    parser.add_argument(
        '--report-interval',
        type=int,
        default=60,
        help='Summary report interval in seconds (default: 60)',
    )
    parser.add_argument(
        '--export-json',
        action='store_true',
        help='Export summary to JSON after each report',
    )
    parser.add_argument(
        '--lookback-hours',
        type=int,
        default=1,
        help='Lookback hours for initial summary (default: 1)',
    )
    
    args = parser.parse_args()
    
    monitor = DiagnosticMonitor(
        log_file=args.log_file,
        lookback_hours=args.lookback_hours,
    )
    
    print("\n" + "="*70)
    print("🔍 INFERENCE GATE DIAGNOSTIC MONITOR")
    print("="*70)
    print(f"📁 Log file: {monitor.log_file}")
    print(f"⏱️  Update interval: {args.interval}s")
    print(f"📊 Report interval: {args.report_interval}s")
    print("🔎 Monitoring markers: [DEBUG], [NaN_TRAP], [INFERENCE_GATE]")
    print("="*70 + "\n")
    
    try:
        last_report = datetime.now()
        
        while True:
            # Monitor for new lines
            monitor.monitor_once(verbose=True)
            
            # Periodic summary
            now = datetime.now()
            if (now - last_report).total_seconds() >= args.report_interval:
                monitor.print_summary()
                if args.export_json:
                    monitor.export_json()
                last_report = now
            
            time.sleep(args.interval)
    
    except KeyboardInterrupt:
        print("\n\n" + "="*70)
        print("🛑 MONITOR STOPPED")
        print("="*70)
        monitor.print_summary()
        if args.export_json:
            monitor.export_json()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
