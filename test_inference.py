from signals.xgb_signal_engine_ec2 import XGBSignalEngine

engine = XGBSignalEngine()
engine.load_model()

result = engine.generate_signal("EURUSD", "1h")

print("\n=== MANUAL INFERENCE RESULT ===")
print("Result:", result)
print("===========================\n")
