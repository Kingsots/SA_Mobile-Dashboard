"""
Migration 006: Add strategy_version column to ml_signals
Allows tracking whether signals come from V1 or V2 engine
"""

import sqlite3
from pathlib import Path

def execute_migration():
    """Add strategy_version column to track signal source (V1 vs V2)"""
    
    db_path = Path(__file__).parent.parent / 'trading_bot.db'
    
    print("Migration 006: Adding strategy_version column to ml_signals")
    print(f"Database: {db_path}")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(ml_signals)")
        columns = {row[1] for row in cursor.fetchall()}
        
        if 'strategy_version' in columns:
            print("✅ Column 'strategy_version' already exists")
            conn.close()
            return True
        
        # Add the column
        print("Adding strategy_version column...")
        cursor.execute("""
            ALTER TABLE ml_signals 
            ADD COLUMN strategy_version TEXT DEFAULT 'v1'
        """)
        
        # Create index for faster querying
        print("Creating index on strategy_version...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ml_signals_strategy_version
            ON ml_signals(strategy_version)
        """)
        
        conn.commit()
        print("✅ Migration 006 completed successfully")
        print("   - Added strategy_version column (default: 'v1')")
        print("   - Created index for strategy_version")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration 006 failed: {e}")
        return False

if __name__ == '__main__':
    success = execute_migration()
    exit(0 if success else 1)
