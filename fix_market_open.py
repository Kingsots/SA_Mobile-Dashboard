#!/usr/bin/env python3

with open('/home/ubuntu/SilentAnalyst/core/config.py', 'r') as f:
    lines = f.readlines()

# Find the is_market_open function and replace it
new_lines = []
i = 0
while i < len(lines):
    if i == 468 and '@classmethod' in lines[i]:
        # Write new function (replacing old 15-line function)
        new_lines.append('    @classmethod\n')
        new_lines.append('    def is_market_open(cls):\n')
        new_lines.append('        """\n')
        new_lines.append('        Forex market is open 22:00 UTC Sunday to 22:00 UTC Friday.\n')
        new_lines.append('        """\n')
        new_lines.append('        from datetime import datetime, timezone\n')
        new_lines.append('        now = datetime.now(timezone.utc)\n')
        new_lines.append('        weekday = now.weekday()  # 0=Mon, 6=Sun\n')
        new_lines.append('        hour = now.hour\n')
        new_lines.append('\n')
        new_lines.append('        # Saturday entirely closed\n')
        new_lines.append('        if weekday == 5:\n')
        new_lines.append('            return False\n')
        new_lines.append('\n')
        new_lines.append('        # Sunday  only open from 22:00 UTC onwards\n')
        new_lines.append('        if weekday == 6:\n')
        new_lines.append('            return hour >= 22\n')
        new_lines.append('\n')
        new_lines.append('        # Friday  closed from 22:00 UTC onwards\n')
        new_lines.append('        if weekday == 4:\n')
        new_lines.append('            return hour < 22\n')
        new_lines.append('\n')
        new_lines.append('        # Monday to Thursday  always open\n')
        new_lines.append('        return True\n')
        i += 15
    else:
        new_lines.append(lines[i])
        i += 1

with open('/home/ubuntu/SilentAnalyst/core/config.py', 'w') as f:
    f.writelines(new_lines)

print("RESULT: SUCCESS")
