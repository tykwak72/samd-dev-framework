# SaMD DHF Data Integrity and Single Ownership Governance Rules (Core Governance Rule)

## 1. Absolute Prohibition of Direct Modification to DHF Store and Docs
- `store/*.json`, `store/audit_history.jsonl`, `store/traceability.json`, `docs/*.md` are protected by a SHA-256 hash chain and 1:1 snapshot cross-check (`verify_audit_history`).
- Do not directly overwrite files inside `store/` using `write_file`, `edit_file` tools, or shell scripts (`cat >`, `sed -i`, `python -c "json.dump(...)"`).
- Always use only the official CLI or `DHFManager` API below:
  - Initialization: `python3 dhf_cli.py -p projects/<slug> init`
  - Register/Update: `python3 dhf_cli.py -p projects/<slug> put --file <filename> --actor <role_id> --reason "<reason>" --item-json '<json_or_path>'`
  - Baseline Snapshot: `python3 dhf_cli.py -p projects/<slug> create-baseline --id BL-xxx --stage "Stage 5" --reason "<reason>"`
  - Traceability Sync: `python3 dhf_cli.py -p projects/<slug> sync-trace`
  - Hash Chain & Store Cross-check: `python3 dhf_cli.py -p projects/<slug> verify-history`
  - Regulatory Docs Rendering: `python3 dhf_cli.py -p projects/<slug> render-docs`

## 2. Principle of Immediate Suspect Link (Change Impact) Resolution
- When an upstream item (e.g., `URS-001`) is modified and its version increments (`v+1`), `is_suspect: true` cascades down to downstream referenced items (`SRS`, `SAD`, `SDS`, `TC`, `HAZ/RC`, `AUD`).
- If even a single `suspect_links` remains, all Stage Gates are blocked.
- When changes occur, owner agents of affected downstream documents must sequentially review the new upstream version and update the version number in `traces_to` to restore `suspect_links == []` status.

## 3. Baseline Lock and Post-Release Maintenance (PR/CR) Control (IEC 62304 Clause 6, 8, 9)
- After initial release (`REL-001`) and baseline (`BL-001`) are established, all core DHF deliverables are automatically locked (`Baseline Lock`).
- When bug fixes or functional upgrades are required post-release:
  1. `6-A_maintenance_change_analyst` first registers a Problem Report (`PR-xxx`, `resolution_status: "OPEN"`) in `pr_cr_log.json`.
  2. Subsequently, a Change Request (`CR-xxx`, `traces_to: {"PR-xxx": ver}`, `approval_status: "APPROVED"`, `impacted_item_ids: [...]`, `regression_test_ids: [...]`) must be registered in `pr_cr_log.json` to unlock modifications.
  3. Upon completing modifications and regression testing (100% `PASS` on `regression_test_ids`), update `PR-xxx` to `"CLOSED"` and re-lock by creating a new release (`REL-xxx`) and baseline (`BL-xxx`).
