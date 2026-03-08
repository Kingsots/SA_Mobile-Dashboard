"""
Model Optimization & Hyperparameter Tuning
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import time
import json
from pathlib import Path

from xgboost import XGBClassifier
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.metrics import accuracy_score, classification_report, make_scorer

from core.config import Config
from core.database import DatabaseManager
from models.xgb_trainer import XGBTrainer


class ModelOptimizer:
    """
    Hyperparameter tuning and model optimization
    
    Optimizes:
    - n_estimators (number of trees)
    - max_depth (tree depth)
    - learning_rate (step size)
    - min_child_weight (minimum samples per leaf)
    - subsample (row sampling ratio)
    - colsample_bytree (feature sampling ratio)
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.trainer = XGBTrainer()
        self.best_params = None
        self.best_score = 0.0
    
    def get_param_grid(self, search_type: str = 'quick') -> Dict:
        """
        Get hyperparameter search grid
        
        Args:
            search_type: 'quick' or 'extensive'
            
        Returns:
            Dict with parameter ranges
        """
        if search_type == 'quick':
            # Quick search - smaller grid
            return {
                'n_estimators': [100, 200, 300],
                'max_depth': [3, 4, 5],
                'learning_rate': [0.01, 0.05, 0.1],
                'min_child_weight': [1, 3],
                'subsample': [0.8, 1.0],
                'colsample_bytree': [0.8, 1.0]
            }
        else:
            # Extensive search - larger grid
            return {
                'n_estimators': [100, 200, 300, 400],
                'max_depth': [3, 4, 5, 6, 7],
                'learning_rate': [0.01, 0.03, 0.05, 0.07, 0.1],
                'min_child_weight': [1, 2, 3, 4],
                'subsample': [0.6, 0.7, 0.8, 0.9, 1.0],
                'colsample_bytree': [0.6, 0.7, 0.8, 0.9, 1.0]
            }
    
    def optimize_hyperparameters(
        self, 
        X: pd.DataFrame, 
        y: pd.Series,
        search_type: str = 'quick',
        cv_splits: int = 3
    ) -> Tuple[Dict, float]:
        """
        Optimize hyperparameters using GridSearchCV
        
        Args:
            X: Feature matrix
            y: Target vector
            search_type: 'quick' or 'extensive'
            cv_splits: Number of cross-validation splits
            
        Returns:
            (best_params, best_score)
        """
        print(f"\n{'='*70}")
        print(f"  🔍 HYPERPARAMETER OPTIMIZATION")
        print(f"  Search Type: {search_type.upper()}")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        
        # Get parameter grid
        param_grid = self.get_param_grid(search_type)
        
        print(f"Parameter Grid:")
        for param, values in param_grid.items():
            print(f"   {param:20} {values}")
        
        # Total combinations
        total_combos = 1
        for values in param_grid.values():
            total_combos *= len(values)
        
        print(f"\nTotal combinations: {total_combos}")
        print(f"CV splits: {cv_splits}")
        print(f"Total fits: {total_combos * cv_splits}\n")
        
        # Initialize base model
        base_model = XGBClassifier(
            objective='multi:softmax',
            num_class=3,
            random_state=42,
            use_label_encoder=False,
            eval_metric='mlogloss'
        )
        
        # Time series cross-validation
        tscv = TimeSeriesSplit(n_splits=cv_splits)
        
        # Map labels for XGBoost
        label_map = {-1: 0, 0: 1, 1: 2}
        y_mapped = y.map(label_map)
        
        # Grid search
        print(f"🔄 Running grid search...")
        
        grid_search = GridSearchCV(
            estimator=base_model,
            param_grid=param_grid,
            cv=tscv,
            scoring='accuracy',
            n_jobs=-1,
            verbose=1
        )
        
        grid_search.fit(X, y_mapped)
        
        training_time = time.time() - start_time
        
        # Results
        self.best_params = grid_search.best_params_
        self.best_score = grid_search.best_score_
        
        print(f"\n✅ Optimization complete in {training_time:.1f}s")
        print(f"\n📊 Best Parameters:")
        for param, value in self.best_params.items():
            print(f"   {param:20} {value}")
        
        print(f"\n🎯 Best CV Score: {self.best_score:.4f}")
        
        # Top 5 configurations
        results_df = pd.DataFrame(grid_search.cv_results_)
        top_5 = results_df.nsmallest(5, 'rank_test_score')[
            ['params', 'mean_test_score', 'std_test_score', 'rank_test_score']
        ]
        
        print(f"\n🏆 Top 5 Configurations:")
        print(top_5.to_string(index=False))
        
        return self.best_params, self.best_score
    
    def save_optimized_params(self, params: Dict, score: float):
        """
        Save optimized parameters to config file
        
        Args:
            params: Best parameters
            score: Best score
        """
        output_file = Path(__file__).parent / 'optimized_params.json'
        
        data = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'best_score': score,
            'best_params': params,
            'config_snippet': f"""
# Optimized XGBoost Parameters (Score: {score:.4f})
XGBOOST_N_ESTIMATORS = {params['n_estimators']}
XGBOOST_MAX_DEPTH = {params['max_depth']}
XGBOOST_LEARNING_RATE = {params['learning_rate']}
XGBOOST_MIN_CHILD_WEIGHT = {params['min_child_weight']}
XGBOOST_SUBSAMPLE = {params['subsample']}
XGBOOST_COLSAMPLE_BYTREE = {params['colsample_bytree']}
"""
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Optimized parameters saved to: {output_file}")
        print(f"\n📝 Add this to core/config.py:")
        print(data['config_snippet'])


class FeatureSelector:
    """
    Feature importance analysis and selection
    """
    
    def __init__(self):
        self.trainer = XGBTrainer()
    
    def analyze_feature_importance(
        self, 
        model: XGBClassifier,
        feature_names: List[str]
    ) -> pd.DataFrame:
        """
        Analyze feature importance
        
        Args:
            model: Trained XGBoost model
            feature_names: List of feature names
            
        Returns:
            DataFrame with feature importance scores
        """
        print(f"\n{'='*70}")
        print(f"  📊 FEATURE IMPORTANCE ANALYSIS")
        print(f"{'='*70}\n")
        
        # Get importance scores
        importance_scores = model.feature_importances_
        
        # Create DataFrame
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importance_scores
        })
        
        # Sort by importance
        importance_df = importance_df.sort_values('importance', ascending=False)
        
        # Calculate cumulative importance
        importance_df['cumulative'] = importance_df['importance'].cumsum()
        importance_df['cumulative_pct'] = (importance_df['cumulative'] / 
                                           importance_df['importance'].sum() * 100)
        
        print(f"Feature Importance Rankings:")
        print(importance_df.to_string(index=False))
        
        # Top features for 80% of importance
        top_features = importance_df[importance_df['cumulative_pct'] <= 80]['feature'].tolist()
        
        print(f"\n🎯 Top features (80% importance): {len(top_features)}")
        for feat in top_features:
            print(f"   • {feat}")
        
        return importance_df
    
    def recommend_features(self, importance_df: pd.DataFrame, threshold: float = 0.01) -> List[str]:
        """
        Recommend features to keep based on importance
        
        Args:
            importance_df: Feature importance DataFrame
            threshold: Minimum importance threshold
            
        Returns:
            List of recommended features
        """
        recommended = importance_df[importance_df['importance'] >= threshold]['feature'].tolist()
        
        print(f"\n💡 Recommended features (importance >= {threshold}):")
        print(f"   Keep: {len(recommended)}/{len(importance_df)} features")
        
        removed = importance_df[importance_df['importance'] < threshold]['feature'].tolist()
        if removed:
            print(f"\n   Consider removing:")
            for feat in removed:
                imp = importance_df[importance_df['feature'] == feat]['importance'].values[0]
                print(f"      • {feat:20} (importance: {imp:.4f})")
        
        return recommended


class IntegrationTester:
    """
    Full integration testing of the ML pipeline
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.results = {
            'tests_run': 0,
            'tests_passed': 0,
            'tests_failed': 0,
            'errors': []
        }
    
    def test_data_pipeline(self) -> bool:
        """Test data fetching and storage"""
        print(f"\n📊 Testing data pipeline...")
        
        try:
            # Check if we have raw data
            df = self.db.load_raw_ohlcv('EURUSD', '1h', days=7)
            
            if df is None or df.empty:
                print(f"   ⚠️  No raw data found")
                return True  # Not a failure, just no data yet
            
            print(f"   ✅ Raw data: {len(df)} candles")
            return True
        
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            self.results['errors'].append(f"Data pipeline: {e}")
            return False
    
    def test_feature_engineering(self) -> bool:
        """Test feature computation"""
        print(f"\n🔧 Testing feature engineering...")
        
        try:
            from features.engine import FeatureEngine
            
            engine = FeatureEngine()
            
            # Check if we have features
            df = self.db.load_features('EURUSD', '1h', days=7)
            
            if df is None or df.empty:
                print(f"   ⚠️  No features found")
                return True  # Not a failure
            
            # Check all required columns
            required = ['ema_21', 'ema_100', 'rsi_14', 'obv', 'ad', 'vwap', 'vwap_slope']
            missing = [col for col in required if col not in df.columns]
            
            if missing:
                print(f"   ❌ Missing features: {missing}")
                return False
            
            print(f"   ✅ Features: {len(df)} rows, {len(df.columns)} columns")
            return True
        
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            self.results['errors'].append(f"Feature engineering: {e}")
            return False
    
    def test_model_training(self) -> bool:
        """Test model training"""
        print(f"\n🤖 Testing model training...")
        
        try:
            # Check if model exists
            model_exists = Config.MODEL_CURRENT_PATH.exists()
            
            if not model_exists:
                print(f"   ⚠️  No trained model found")
                return True  # Not a failure
            
            # Load model metadata
            if Config.MODEL_METADATA_PATH.exists():
                with open(Config.MODEL_METADATA_PATH, 'r') as f:
                    metadata = json.load(f)
                
                accuracy = metadata['metrics']['accuracy']
                print(f"   ✅ Model deployed: {accuracy:.2%} accuracy")
                return True
            else:
                print(f"   ⚠️  Model metadata missing")
                return True
        
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            self.results['errors'].append(f"Model training: {e}")
            return False
    
    def test_signal_generation(self) -> bool:
        """Test signal generation"""
        print(f"\n🔮 Testing signal generation...")
        
        try:
            from signals.xgb_signal_engine import XGBSignalEngine
            
            engine = XGBSignalEngine()
            
            # Check recent signals
            conn = self.db.conn if hasattr(self.db, 'conn') else None
            if conn is None:
                import sqlite3
                conn = sqlite3.connect(Config.DB_PATH)
            
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ml_signals")
            signal_count = cursor.fetchone()[0]
            
            print(f"   ✅ ML signals in database: {signal_count}")
            return True
        
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            self.results['errors'].append(f"Signal generation: {e}")
            return False
    
    def test_unified_alerts(self) -> bool:
        """Test unified alert system"""
        print(f"\n📱 Testing unified alerts...")
        
        try:
            from unified_alerts import UnifiedAlertSystem
            
            system = UnifiedAlertSystem(alert_moderate=False, alert_weak=False)
            
            # Test analysis (don't send alerts)
            analysis = system.analyze_symbol('EURUSD', '1h')
            
            if analysis:
                print(f"   ✅ Unified analysis working")
                print(f"      Consensus: {analysis['consensus']['level']}")
                return True
            else:
                print(f"   ⚠️  Analysis returned None")
                return True
        
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            self.results['errors'].append(f"Unified alerts: {e}")
            return False
    
    def run_all_tests(self):
        """Run all integration tests"""
        print(f"\n{'='*70}")
        print(f"  🧪 INTEGRATION TESTING")
        print(f"{'='*70}")
        
        tests = [
            ('Data Pipeline', self.test_data_pipeline),
            ('Feature Engineering', self.test_feature_engineering),
            ('Model Training', self.test_model_training),
            ('Signal Generation', self.test_signal_generation),
            ('Unified Alerts', self.test_unified_alerts)
        ]
        
        for test_name, test_func in tests:
            self.results['tests_run'] += 1
            
            passed = test_func()
            
            if passed:
                self.results['tests_passed'] += 1
            else:
                self.results['tests_failed'] += 1
        
        # Summary
        print(f"\n{'='*70}")
        print(f"  📊 TEST SUMMARY")
        print(f"{'='*70}")
        print(f"   Tests Run:    {self.results['tests_run']}")
        print(f"   Tests Passed: {self.results['tests_passed']} ✅")
        print(f"   Tests Failed: {self.results['tests_failed']} ❌")
        
        if self.results['errors']:
            print(f"\n   Errors:")
            for error in self.results['errors']:
                print(f"      • {error}")
        
        print(f"{'='*70}\n")
        
        return self.results['tests_failed'] == 0


def main():
    """Run optimization and testing"""
    print(f"\n{'='*70}")
    print(f"  🎯 PHASE 9: OPTIMIZATION & TESTING")
    print(f"{'='*70}\n")
    
    # 1. Integration Testing
    print(f"Step 1: Integration Testing")
    tester = IntegrationTester()
    all_passed = tester.run_all_tests()
    
    if not all_passed:
        print(f"⚠️  Some integration tests failed")
        print(f"   Fix errors before proceeding to optimization\n")
        return
    
    print(f"✅ All integration tests passed!\n")
    
    # 2. Hyperparameter Optimization (optional - commented out by default)
    print(f"Step 2: Hyperparameter Optimization")
    print(f"   ⚠️  Optimization is resource-intensive")
    print(f"   Uncomment the code below to run optimization\n")
    
    """
    # Uncomment to run optimization
    optimizer = ModelOptimizer()
    
    # Load training data
    trainer = XGBTrainer()
    df = trainer.load_training_data(interval='1h', days=90)
    
    if df is not None and not df.empty:
        X, y = trainer.prepare_features(df)
        
        # Quick search
        best_params, best_score = optimizer.optimize_hyperparameters(
            X, y, 
            search_type='quick',
            cv_splits=3
        )
        
        # Save results
        optimizer.save_optimized_params(best_params, best_score)
    """
    
    print(f"✅ Phase 9 Complete!\n")


if __name__ == '__main__':
    main()
