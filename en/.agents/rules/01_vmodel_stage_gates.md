# IEC 62304 V-Model Stage 0~5 Gate Acceptance Criteria Rules (V-Model Stage Gates Rule)

For every project (`projects/<slug>/`), running `python3 gatekeeper.py -p projects/<slug> check-stage <0~5>` upon completing each Stage must pass the criteria below 100% before proceeding to the next stage.

## 1. Common Gate Criteria (Mandatory for All Stages)
- `verify_audit_history()` == `True` (100% integrity match between SHA-256 hash chain and `store/*.json` 1:1 snapshot)
- `broken_links == []` (0 references to non-existent upstream IDs)
- `suspect_links == []` (0 unreviewed downstream items after upstream version change)

## 2. Symmetrical Verification Criteria by Stage
- **Stage 0 Gate (Planning & Execution Plan)**:
  - `INT` $\rightarrow$ `LIT` and `REG` downward links complete
  - `REG` $\rightarrow$ `SDP` downward link complete
  - Audit verdict `verdict == "PASS"` for `stage == "Stage 0"` in `audit_findings.json`
- **Stage 1 Gate (Requirements & Initial Risk/Security Analysis)**:
  - `INT` $\rightarrow$ `URS` $\rightarrow$ `SRS` downward links complete
  - All `HAZ-SAF`(`control_required=True`) $\rightarrow$ `RC-SAF` $\rightarrow$ `SRS` reflected completely
  - All `HAZ-SEC` $\rightarrow$ `RC-SEC` $\rightarrow$ `SRS` reflected completely
  - Audit verdict `PASS` for `stage == "Stage 1"`
- **Stage 2 Gate (Architecture & Detailed Design Signature Contracts)**:
  - All `SRS` $\rightarrow$ `SAD` and `SDS` downward links complete
  - All `SDS` equipped with `target_file_path`, `callable_name`, `callable_signature`, `parameters_contract`, `return_contract`, `exception_contract`
  - Audit verdict `PASS` for `stage == "Stage 2"`
- **Stage 3 Gate (Source Code Unit Implementation & AST Verification)**:
  - `gatekeeper.py check-signatures` pass mandatory
  - Exact version match in `# @traces: SDS-xxx@<latest_version>` comment inside `src/` code
  - 100% match in function/class names and parameter order/names based on Python AST parsing
  - 0 `TODO`/`FIXME`/`TBD`/`XXX` comments, 0 empty functions/standalone `pass`/`NotImplementedError`
  - 0 imports of external third-party packages not registered in `03_sad_soup.json`
  - Audit verdict `PASS` for `stage == "Stage 3"`
- **Stage 4 Gate (V-Model 4-Tier Independent Verification & Residual Risk Closure)**:
  - `test_callable_name` of all automated tests registered in `05_tc.json` exists in `tests/*.py` AST with execution result `PASS`
  - 4-Tier symmetrical coverage: $\forall \text{SDS} \Rightarrow \text{UT(PASS)}$, $\forall \text{SAD} \Rightarrow \text{IT(PASS)}$, $\forall \text{SRS} \Rightarrow \text{ST(PASS)}$, $\forall \text{URS} \Rightarrow \text{VT(PASS)}$
  - Risk control fault injection testing: $\forall (\text{RC-SAF}, \text{RC-SEC}) \Rightarrow \text{Negative Test (is\_negative\_test=True, PASS)}$
  - Closure of residual risk acceptance (`residual_acceptable == True`) for all `HAZ-SAF` and `HAZ-SEC`
  - Audit verdict `PASS` for `stage == "Stage 4"`
- **Stage 5 Gate (Final SW Release & Baseline Lock)**:
  - `uncovered_items == []` (0 orphan items)
  - `overall_residual_risk_acceptable == True` for the latest `REL-xxx` in `06_release.json`
  - `baseline_id`(`BL-xxx`) referenced by the latest `REL-xxx` exists in `cm_baselines.json` and matches 100% of latest versions of all active items
  - All `AUD-xxx` and `PR-xxx` are `CLOSED` (or if `DEFERRED`, safety justification is documented in `known_remaining_anomalies`)
  - Audit verdict `PASS` for `stage == "Stage 5"`
