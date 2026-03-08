from signals.xgb_signal_engine_ec2 import XGBSignalEngine

e = XGBSignalEngine()
print("=" * 80)
print("PRODUCTION MODEL CLASSES")
print("=" * 80)
print(f"Model classes: {e.model.classes_}")
print(f"Number of classes: {len(e.model.classes_)}")
print("=" * 80)
