#!/bin/bash

usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')

if [ "$usage" -gt 90 ]; then
    echo "⚠ Silent Analyst Disk Alert: $usage% full" >> /home/ubuntu/SilentAnalyst/logs/disk_guard.log
    echo "$(date -u '+%Y-%m-%d %H:%M:%S UTC') - Disk usage: $usage%" >> /home/ubuntu/SilentAnalyst/logs/disk_guard.log
fi
