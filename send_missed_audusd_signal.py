#!/usr/bin/env python3
"""
Manually send the missed AUDUSD signal to Telegram
"""

import sys
sys.path.insert(0, '/home/ubuntu/SilentAnalyst')

from alerts.telegram_bot import TelegramBot
import asyncio

async def send_missed_signal():
    # AUDUSD signal details from 13:30 UTC event
    ticker = 'AUDUSD'
    signal_dir = -1  # SELL
    confidence = 1.0
    entry = 0.70999
    sl = 0.71138
    tp = 0.7072
    ts = '2026-02-27T13:30:00+00:00'
    
    print(f"✅ Sending missed signal:")
    print(f"   Ticker: {ticker}")
    print(f"   Direction: {'SELL' if signal_dir == -1 else 'BUY'} ({signal_dir})")
    print(f"   Confidence: {confidence:.2%}")
    print(f"   Entry: {entry:.5f}")
    print(f"   SL: {sl:.5f}")
    print(f"   TP: {tp:.5f}")
    print(f"   Timestamp: {ts}")
    
    # Initialize Telegram bot
    telegram_bot = TelegramBot()
    
    # Format and send message
    emoji = "🔴" if signal_dir == -1 else "🟢"
    signal_label = "SELL" if signal_dir == -1 else "BUY"
    
    message = (
        f"{emoji} <b>Event Signal Alert</b>\n\n"
        f"<b>Symbol:</b> {ticker}\n"
        f"<b>Signal:</b> {signal_label}\n"
        f"<b>Confidence:</b> {confidence:.2%}\n\n"
        f"<b>Entry Price:</b> {entry:.5f}\n"
        f"<b>Stop Loss:</b> {sl:.5f}\n"
        f"<b>Take Profit:</b> {tp:.5f}\n\n"
        f"<b>Time:</b> {ts}\n"
        f"<i>Event: trendline_break_support</i>"
    )
    
    try:
        # Send the message
        result = await telegram_bot.send_message(message)
        print(f"\n✅ Message sent successfully!")
        print(f"   Result: {result}")
    except Exception as e:
        print(f"\n❌ Failed to send message: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(send_missed_signal())
