"""
Backtest Engine
Simulate OptiCore strategy on historical data to validate performance.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
from core.config import Config
from core.database import DatabaseManager
from data.fetcher import DataFetcher
from strategies.opticore_strategy import OptiCoreStrategy
from utils.logger import setup_logger


class BacktestEngine:
    """
    Backtest the OptiCore strategy on historical data.
    
    Simulates:
    - Entry signals (LONG/SHORT)
    - Exit conditions
    - Win/loss tracking
    - Performance metrics
    """
    
    def __init__(self, lookback_days: int = None):
        """
        Initialize backtest engine
        
        Args:
            lookback_days: Number of days of historical data to test (default: from config)
        """
        self.logger = setup_logger('BacktestEngine')
        self.lookback_days = lookback_days or Config.BACKTEST_DAYS
        self.fetcher = DataFetcher()
        self.strategy = OptiCoreStrategy()
        self.db = DatabaseManager()
        
        self.trades = []  # List of all trades
        self.equity_curve = []  # Equity over time
        
        self.logger.info(f"Backtest engine initialized | lookback={self.lookback_days} days")
    
    def run_backtest(self, symbols: Optional[List[str]] = None, 
                     timeframes: Optional[List[str]] = None) -> Dict:
        """
        Run backtest on specified symbols and timeframes
        
        Args:
            symbols: List of symbols to test (default: watchlist)
            timeframes: List of timeframes to test (default: entry timeframes)
        
        Returns:
            Backtest results dictionary
        """
        symbols = symbols or Config.get_symbol_list()
        timeframes = timeframes or Config.ENTRY_TIMEFRAMES
        
        self.logger.info(f"Starting backtest | symbols={len(symbols)} timeframes={timeframes}")
        
        results = {
            'start_time': datetime.now(),
            'symbols': symbols,
            'timeframes': timeframes,
            'lookback_days': self.lookback_days,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'breakeven_trades': 0,
            'total_profit': 0.0,
            'total_loss': 0.0,
            'by_symbol': {},
            'by_timeframe': {},
            'trades': []
        }
        
        for symbol in symbols:
            self.logger.info(f"Backtesting {symbol}...")
            
            # Fetch all cascade timeframes
            timeframe_data = self.fetcher.fetch_all_timeframes(
                symbol, 
                Config.CASCADE_TIMEFRAMES,
                force_refresh=False
            )
            
            if not timeframe_data:
                self.logger.warning(f"No data for {symbol}, skipping")
                continue
            
            # Test each entry timeframe
            for timeframe in timeframes:
                if timeframe not in timeframe_data or timeframe_data[timeframe] is None:
                    continue
                
                symbol_tf_trades = self._backtest_symbol_timeframe(
                    symbol, 
                    timeframe, 
                    timeframe_data
                )
                
                # Aggregate results
                results['trades'].extend(symbol_tf_trades)
                results['total_trades'] += len(symbol_tf_trades)
                
                # Count wins/losses
                for trade in symbol_tf_trades:
                    if trade['profit'] > 0:
                        results['winning_trades'] += 1
                        results['total_profit'] += trade['profit']
                    elif trade['profit'] < 0:
                        results['losing_trades'] += 1
                        results['total_loss'] += abs(trade['profit'])
                    else:
                        results['breakeven_trades'] += 1
                
                # By symbol stats
                if symbol not in results['by_symbol']:
                    results['by_symbol'][symbol] = {'trades': 0, 'wins': 0, 'profit': 0.0}
                results['by_symbol'][symbol]['trades'] += len(symbol_tf_trades)
                results['by_symbol'][symbol]['wins'] += sum(1 for t in symbol_tf_trades if t['profit'] > 0)
                results['by_symbol'][symbol]['profit'] += sum(t['profit'] for t in symbol_tf_trades)
                
                # By timeframe stats
                if timeframe not in results['by_timeframe']:
                    results['by_timeframe'][timeframe] = {'trades': 0, 'wins': 0, 'profit': 0.0}
                results['by_timeframe'][timeframe]['trades'] += len(symbol_tf_trades)
                results['by_timeframe'][timeframe]['wins'] += sum(1 for t in symbol_tf_trades if t['profit'] > 0)
                results['by_timeframe'][timeframe]['profit'] += sum(t['profit'] for t in symbol_tf_trades)
        
        results['end_time'] = datetime.now()
        results['duration'] = (results['end_time'] - results['start_time']).total_seconds()
        
        self.logger.info(f"Backtest complete | total_trades={results['total_trades']} wins={results['winning_trades']}")
        
        return results
    
    def _backtest_symbol_timeframe(self, symbol: str, timeframe: str, 
                                   timeframe_data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """
        Backtest a single symbol/timeframe combination
        
        Args:
            symbol: Trading symbol
            timeframe: Entry timeframe
            timeframe_data: Dict of all timeframe DataFrames
        
        Returns:
            List of trade dictionaries
        """
        trades = []
        current_df = timeframe_data[timeframe]
        
        if current_df is None or current_df.empty or len(current_df) < 100:
            return trades
        
        # Iterate through historical candles (skip first 100 for indicators)
        for i in range(100, len(current_df)):
            # Get data up to current candle
            historical_data = {}
            for tf, df in timeframe_data.items():
                if df is not None and not df.empty:
                    # Slice data up to equivalent timestamp
                    current_timestamp = current_df.index[i]
                    # Ensure timezone compatibility
                    if hasattr(current_timestamp, 'tz'):
                        if current_timestamp.tz is None:
                            current_timestamp = current_timestamp.tz_localize('UTC')
                        else:
                            current_timestamp = current_timestamp.tz_convert('UTC')
                    # Convert df index to UTC if needed
                    df_index = df.index
                    if hasattr(df_index, 'tz'):
                        if df_index.tz is None:
                            df_index = df_index.tz_localize('UTC')
                        else:
                            df_index = df_index.tz_convert('UTC')
                    historical_data[tf] = df[df_index <= current_timestamp]
            
            # Run strategy on historical data
            try:
                result = self.strategy.analyze_symbol(symbol, timeframe, historical_data)
                
                if result['signal'] in ['LONG', 'SHORT'] and result.get('entry_valid'):
                    # Simulate trade
                    trade = self._simulate_trade(
                        symbol,
                        timeframe,
                        result,
                        current_df,
                        i
                    )
                    
                    if trade:
                        trades.append(trade)
            
            except Exception as e:
                self.logger.debug(f"Strategy error at {symbol} {timeframe} index {i}: {e}")
                continue
        
        return trades
    
    def _simulate_trade(self, symbol: str, timeframe: str, signal_result: Dict, 
                       df: pd.DataFrame, entry_index: int) -> Optional[Dict]:
        """
        Simulate a single trade from entry to exit
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            signal_result: Strategy result with entry signal
            df: Price DataFrame
            entry_index: Index where entry occurred
        
        Returns:
            Trade dictionary or None
        """
        signal = signal_result['signal']
        entry_price = signal_result.get('price', float(df['close'].iloc[entry_index]))
        entry_time = df.index[entry_index]
        
        # Simple exit strategy: Hold for N candles or until opposite signal
        hold_periods = 10  # Hold for 10 candles (e.g., 5 hours for 30m, 10 hours for 1h)
        stop_loss_pct = 0.02  # 2% stop loss
        take_profit_pct = 0.03  # 3% take profit
        
        exit_price = None
        exit_time = None
        exit_reason = None
        
        # Look ahead for exit
        for j in range(entry_index + 1, min(entry_index + hold_periods + 1, len(df))):
            current_high = float(df['high'].iloc[j])
            current_low = float(df['low'].iloc[j])
            current_close = float(df['close'].iloc[j])
            
            if signal == 'LONG':
                # Check stop loss
                if current_low <= entry_price * (1 - stop_loss_pct):
                    exit_price = entry_price * (1 - stop_loss_pct)
                    exit_time = df.index[j]
                    exit_reason = 'stop_loss'
                    break
                
                # Check take profit
                if current_high >= entry_price * (1 + take_profit_pct):
                    exit_price = entry_price * (1 + take_profit_pct)
                    exit_time = df.index[j]
                    exit_reason = 'take_profit'
                    break
                
                # Exit at hold period
                if j == entry_index + hold_periods or j == len(df) - 1:
                    exit_price = current_close
                    exit_time = df.index[j]
                    exit_reason = 'time_exit'
                    break
            
            elif signal == 'SHORT':
                # Check stop loss
                if current_high >= entry_price * (1 + stop_loss_pct):
                    exit_price = entry_price * (1 + stop_loss_pct)
                    exit_time = df.index[j]
                    exit_reason = 'stop_loss'
                    break
                
                # Check take profit
                if current_low <= entry_price * (1 - take_profit_pct):
                    exit_price = entry_price * (1 - take_profit_pct)
                    exit_time = df.index[j]
                    exit_reason = 'take_profit'
                    break
                
                # Exit at hold period
                if j == entry_index + hold_periods or j == len(df) - 1:
                    exit_price = current_close
                    exit_time = df.index[j]
                    exit_reason = 'time_exit'
                    break
        
        if exit_price is None:
            # No exit found (end of data)
            exit_price = float(df['close'].iloc[-1])
            exit_time = df.index[-1]
            exit_reason = 'end_of_data'
        
        # Calculate profit
        if signal == 'LONG':
            profit_pct = ((exit_price - entry_price) / entry_price) * 100
        else:  # SHORT
            profit_pct = ((entry_price - exit_price) / entry_price) * 100
        
        trade = {
            'symbol': symbol,
            'timeframe': timeframe,
            'signal': signal,
            'entry_time': entry_time,
            'entry_price': entry_price,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'profit': profit_pct,
            'confidence': signal_result.get('confidence', 0),
            'cascade_aligned': signal_result.get('cascade_aligned', False)
        }
        
        return trade
    
    def get_trade_summary(self) -> str:
        """
        Get summary of all trades
        
        Returns:
            Formatted summary string
        """
        if not self.trades:
            return "No trades executed"
        
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t['profit'] > 0)
        losing_trades = sum(1 for t in self.trades if t['profit'] < 0)
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        total_profit = sum(t['profit'] for t in self.trades if t['profit'] > 0)
        total_loss = abs(sum(t['profit'] for t in self.trades if t['profit'] < 0))
        
        profit_factor = (total_profit / total_loss) if total_loss > 0 else 0
        
        lines = []
        lines.append("=" * 60)
        lines.append("BACKTEST SUMMARY")
        lines.append("=" * 60)
        lines.append(f"Total Trades: {total_trades}")
        lines.append(f"Winning Trades: {winning_trades} ({win_rate:.1f}%)")
        lines.append(f"Losing Trades: {losing_trades}")
        lines.append(f"Total Profit: {total_profit:.2f}%")
        lines.append(f"Total Loss: {total_loss:.2f}%")
        lines.append(f"Net Profit: {total_profit - total_loss:.2f}%")
        lines.append(f"Profit Factor: {profit_factor:.2f}")
        lines.append("=" * 60)
        
        return "\n".join(lines)


if __name__ == '__main__':
    # Run backtest
    engine = BacktestEngine(lookback_days=90)
    results = engine.run_backtest()
    
    # Print summary
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Total Trades: {results['total_trades']}")
    print(f"Winning Trades: {results['winning_trades']}")
    print(f"Losing Trades: {results['losing_trades']}")
    
    if results['total_trades'] > 0:
        win_rate = (results['winning_trades'] / results['total_trades']) * 100
        print(f"Win Rate: {win_rate:.1f}%")
        
        net_profit = results['total_profit'] - results['total_loss']
        print(f"Net Profit: {net_profit:.2f}%")
        
        if results['total_loss'] > 0:
            profit_factor = results['total_profit'] / results['total_loss']
            print(f"Profit Factor: {profit_factor:.2f}")
    
    print(f"\nDuration: {results['duration']:.1f} seconds")
    print("=" * 60)
