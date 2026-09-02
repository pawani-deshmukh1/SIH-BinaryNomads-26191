"""
run_bc.py -- Export only landslide (B) and flood (C) models.
Model A (damage) already exported and verified. Run this to complete Phase 0.
"""
import os, sys
os.environ["ORT_LOGGING_LEVEL"] = "3"

# Add project root to path so imports work
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

# Import both export functions from the main script
import importlib.util
spec = importlib.util.spec_from_file_location(
    "export_onnx",
    str(Path(__file__).parent / "export_onnx.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

results = {}
results["landslide"] = mod.export_landslide()
results["flood"]     = mod.export_flood()

print()
print("=" * 40)
for name, passed in results.items():
    print(f"  {name:<12} [{'PASS' if passed else 'FAIL'}]")

if all(results.values()):
    print("\n  Models B+C complete. Phase 0 DONE (A already passed).")
    sys.exit(0)
else:
    print("\n  One or more failed -- check output above.")
    sys.exit(1)
