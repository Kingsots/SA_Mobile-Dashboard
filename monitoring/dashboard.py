"""
Monitoring Dashboard
Real-time tracking of API usage, model performance, signal accuracy
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import json

from core.config import Config
from core.database import DatabaseManager


class MLPipelineDashboard:
    """
    Monitoring dashboard for ML pipeline
    
    Tracks:
    - API usage (hourly/daily limits)
    - Model performance (accuracy, deployment history)
    - Signal accuracy (BUY/SELL win rates)
    - System health (database size, data freshness)
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.conn = sqlite3.connect(Config.DB_PATH)
    
    def close(self):
        """Close database connection"""
        self.conn.close()
    
    # ==========================================
    # API USAGE MONITORING
    # ==========================================
    
    def get_api_usage_stats(self) -> Dict:
        """
        Get API usage statistics
        
        Returns:
            Dict with hourly/daily usage
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow()
        
        # Hourly usage
        hour_ago = now - timedelta(hours=1)
        cursor.execute("""
            SELECT COUNT(*) FROM api_usage 
            WHERE api_name = 'tiingo' 
            AND timestamp >= ? 
            AND success = 1
        """, (hour_ago.isoformat(),))
        hourly_used = cursor.fetchone()[0]
        
        # Daily usage
        day_ago = now - timedelta(days=1)
        cursor.execute("""
            SELECT COUNT(*) FROM api_usage 
            WHERE api_name = 'tiingo' 
            AND timestamp >= ? 
            AND success = 1
        """, (day_ago.isoformat(),))
        daily_used = cursor.fetchone()[0]
        
        # Failed requests
        cursor.execute("""
            SELECT COUNT(*) FROM api_usage 
            WHERE api_name = 'tiingo' 
            AND timestamp >= ? 
            AND success = 0
        """, (day_ago.isoformat(),))
        failed = cursor.fetchone()[0]
        
        # Success rate
        total = daily_used + failed
        success_rate = (daily_used / total * 100) if total > 0 else 0
        
        return {
            'hourly_used': hourly_used,
            'hourly_limit': Config.TIINGO_MAX_HOURLY_REQUESTS,
            'hourly_remaining': Config.TIINGO_MAX_HOURLY_REQUESTS - hourly_used,
            'hourly_pct': hourly_used / Config.TIINGO_MAX_HOURLY_REQUESTS * 100,
            'daily_used': daily_used,
            'daily_limit': Config.TIINGO_MAX_DAILY_REQUESTS,
            'daily_remaining': Config.TIINGO_MAX_DAILY_REQUESTS - daily_used,
            'daily_pct': daily_used / Config.TIINGO_MAX_DAILY_REQUESTS * 100,
            'failed_requests': failed,
            'success_rate': success_rate
        }
    
    def get_api_usage_timeline(self, hours: int = 24) -> pd.DataFrame:
        """
        Get API usage over time
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            DataFrame with hourly API usage
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        query = """
        SELECT 
            strftime('%Y-%m-%d %H:00', timestamp) as hour,
            COUNT(*) as requests,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
        FROM api_usage
        WHERE api_name = 'tiingo' AND timestamp >= ?
        GROUP BY hour
        ORDER BY hour
        """
        
        df = pd.read_sql_query(query, self.conn, params=(cutoff.isoformat(),))
        return df
    
    # ==========================================
    # MODEL PERFORMANCE MONITORING
    # ==========================================
    
    def get_model_performance(self) -> Dict:
        """
        Get current model performance metrics
        
        Returns:
            Dict with accuracy, precision, recall, F1
        """
        # Get latest deployed model
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM model_training_log 
            WHERE deployed = 1 
            ORDER BY timestamp DESC 
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        
        if row is None:
            return {
                'model_exists': False,
                'message': 'No deployed model found'
            }
        
        columns = [desc[0] for desc in cursor.description]
        model_data = dict(zip(columns, row))
        
        return {
            'model_exists': True,
            'version': model_data['model_version'],
            'timestamp': model_data['timestamp'],
            'accuracy': model_data['accuracy'],
            'precision': model_data['precision_score'],
            'recall': model_data['recall'],
            'f1_score': model_data['f1_score'],
            'train_samples': model_data['train_samples'],
            'test_samples': model_data['test_samples'],
            'training_time': model_data['training_time_seconds']
        }
    
    def get_model_training_history(self, limit: int = 10) -> pd.DataFrame:
        """
        Get model training history
        
        Args:
            limit: Number of training runs to return
            
        Returns:
            DataFrame with training history
        """
        query = """
        SELECT 
            timestamp,
            model_version,
            accuracy,
            precision_score,
            recall,
            f1_score,
            train_samples,
            test_samples,
            deployed
        FROM model_training_log
        ORDER BY timestamp DESC
        LIMIT ?
        """
        
        df = pd.read_sql_query(query, self.conn, params=(limit,))
        return df
    
    # ==========================================
    # SIGNAL ACCURACY MONITORING
    # ==========================================
    
    def get_signal_accuracy(self, days: int = 7) -> Dict:
        """
        Calculate signal accuracy over time period
        
        Note: This is a simplified version. Full accuracy tracking
        would require tracking actual price movements after signals.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dict with signal statistics
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        cursor = self.conn.cursor()
        
        # Total signals
        cursor.execute("""
            SELECT COUNT(*) FROM ml_signals 
            WHERE timestamp >= ?
        """, (cutoff.isoformat(),))
        total_signals = cursor.fetchone()[0]
        
        # Signals by type
        cursor.execute("""
            SELECT 
                signal,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM ml_signals
            WHERE timestamp >= ?
            GROUP BY signal
        """, (cutoff.isoformat(),))
        
        signal_breakdown = {}
        for row in cursor.fetchall():
            signal_type = Config.ML_SIGNAL_LABELS.get(row[0], 'UNKNOWN')
            signal_breakdown[signal_type] = {
                'count': row[1],
                'avg_confidence': row[2]
            }
        
        # Average confidence
        cursor.execute("""
            SELECT AVG(confidence) FROM ml_signals 
            WHERE timestamp >= ?
        """, (cutoff.isoformat(),))
        avg_confidence = cursor.fetchone()[0] or 0.0
        
        return {
            'period_days': days,
            'total_signals': total_signals,
            'signal_breakdown': signal_breakdown,
            'avg_confidence': avg_confidence
        }
    
    def get_signal_timeline(self, hours: int = 24) -> pd.DataFrame:
        """
        Get signals over time
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            DataFrame with signal timeline
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        query = """
        SELECT 
            timestamp,
            ticker,
            CASE signal 
                WHEN 1 THEN 'BUY'
                WHEN -1 THEN 'SELL'
                ELSE 'NEUTRAL'
            END as signal_type,
            confidence,
            interval
        FROM ml_signals
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
        """
        
        df = pd.read_sql_query(query, self.conn, params=(cutoff.isoformat(),))
        return df
    
    # ==========================================
    # DATA QUALITY MONITORING
    # ==========================================
    
    def get_data_freshness(self) -> Dict:
        """
        Check data freshness for all symbols
        
        Returns:
            Dict with freshness status per symbol
        """
        cursor = self.conn.cursor()
        now = datetime.utcnow()
        
        freshness = {}
        
        for symbol in Config.get_symbol_list():
            # Check raw OHLCV data
            cursor.execute("""
                SELECT MAX(timestamp) FROM ohlcv_data 
                WHERE symbol = ?
            """, (symbol,))
            
            last_raw = cursor.fetchone()[0]
            
            # Check features
            cursor.execute("""
                SELECT MAX(timestamp) FROM features 
                WHERE ticker = ?
            """, (symbol,))
            
            last_features = cursor.fetchone()[0]
            
            freshness[symbol] = {
                'last_raw_data': last_raw,
                'last_features': last_features,
                'raw_age_hours': None,
                'features_age_hours': None
            }
            
            if last_raw:
                age = now - datetime.fromisoformat(last_raw)
                freshness[symbol]['raw_age_hours'] = age.total_seconds() / 3600
            
            if last_features:
                age = now - datetime.fromisoformat(last_features)
                freshness[symbol]['features_age_hours'] = age.total_seconds() / 3600
        
        return freshness
    
    def get_database_health(self) -> Dict:
        """
        Get database health metrics
        
        Returns:
            Dict with database statistics
        """
        cursor = self.conn.cursor()
        
        # Table sizes
        tables = ['ohlcv_data', 'features', 'ml_signals', 'api_usage', 'model_training_log']
        table_sizes = {}
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            table_sizes[table] = cursor.fetchone()[0]
        
        # Database file size
        db_path = Path(Config.DB_PATH)
        db_size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0
        
        # Oldest data
        cursor.execute("SELECT MIN(timestamp) FROM ohlcv_data")
        oldest_data = cursor.fetchone()[0]
        
        return {
            'db_size_mb': db_size_mb,
            'table_sizes': table_sizes,
            'oldest_data': oldest_data,
            'total_records': sum(table_sizes.values())
        }
    
    # ==========================================
    # SYSTEM HEALTH CHECK
    # ==========================================
    
    def health_check(self) -> Dict:
        """
        Complete system health check
        
        Returns:
            Dict with all health metrics
        """
        health = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'healthy',
            'warnings': [],
            'errors': []
        }
        
        # Check API usage
        api_stats = self.get_api_usage_stats()
        health['api_usage'] = api_stats
        
        if api_stats['hourly_pct'] > 90:
            health['warnings'].append(f"Hourly API usage at {api_stats['hourly_pct']:.0f}%")
        
        if api_stats['daily_pct'] > 90:
            health['warnings'].append(f"Daily API usage at {api_stats['daily_pct']:.0f}%")
        
        # Check model
        model_perf = self.get_model_performance()
        health['model'] = model_perf
        
        if not model_perf['model_exists']:
            health['errors'].append("No deployed model found")
        elif model_perf['accuracy'] < Config.ML_TARGET_ACCURACY:
            health['warnings'].append(f"Model accuracy below target: {model_perf['accuracy']:.1%}")
        
        # Check data freshness
        freshness = self.get_data_freshness()
        stale_count = 0
        
        for symbol, data in freshness.items():
            if data['raw_age_hours'] and data['raw_age_hours'] > 2:
                stale_count += 1
        
        if stale_count > 0:
            health['warnings'].append(f"{stale_count} symbols have stale data (>2h old)")
        
        # Check database
        db_health = self.get_database_health()
        health['database'] = db_health
        
        if db_health['db_size_mb'] > 1000:  # 1 GB
            health['warnings'].append(f"Database large: {db_health['db_size_mb']:.0f} MB")
        
        # Set overall status
        if health['errors']:
            health['status'] = 'error'
        elif health['warnings']:
            health['status'] = 'warning'
        
        return health
    
    # ==========================================
    # DISPLAY METHODS
    # ==========================================
    
    def print_dashboard(self):
        """Print formatted dashboard to console"""
        print(f"\n{'='*70}")
        print(f"  📊 ML PIPELINE DASHBOARD")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        # API Usage
        print(f"🌐 API USAGE (Tiingo)")
        print(f"{'='*70}")
        api_stats = self.get_api_usage_stats()
        print(f"   Hourly:  {api_stats['hourly_used']:3}/{api_stats['hourly_limit']} "
              f"({api_stats['hourly_pct']:5.1f}%) [{api_stats['hourly_remaining']} remaining]")
        print(f"   Daily:   {api_stats['daily_used']:4}/{api_stats['daily_limit']} "
              f"({api_stats['daily_pct']:5.1f}%) [{api_stats['daily_remaining']} remaining]")
        print(f"   Success: {api_stats['success_rate']:.1f}% (Failed: {api_stats['failed_requests']})")
        
        # Model Performance
        print(f"\n🤖 MODEL PERFORMANCE")
        print(f"{'='*70}")
        model_perf = self.get_model_performance()
        
        if model_perf['model_exists']:
            print(f"   Version:   {model_perf['version']}")
            print(f"   Accuracy:  {model_perf['accuracy']:.2%}")
            print(f"   Precision: {model_perf['precision']:.2%}")
            print(f"   Recall:    {model_perf['recall']:.2%}")
            print(f"   F1 Score:  {model_perf['f1_score']:.2%}")
            print(f"   Samples:   {model_perf['train_samples']} train, {model_perf['test_samples']} test")
        else:
            print(f"   ⚠️  No deployed model found")
        
        # Signal Statistics
        print(f"\n🔮 SIGNAL STATISTICS (Last 7 days)")
        print(f"{'='*70}")
        signal_stats = self.get_signal_accuracy(days=7)
        print(f"   Total Signals:   {signal_stats['total_signals']}")
        print(f"   Avg Confidence:  {signal_stats['avg_confidence']:.1%}")
        
        for signal_type, data in signal_stats['signal_breakdown'].items():
            print(f"   {signal_type:8} {data['count']:4} signals (conf: {data['avg_confidence']:.1%})")
        
        # Database Health
        print(f"\n🗄️  DATABASE HEALTH")
        print(f"{'='*70}")
        db_health = self.get_database_health()
        print(f"   Size:          {db_health['db_size_mb']:.1f} MB")
        print(f"   Total Records: {db_health['total_records']:,}")
        print(f"   Oldest Data:   {db_health['oldest_data'] or 'N/A'}")
        
        print(f"\n   Table Sizes:")
        for table, count in db_health['table_sizes'].items():
            print(f"      {table:20} {count:8,} records")
        
        # System Health
        print(f"\n🏥 SYSTEM HEALTH")
        print(f"{'='*70}")
        health = self.health_check()
        
        status_emoji = {
            'healthy': '✅',
            'warning': '⚠️',
            'error': '❌'
        }
        
        print(f"   Status: {status_emoji[health['status']]} {health['status'].upper()}")
        
        if health['warnings']:
            print(f"\n   Warnings:")
            for warning in health['warnings']:
                print(f"      ⚠️  {warning}")
        
        if health['errors']:
            print(f"\n   Errors:")
            for error in health['errors']:
                print(f"      ❌ {error}")
        
        print(f"\n{'='*70}\n")


def main():
    """Display dashboard"""
    dashboard = MLPipelineDashboard()
    
    try:
        dashboard.print_dashboard()
    finally:
        dashboard.close()


if __name__ == '__main__':
    main()
