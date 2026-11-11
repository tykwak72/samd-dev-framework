---
name: samd-orchestrator
description: >-
  Use this skill when the user requests to develop, plan, or maintain a medical device software (SaMD or SiMD) project following the IEC 62304 V-model lifecycle, ISO 14971 risk management, and FDA CSA governance. Guides the Orchestrator agent through project isolation, Stage 0-5 execution, feedback loops, and independent subagent audits.
---

# 👑 SaMD V-Model Lifecycle Orchestrator Runbook

This skill serves as the standard Orchestrator runbook to receive medical device software (SaMD/SiMD) development or maintenance requests and direct the full lifecycle from **Stage 0 (Planning) to Stage 5 (Release) and Stage 6 (Post-Release Maintenance)**.

---

## 1. Isolated Project Initialization (Step 0)

All medical device projects must be isolated within a `projects/<project_slug>/` folder, separated from the framework core engine.

1. Run the bootstrap script to create an isolated project sandbox:
   ```bash
   python3 .agents/skills/samd-orchestrator/scripts/bootstrap_project.py --slug <project_slug>
   ```
   (This script creates `projects/<project_slug>/{store,docs,src,tests}` and executes `dhf_cli.py init`.)

---

## 2. Stage 0 ~ Stage 5 V-Model Execution Procedures

For detailed JSON schemas and owner (`actor`) IDs for each stage, consult [schema_and_owners.md](../samd-dhf-engine/references/schema_and_owners.md) in the `samd-dhf-engine` skill.

### Stage 0: Intake · Literature · Regulatory Classification · Development Plan (SDP)
1. **`0-0_intake_agent`**: Identify missing clinical information from user requirements (indications, patient population, SaMD/SiMD, AI/network/alarm presence) and register `00_intake.json`(`INT-001`).
2. **`0-A_literature_researcher`**: Investigate clinical guidelines and benchmark literature, registering `00_literature.json`(`LIT-001`, `traces_to: {"INT-001": 1}`).
3. **`0-B_regulatory_strategist`**: Determine safety class (Class A/B/C), target regions, and applicable standards, registering `00_regulatory.json`(`REG-001`, `traces_to: {"INT-001": 1}`).
4. **`0-C_sdp_planner`**: Define development language, coverage criteria, and workflow steps, registering `00_sdp_plan.json`(`SDP-001`, `traces_to: {"REG-001": 1}`).
5. **`0-D_stage0_auditor`**: Perform compliance audit and register `audit_findings.json`(`AUD-001`, `stage: "Stage 0"`, `verdict: "PASS"`).
6. **Pass Gate Checkpoint**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-stage 0
   ```

### Stage 1: Requirements Specification (URS/SRS) & Risk/Security Feedback Loops
1. **`1-A_requirements_author` (Draft)**: Register `01_urs.json`(`URS-xxx`) and `02_srs.json`(`SRS-xxx` functional/performance requirements draft). (If active options exist, `1-E_option_domain_author` registers `opt_*.json`).
2. **`1-B_safety_risk_analyst`**: Register hazards (`HAZ-SAF-xxx`) and safety risk control measures (`RC-SAF-xxx`) in `rmf_safety.json`. *(Never modify `02_srs.json` directly!)*
3. **`1-C_security_risk_analyst`**: Register security threats (`HAZ-SEC-xxx`) and security control measures (`RC-SEC-xxx`, including safety tradeoff review) in `rmf_security.json`.
4. **`1-A_requirements_author` (Feedback Incorporation)**: Read `RC-SAF-xxx` and `RC-SEC-xxx` as inputs, appending and updating safety/security requirements in `02_srs.json` (linking `RC-*` in `traces_to`).
5. **`1-D_stage1_auditor`**: Register `audit_findings.json`(`stage: "Stage 1"`, `verdict: "PASS"`).
6. **Pass Gate Checkpoint**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-stage 1
   ```

### Stage 2: Architecture (SAD/SOUP) & Detailed Design (SDS Signature Contracts)
1. **`2-A_software_architect`**:
   - Register module architecture (`SAD-xxx`) and external packages (`SOUP-xxx`) in `03_sad_soup.json`.
   - Register strict signature contracts for black-box testing (`SDS-xxx`: `target_file_path`, `callable_name`, `callable_signature`, `parameters_contract`, `return_contract`, `exception_contract`) in `04_sds.json`.
2. If necessary, `2-B_dfmea_risk_analyst` / `2-C_threat_security_analyst` identify additional design flaw risks and incorporate feedback in `1-A` $\rightarrow$ `2-A` order.
3. **`2-D_stage2_auditor`**: Register `audit_findings.json`(`stage: "Stage 2"`, `verdict: "PASS"`).
4. **Pass Gate Checkpoint**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-stage 2
   ```

### Stage 3: Source Code Unit Implementation & AST Contract Verification
1. **`3-A_developer`**: Implement Python code in `projects/<project_slug>/src/` matching `04_sds.json` contracts 100%.
   - Must include the comment `# @traces: SDS-xxx@<latest_version>` above functions.
   - `TODO`, `FIXME`, standalone `pass` bodies, and unapproved SOUP `import`s are immediately blocked.
2. **AST Signature Check**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-signatures
   ```
3. **`3-C_stage3_auditor`**: Register `audit_findings.json`(`stage: "Stage 3"`, `verdict: "PASS"`) and pass `check-stage 3`.

### Stage 4: V-Model 4-Tier Independent Verification (UT/IT/ST/VT) & Residual Risk Closure
1. **`4-A_blackbox_tester`**: Without inspecting `src/` code, rely solely on specifications (`04_sds`, `03_sad_soup`, `02_srs`, `01_urs`, `rmf_*`) to register test specifications (`UT`, `IT`, `ST`, `VT` and `RC` target `is_negative_test: true` fault injection tests) in `05_tc.json` and author `projects/<project_slug>/tests/test_*.py`.
   - Note: `test_callable_name` in `05_tc.json` must match function names in `tests/test_*.py` AST exactly.
2. **Execute Black-Box Tests**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> run-tests
   ```
3. **`4-B_residual_risk_evaluator`**: After verifying all tests `PASS`, finalize residual risks (`residual_acceptable: true`) in `rmf_safety.json` and `rmf_security.json`. (If downstream items become Suspect as a result, synchronize versions in `RC` $\rightarrow$ `SRS` $\rightarrow$ `SAD/SDS` (including `src/` `@traces` versions) $\rightarrow$ `TC` order.)
4. **`4-D_stage4_auditor`**: Register `audit_findings.json`(`stage: "Stage 4"`, `verdict: "PASS"`) and pass `check-stage 4`.

### Stage 5: Final SW Release & Baseline Snapshot Lock
1. **`5-A_release_author`**: Register `REL-xxx`(`baseline_id: "BL-xxx"`, `overall_residual_risk_acceptable: true`) in `06_release.json`.
2. **`5-B_final_release_auditor`**: Register `audit_findings.json`(`stage: "Stage 5"`, `verdict: "PASS"`).
3. **`0_orchestrator` (Baseline Creation)**:
   ```bash
   python3 dhf_cli.py -p projects/<project_slug> create-baseline --id BL-001 --stage "Stage 5 Release v1.0.0" --reason "Official Release Baseline"
   ```
4. **Final Gate Checkpoint & Regulatory Docs Rendering**:
   ```bash
   python3 gatekeeper.py -p projects/<project_slug> check-stage 5
   python3 dhf_cli.py -p projects/<project_slug> render-docs
   python3 dhf_cli.py -p projects/<project_slug> verify-history
   ```

---

## 3. Independent Third-Party Auditor Subagent Invocation (Mandatory)

Upon completing Stage 2 and completing Stage 5 final release (or maintenance release), always invoke `invoke_subagent` to have a context-decoupled independent auditor execute a full audit based on the `samd-independent-auditor` skill and report findings.
