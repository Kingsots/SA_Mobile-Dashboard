"""
Verify Updated Watchlist
"""
from core.config import Config

symbols = Config.get_symbol_list()

print("\n" + "=" * 60)
print("  ✅ UPDATED WATCHLIST")
print("=" * 60)
print(f"\nTotal Symbols: {len(symbols)}")
print()

# Group by type
indices = []
commodities = []
forex = []

for sym in symbols:
    sym_type = Config.WATCHLIST[sym]["type"]
    if sym_type == "index":
        indices.append(sym)
    elif sym_type == "commodity":
        commodities.append(sym)
    else:
        forex.append(sym)

print("📊 INDICES:")
for sym in indices:
    print(f"  ✅ {sym:10} - {Config.WATCHLIST[sym]['name']}")

print("\n💰 COMMODITIES:")
for sym in commodities:
    print(f"  ✅ {sym:10} - {Config.WATCHLIST[sym]['name']}")

print("\n💱 FOREX:")
for sym in forex:
    print(f"  ✅ {sym:10} - {Config.WATCHLIST[sym]['name']}")

print("\n" + "=" * 60)
print(f"  Total: {len(symbols)} symbols")
print("  - Indices: 3")
print("  - Commodities: 1")
print("  - Forex: 11")
print("=" * 60 + "\n")

# Verify against your list
your_list = [
    "USDJPY", "GBPUSD", "EURUSD", "USDCAD", "AUDUSD",
    "GBPJPY", "AUDJPY", "EURJPY", "CADJPY",
    "EURGBP", "AUDCAD",
    "NAS100", "US30", "US500",
    "XAUUSD"
]

print("🔍 VERIFICATION:")
print("=" * 60)
missing = []
for sym in your_list:
    if sym in symbols:
        print(f"  ✅ {sym}")
    else:
        print(f"  ❌ {sym} - MISSING")
        missing.append(sym)

if missing:
    print(f"\n⚠️  Missing symbols: {', '.join(missing)}")
else:
    print("\n✅ ALL SYMBOLS FROM YOUR WATCHLIST ARE INCLUDED!")

print("=" * 60 + "\n")
