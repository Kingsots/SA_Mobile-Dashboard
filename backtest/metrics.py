"""
Performance Metrics Calculator
Calculate trading performance metrics from backtest results.
"""

import numpy as np
from typing import Dict, List
from datetime import datetime
from core.config import Config
from utils.logger import setup_logger


class PerformanceMetrics:
    """
    Calculate comprehensive performance metrics for backtest results.
    
    Metrics:
    - Win rate (efficiency)
    - Profit factor
    - Average trade
    - Max drawdown
    - Sharpe ratio
    - Risk/reward ratio
    """
    
    def __init__(self):
        self.logger = setup_logger('PerformanceMetrics')
    
    def calculate_all_metrics(self, backtest_results: Dict) -> Dict:
        """
        Calculate all performance metrics from backtest results
        
        Args:
            backtest_results: Results dictionary from BacktestEngine
        
        Returns:
            Dictionary with all metrics
        """
        trades = backtest_results.get('trades', [])
        
        if not trades:
            self.logger.warning("No trades to analyze")
            return {
                'error': 'No trades found',
                'metrics': {}
            }
        
        metrics = {}
        
        # Basic counts
        metrics['total_trades'] = len(trades)
        metrics['winning_trades'] = sum(1 for t in trades if t['profit'] > 0)
        metrics['losing_trades'] = sum(1 for t in trades if t['profit'] < 0)
        metrics['breakeven_trades'] = sum(1 for t in trades if t['profit'] == 0)
        
        # Win rate (efficiency)
        metrics['win_rate'] = self._calculate_win_rate(trades)
        metrics['efficiency'] = metrics['win_rate']  # Alias
        
        # Profit metrics
        metrics['total_profit'] = sum(t['profit'] for t in trades if t['profit'] > 0)
        metrics['total_loss'] = abs(sum(t['profit'] for t in trades if t['profit'] < 0))
        metrics['net_profit'] = metrics['total_profit'] - metrics['total_loss']
        
        # Average trades
        metrics['avg_win'] = self._calculate_avg_win(trades)
        metrics['avg_loss'] = self._calculate_avg_loss(trades)
        metrics['avg_trade'] = self._calculate_avg_trade(trades)
        
        # Profit factor
        metrics['profit_factor'] = self._calculate_profit_factor(trades)
        
        # Risk/reward ratio
        metrics['risk_reward_ratio'] = self._calculate_risk_reward(trades)
        
        # Drawdown
        metrics['max_drawdown'] = self._calculate_max_drawdown(trades)
        metrics['max_drawdown_pct'] = metrics['max_drawdown']
        
        # Sharpe ratio (annualized)
        metrics['sharpe_ratio'] = self._calculate_sharpe_ratio(trades)
        
        # Consecutive wins/losses
        metrics['max_consecutive_wins'] = self._calculate_max_consecutive_wins(trades)
        metrics['max_consecutive_losses'] = self._calculate_max_consecutive_losses(trades)
        
        # Best/worst trade
        metrics['best_trade'] = max((t['profit'] for t in trades), default=0)
        metrics['worst_trade'] = min((t['profit'] for t in trades), default=0)
        
        # Exit reasons breakdown
        metrics['exit_reasons'] = self._analyze_exit_reasons(trades)
        
        # Target validation
        metrics['meets_target_efficiency'] = metrics['efficiency'] >= (Config.TARGET_EFFICIENCY * 100)
        metrics['target_efficiency'] = Config.TARGET_EFFICIENCY * 100
        
        self.logger.info(f"Metrics calculated | win_rate={metrics['win_rate']:.1f}% profit_factor={metrics['profit_factor']:.2f}")
        
        return metrics
    
    def _calculate_win_rate(self, trades: List[Dict]) -> float:
        """Calculate win rate (percentage of winning trades)"""
        if not trades:
            return 0.0
        
        winning_trades = sum(1 for t in trades if t['profit'] > 0)
        return (winning_trades / len(trades)) * 100
    
    def _calculate_avg_win(self, trades: List[Dict]) -> float:
        """Calculate average winning trade profit"""
        winning_trades = [t['profit'] for t in trades if t['profit'] > 0]
        if not winning_trades:
            return 0.0
        return sum(winning_trades) / len(winning_trades)
    
    def _calculate_avg_loss(self, trades: List[Dict]) -> float:
        """Calculate average losing trade loss"""
        losing_trades = [abs(t['profit']) for t in trades if t['profit'] < 0]
        if not losing_trades:
            return 0.0
        return sum(losing_trades) / len(losing_trades)
    
    def _calculate_avg_trade(self, trades: List[Dict]) -> float:
        """Calculate average trade profit/loss"""
        if not trades:
            return 0.0
        return sum(t['profit'] for t in trades) / len(trades)
    
    def _calculate_profit_factor(self, trades: List[Dict]) -> float:
        """Calculate profit factor (total profit / total loss)"""
        total_profit = sum(t['profit'] for t in trades if t['profit'] > 0)
        total_loss = abs(sum(t['profit'] for t in trades if t['profit'] < 0))
        
        if total_loss == 0:
            return float('inf') if total_profit > 0 else 0.0
        
        return total_profit / total_loss
    
    def _calculate_risk_reward(self, trades: List[Dict]) -> float:
        """Calculate risk/reward ratio (avg win / avg loss)"""
        avg_win = self._calculate_avg_win(trades)
        avg_loss = self._calculate_avg_loss(trades)
        
        if avg_loss == 0:
            return float('inf') if avg_win > 0 else 0.0
        
        return avg_win / avg_loss
    
    def _calculate_max_drawdown(self, trades: List[Dict]) -> float:
        """Calculate maximum drawdown percentage"""
        if not trades:
            return 0.0
        
        # Build equity curve
        equity = 100.0  # Start with 100%
        equity_curve = [equity]
        
        for trade in trades:
            equity += trade['profit']
            equity_curve.append(equity)
        
        # Calculate drawdowns
        max_equity = equity_curve[0]
        max_drawdown = 0.0
        
        for equity_value in equity_curve:
            if equity_value > max_equity:
                max_equity = equity_value
            
            drawdown = ((max_equity - equity_value) / max_equity) * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def _calculate_sharpe_ratio(self, trades: List[Dict]) -> float:
        """Calculate Sharpe ratio (annualized)"""
        if not trades or len(trades) < 2:
            return 0.0
        
        returns = [t['profit'] for t in trades]
        
        # Calculate mean and std of returns
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming 252 trading days)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        
        return sharpe
    
    def _calculate_max_consecutive_wins(self, trades: List[Dict]) -> int:
        """Calculate maximum consecutive winning trades"""
        if not trades:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade['profit'] > 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _calculate_max_consecutive_losses(self, trades: List[Dict]) -> int:
        """Calculate maximum consecutive losing trades"""
        if not trades:
            return 0
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in trades:
            if trade['profit'] < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _analyze_exit_reasons(self, trades: List[Dict]) -> Dict:
        """Analyze breakdown of exit reasons"""
        exit_reasons = {}
        
        for trade in trades:
            reason = trade.get('exit_reason', 'unknown')
            if reason not in exit_reasons:
                exit_reasons[reason] = {'count': 0, 'wins': 0, 'profit': 0.0}
            
            exit_reasons[reason]['count'] += 1
            if trade['profit'] > 0:
                exit_reasons[reason]['wins'] += 1
            exit_reasons[reason]['profit'] += trade['profit']
        
        return exit_reasons
    
    def format_metrics_report(self, metrics: Dict) -> str:
        """
        Format metrics as readable report
        
        Args:
            metrics: Metrics dictionary
        
        Returns:
            Formatted report string
        """
        if 'error' in metrics:
            return f"❌ Error: {metrics['error']}"
        
        lines = []
        lines.append("")
        lines.append("=" * 70)
        lines.append("PERFORMANCE METRICS REPORT")
        lines.append("=" * 70)
        lines.append("")
        
        # Overview
        lines.append("📊 OVERVIEW")
        lines.append("-" * 70)
        lines.append(f"  Total Trades:        {metrics['total_trades']}")
        lines.append(f"  Winning Trades:      {metrics['winning_trades']} ({metrics['win_rate']:.1f}%)")
        lines.append(f"  Losing Trades:       {metrics['losing_trades']}")
        lines.append(f"  Breakeven Trades:    {metrics['breakeven_trades']}")
        lines.append("")
        
        # Efficiency
        target_met = "✅ TARGET MET" if metrics['meets_target_efficiency'] else "❌ BELOW TARGET"
        lines.append("⚡ EFFICIENCY")
        lines.append("-" * 70)
        lines.append(f"  Win Rate (Efficiency): {metrics['efficiency']:.1f}%")
        lines.append(f"  Target:                {metrics['target_efficiency']:.1f}%")
        lines.append(f"  Status:                {target_met}")
        lines.append("")
        
        # Profit metrics
        lines.append("💰 PROFIT METRICS")
        lines.append("-" * 70)
        lines.append(f"  Total Profit:        +{metrics['total_profit']:.2f}%")
        lines.append(f"  Total Loss:          -{metrics['total_loss']:.2f}%")
        lines.append(f"  Net Profit:          {metrics['net_profit']:+.2f}%")
        lines.append(f"  Average Trade:       {metrics['avg_trade']:+.2f}%")
        lines.append(f"  Average Win:         +{metrics['avg_win']:.2f}%")
        lines.append(f"  Average Loss:        -{metrics['avg_loss']:.2f}%")
        lines.append("")
        
        # Risk metrics
        lines.append("📉 RISK METRICS")
        lines.append("-" * 70)
        lines.append(f"  Profit Factor:       {metrics['profit_factor']:.2f}")
        lines.append(f"  Risk/Reward Ratio:   {metrics['risk_reward_ratio']:.2f}")
        lines.append(f"  Max Drawdown:        {metrics['max_drawdown']:.2f}%")
        lines.append(f"  Sharpe Ratio:        {metrics['sharpe_ratio']:.2f}")
        lines.append("")
        
        # Consecutive trades
        lines.append("🔄 STREAKS")
        lines.append("-" * 70)
        lines.append(f"  Max Consecutive Wins:   {metrics['max_consecutive_wins']}")
        lines.append(f"  Max Consecutive Losses: {metrics['max_consecutive_losses']}")
        lines.append(f"  Best Trade:             +{metrics['best_trade']:.2f}%")
        lines.append(f"  Worst Trade:            {metrics['worst_trade']:.2f}%")
        lines.append("")
        
        # Exit reasons
        if metrics.get('exit_reasons'):
            lines.append("🚪 EXIT REASONS")
            lines.append("-" * 70)
            for reason, data in metrics['exit_reasons'].items():
                win_rate = (data['wins'] / data['count'] * 100) if data['count'] > 0 else 0
                lines.append(f"  {reason.upper():20} | Count: {data['count']:3} | "
                           f"Win Rate: {win_rate:5.1f}% | Profit: {data['profit']:+7.2f}%")
            lines.append("")
        
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def save_metrics_to_db(self, metrics: Dict, backtest_id: str = None):
        """
        Save metrics to database
        
        Args:
            metrics: Metrics dictionary
            backtest_id: Optional backtest identifier
        """
        from core.database import DatabaseManager
        
        db = DatabaseManager()
        
        try:
            # Insert into performance_metrics table
            conn = db.db_path
            import sqlite3
            conn = sqlite3.connect(db.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
            INSERT INTO performance_metrics 
            (total_signals, win_signals, loss_signals, efficiency, 
             profit_factor, avg_trade, max_drawdown, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                metrics['total_trades'],
                metrics['winning_trades'],
                metrics['losing_trades'],
                metrics['efficiency'],
                metrics['profit_factor'],
                metrics['avg_trade'],
                metrics['max_drawdown'],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            conn.commit()
            conn.close()
            
            self.logger.info("Metrics saved to database")
            
        except Exception as e:
            self.logger.error(f"Error saving metrics to database: {e}")


if __name__ == '__main__':
    # Example usage
    from backtest.engine import BacktestEngine
    
    print("Running backtest...")
    engine = BacktestEngine(lookback_days=90)
    results = engine.run_backtest()
    
    print("\nCalculating metrics...")
    calc = PerformanceMetrics()
    metrics = calc.calculate_all_metrics(results)
    
    # Print report
    print(calc.format_metrics_report(metrics))
    
    # Save to database
    calc.save_metrics_to_db(metrics)
