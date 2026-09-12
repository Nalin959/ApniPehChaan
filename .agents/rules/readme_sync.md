# Rule: Automated README Maintenance & Verification

1. **Continuous Synchronization**:
   - Keep `README.md` (and related project documentation like `HANDOVER.md` and `DEMO.md`) synchronized with real implementation status.
   - When features are added, endpoints modified, or security layers hardened, update `README.md` to reflect them accurately.

2. **Ground Truth Validation**:
   - Always run the test suite (`./.venv/bin/python test_system.py`) before updating badge counts or test metrics in documentation.
   - Only document capabilities that are verified and working in code (zero hallmarked or unverified claims).

3. **Scheduled Periodic Sync**:
   - At 30-minute intervals or after completing significant work units, inspect git status, recent commits/diffs, and audit `README.md` for any required updates.
