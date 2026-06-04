#!/usr/bin/env python3
"""
Simple Alert Bot - Generate signals from existing data
"""

import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta

print("🚀 Simple Alert Bot - Starting...")
print("=" * 50)

# Technical Analysis Functions
def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index"""
    if len(prices) < period + 1:
        return 50.0
    try:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        result = float(rsi.iloc[-1])
        return result if not pd.isna(result) else 50.0
    except:
        return 50.0

def calculate_ema(prices, period):
    """Calculate Exponential Moving Average"""
    return float(prices.ewm(span=period).mean().iloc[-1])

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    try:
        high = df['high']
        low = df['low']
        close = df['close']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        return float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
    except:
        return 0.0

def calculate_volatility(df):
    """Calculate volatility as standard deviation of returns"""
    returns = df['close'].pct_change().dropna()
    return float(returns.std() * 100) if len(returns) > 0 else 1.0

def generate_signal(df, indicators):
    """Generate trading signal based on rules"""
    if df is None or indicators is None:
        return {"signal": "HOLD", "confidence": 0}
    
    try:
        current_close = df['close'].iloc[-1]
        previous_close = df['close'].iloc[-2]
        current_open = df['open'].iloc[-1]
        previous_open = df['open'].iloc[-2]
        
        bullish_score = 0
        bearish_score = 0
        
        if indicators['ema_12'] > indicators['ema_26']:
            bullish_score += 1
        else:
            bearish_score += 1
        
        if indicators['rsi'] < 30:
            bullish_score += 1
        elif indicators['rsi'] > 70:
            bearish_score += 1
        elif 40 <= indicators['rsi'] <= 60:
            if bullish_score > bearish_score:
                bullish_score += 0.5
            else:
                bearish_score += 0.5
        
        is_bullish_engulfing = (
            current_close > current_open and
            previous_close < previous_open and
            current_open < previous_close and
            current_close > previous_open
        )
        is_bearish_engulfing = (
            current_close < current_open and
            previous_close > previous_open and
            current_open > previous_close and
            current_close < previous_open
        )
        
        if is_bullish_engulfing:
            bullish_score += 2
        elif is_bearish_engulfing:
            bearish_score += 2
        
        if indicators['volatility'] > 3.0:
            bullish_score *= 0.7
            bearish_score *= 0.7
        
        if bullish_score > bearish_score + 1:
            confidence = min(95, bullish_score * 20)
            return {"signal": "BUY", "confidence": confidence}
        elif bearish_score > bullish_score + 1:
            confidence = min(95, bearish_score * 20)
            return {"signal": "SELL", "confidence": confidence}
        else:
            return {"signal": "HOLD", "confidence": 0}
    
    except Exception as e:
        print(f"Signal generation error: {str(e)}")
        return {"signal": "HOLD", "confidence": 0}

# Main function to generate alerts
def generate_alerts():
    """Generate trading alerts from database data"""
    db_path = "trading_bot.db"
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Get list of symbols in database
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT symbol FROM ohlcv_data")
        symbols = [row[0] for row in cursor.fetchall()]
        
        print(f"Found {len(symbols)} symbols in database: {symbols}")
        
        alerts = []
        
        for symbol in symbols:
            print(f"\n📊 Analyzing {symbol}...")
            
            # Get the most recent data for this symbol
            query = f"""
            SELECT timestamp, open, high, low, close, volume 
            FROM ohlcv_data 
            WHERE symbol = ? 
            ORDER BY timestamp DESC 
            LIMIT 100
            """
            
            df = pd.read_sql_query(query, conn, params=(symbol,), parse_dates=['timestamp'])
            
            if df.empty or len(df) < 20:
                print(f"  ❌ Not enough data for {symbol}")
                continue
            
            # Set timestamp as index
            df = df.set_index('timestamp')
            
            # Calculate indicators
            indicators = {}
            indicators['rsi'] = calculate_rsi(df['close'])
            indicators['ema_12'] = calculate_ema(df['close'], 12)
            indicators['ema_26'] = calculate_ema(df['close'], 26)
            indicators['atr'] = calculate_atr(df)
            indicators['volatility'] = calculate_volatility(df)
            
            print(f"  📈 Indicators: RSI={indicators['rsi']:.2f}, EMA12={indicators['ema_12']:.2f}, EMA26={indicators['ema_26']:.2f}")
            
            # Generate signal
            signal_data = generate_signal(df, indicators)
            
            if signal_data['signal'] != 'HOLD':
                alerts.append({
                    'symbol': symbol,
                    'signal': signal_data['signal'],
                    'confidence': signal_data['confidence'],
                    'price': df['close'].iloc[-1],
                    'indicators': indicators
                })
                print(f"  🚨 SIGNAL: {signal_data['signal']} with {signal_data['confidence']:.1f}% confidence")
            else:
                print(f"  📊 No signal: HOLD")
        
        conn.close()
        return alerts
        
    except Exception as e:
        print(f"❌ Error generating alerts: {e}")
        return []

# Telegram notification function
def send_telegram_alert(alert):
    """Send alert to Telegram"""
    try:
        import requests
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        if not token or not chat_id:
            print("❌ Telegram credentials not set")
            return False
        
        symbol = alert['symbol']
        signal = alert['signal']
        confidence = alert['confidence']
        price = alert['price']
        indicators = alert['indicators']
        
        message = f"""
🚀 *Trading Signal Alert*

📊 *{symbol}*: **{signal}**
🎯 Confidence: {confidence:.1f}%
💰 Price: {price:.5f}

📈 *Technical Indicators:*
• RSI: {indicators.get('rsi', 0):.1f}
• EMA12/26: {indicators.get('ema_12', 0):.3f}/{indicators.get('ema_26', 0):.3f}
• ATR: {indicators.get('atr', 0):.4f}
• Volatility: {indicators.get('volatility', 0):.2f}%

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message.strip(),
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            print(f"  ✅ Telegram alert sent for {symbol}")
            return True
        else:
            print(f"  ❌ Telegram API error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Telegram error: {e}")
        return False

# Main execution
if __name__ == "__main__":
    print("Generating trading alerts...")
    alerts = generate_alerts()
    
    if alerts:
        print(f"\n🎯 Found {len(alerts)} trading signals:")
        for alert in alerts:
            print(f"  {alert['symbol']}: {alert['signal']} ({alert['confidence']:.1f}%)")
            
            # Send Telegram alert
            send_telegram_alert(alert)
    else:
        print("\n📊 No trading signals found at this time.")