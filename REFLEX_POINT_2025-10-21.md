Reflex Point: 2025-10-21

Summary:
- Decision: Activate Tiingo ML pipeline for local validation and short-term cloud readiness.
- Reason: ML pipeline implemented, tested, and provides better live data source than static CSVs.
- Immediate actions:
  1. Set `USE_TIINGO_PIPELINE = True` in `core/config.py`.
  2. Run `async_scheduler.py` or `python async_scheduler.py` after validation.
- Next steps:
  - Deploy to small cloud VM for 24/7 operation.
  - Add backups, monitoring, and multi-channel alerts.

Notes:
- This reflex is a snapshot for the project state and decision rationale.
- Created by assistant on 2025-10-21.