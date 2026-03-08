"""Enable Tiingo pipeline by replacing flag in core/config.py"""
import io
from pathlib import Path

root = Path(__file__).parent.parent
config_path = root / 'core' / 'config.py'

text = config_path.read_text(encoding='utf-8')
old = "USE_TIINGO_PIPELINE = False"
new = "USE_TIINGO_PIPELINE = True"
if old in text:
    text = text.replace(old, new)
    config_path.write_text(text, encoding='utf-8')
    print(f"Patched {config_path}")
else:
    print("No change needed; flag not found or already True")
