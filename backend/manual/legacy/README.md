## Legacy Manual Scripts

These files were previously named like automated tests (`test_*.py`) but are
actually one-off or exploratory scripts for the old Reddit / hybrid runtime.
They are kept here for historical reference and should not be included in the
current pytest suite.

Additional archived files in this folder are old heuristic drift-analysis or
manual optimization probes that are no longer the supported runtime path.
Use the current Vertex-backed entrypoints instead:

- `backend/run_drift_service.py`
- `backend/analyze_specific_drift.py`
