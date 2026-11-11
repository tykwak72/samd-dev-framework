---
name: samd-dhf-engine
description: >-
  Use this skill when interacting with dhf_cli.py or gatekeeper.py to create/update DHF items, resolve Suspect Links, manage configuration baselines (BL-xxx), or execute post-release maintenance (PR-xxx / CR-xxx). Provides CLI commands and references the complete 18-file schema and single-ownership mapping.
---

# ⚙️ SaMD DHF CLI & Gatekeeper Engine Skill

This skill serves as the technical manual for safely registering and modifying DHF items, managing traceability (Suspect Link), baseline locks (`BL-xxx`), and maintenance (`PR/CR`) using `dhf_cli.py` and `gatekeeper.py`.

For exclusive owner (`actor`) IDs and mandatory schema fields per file, consult [references/schema_and_owners.md](references/schema_and_owners.md).

---

## 1. `dhf_cli.py` Core Commands

All commands must include the `-p projects/<project_slug>` option.

### 1.1 Item Registration and Modification (`put`)
```bash
python3 dhf_cli.py -p projects/<slug> put \
  --file <store_filename.json> \
  --actor <authorized_actor_role> \
  --reason "<change_reason>" \
  --item-json '<JSON_string_or_temp_JSON_file_path>'
```
- **Note**: When putting an existing `id`, the engine automatically increments `version` to `old_version + 1`, logs the SHA-256 hash chain in `audit_history.jsonl`, and immediately synchronizes `traceability.json`.

### 1.2 Item Query (`get`)
```bash
python3 dhf_cli.py -p projects/<slug> get --id <ITEM_ID>
```

### 1.3 Bidirectional Traceability Sync & Suspect Link Check (`sync-trace`)
```bash
python3 dhf_cli.py -p projects/<slug> sync-trace
```

### 1.4 Baseline Snapshot Creation and Lock (`create-baseline`)
```bash
python3 dhf_cli.py -p projects/<slug> create-baseline \
  --id BL-001 \
  --stage "Stage 5 Release v1.0.0" \
  --actor 0_orchestrator \
  --reason "Lock baseline for Release v1.0.0"
```

### 1.5 Audit Hash Chain & Store 1:1 Cross-Verification (`verify-history`)
```bash
python3 dhf_cli.py -p projects/<slug> verify-history
```

### 1.6 Render 8 Types of Regulatory Markdown Reports for Auditors (`render-docs`)
```bash
python3 dhf_cli.py -p projects/<slug> render-docs
```

---

## 2. `gatekeeper.py` Core Commands

```bash
# Execute Stage 0 ~ 5 Gate checkpoints
python3 gatekeeper.py -p projects/<slug> check-stage <0|1|2|3|4|5>

# Inspect Stage 3 source code AST signatures and quality (TODO, pass, unapproved SOUP)
python3 gatekeeper.py -p projects/<slug> check-signatures

# Execute Stage 4 independent black-box tests and update 05_tc.json results
python3 gatekeeper.py -p projects/<slug> run-tests
```

---

## 3. Post-Release Maintenance & Change Control (IEC 62304 Clause 6, 8.2, 9) Procedure

After creating a baseline (`BL-001`) via `create-baseline`, `01_urs.json` ~ `05_tc.json` and `rmf_*.json` are all locked (`Baseline Lock`).
To perform defect fixes or changes post-release, you must strictly follow the sequence below:

1. **Issue Problem Report (`PR-xxx`)**:
   - Owner: `6-A_maintenance_change_analyst` (or `4-C_maintenance_change_analyst`)
   - File: `pr_cr_log.json`
   - Mandatory Status: `"resolution_status": "OPEN"`, `"traces_to": {"REL-001": <ver>}`
2. **Issue and Approve Change Request (`CR-xxx`)**:
   - Owner: `6-A_maintenance_change_analyst`
   - File: `pr_cr_log.json`
   - Mandatory Settings:
     - `"traces_to": {"PR-001": <ver>}`
     - `"approval_status": "APPROVED"`
     - `"impacted_item_ids": ["SRS-001", "SAD-001", "SDS-001", ...]` (List of item IDs to directly modify)
     - `"regression_test_ids": ["UT-001", "ST-001", ...]` (List of regression test IDs to execute)
3. **Modify Impact Scope Items and Source Code**:
   - Each document owner updates `impacted_item_ids` and cascading `Suspect Link` items from upstream$\rightarrow$downstream order.
   - Update `# @traces: SDS-xxx@<new_version>` comments in `src/` code to match the latest SDS version.
4. **Execute Regression Tests and Re-audit**:
   - Run `gatekeeper.py run-tests` (all `regression_test_ids` must `PASS`).
   - Update affected Stage audits (`AUD-xxx`).
5. **Close `PR-xxx` and Finalize New Release / Baseline**:
   - Update `resolution_status` of `PR-xxx` to `"CLOSED"` and synchronize `traces_to` of `CR-xxx` with the latest `PR-xxx` version.
   - Register new `REL-002`(`baseline_id: "BL-002"`) in `06_release.json` and approve Stage 5 audit (`AUD-xxx`).
   - Execute `create-baseline --id BL-002` to re-lock, followed by `check-stage 5` and `render-docs`.
