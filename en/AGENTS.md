# 🏥 Antigravity SaMD / Medical Device SW Development Multi-Agent Framework Constitution (AGENTS.md)

This workspace (`/root/workspace/samd-dev-framework`) is a general-purpose medical device software (SaMD/SiMD) development framework complying with **IEC 62304, ISO 14971, ISO 13485(4.1.6), IEC 82304-1, IEC 81001-5-1, ISO/TR 80002-2, and FDA CSA**.

All agents operating in this workspace (Orchestrator, stage author agents, risk/security analysts, black-box testers, independent auditors) must adhere to the **5 Core Invariants** below without exception.

---

## 1. 5 Core Invariants

1. **Strict Project Isolation**
   - In the framework root (`/root/workspace/samd-dev-framework`), only framework core engines (`dhf_cli.py`, `gatekeeper.py`, `test_framework_csa.py`), master specifications (`BLUEPRINT.md`, `ROADMAP.md`, `SCHEMA_SPEC.md`), and `.agents/` configuration must exist.
   - All medical device development requests from users must be created and executed in an isolated sandbox (`store/`, `docs/`, `src/`, `tests/`) under the **`projects/<project_slug>/`** subdirectory.
   - Always specify the `-p projects/<project_slug>` option when executing all CLI commands.

2. **Deterministic CLI Enforcement & Prohibition of Direct File Modification (No Direct Store Manipulation)**
   - **Direct modification** of `projects/<project_slug>/store/*.json`, `audit_history.jsonl`, `traceability.json`, and `docs/*.md` using text tools (`write_file`, `edit_file`) or shell redirections is **strictly prohibited** (immediately blocked by `.agents/hooks/pre_tool_guard.py` and detected during `verify-history` cross-checks).
   - All item creation, modification, versioning, and rendering must be performed exclusively via **`python3 dhf_cli.py -p projects/<project_slug> ...`**.

3. **Strict Single Ownership & Feedback Loops**
   - Each DHF JSON file can only be modified by its exclusive owner (`actor`) defined in [`SCHEMA_SPEC.md`](file:///root/workspace/samd-dev-framework/SCHEMA_SPEC.md):
     - `00_intake.json`: `0-0_intake_agent`
     - `00_literature.json`: `0-A_literature_researcher`
     - `00_regulatory.json`: `0-B_regulatory_strategist`
     - `00_sdp_plan.json`: `0-C_sdp_planner`, `0_orchestrator`
     - `01_urs.json`, `02_srs.json`: `1-A_requirements_author`
     - `opt_*.json`: `1-E_option_domain_author`
     - `03_sad_soup.json`, `04_sds.json`: `2-A_software_architect`
     - `src/` source code: `3-A_developer`
     - `05_tc.json`, `tests/`: `4-A_blackbox_tester`
     - `06_release.json`: `5-A_release_author`
     - `rmf_safety.json`: `1-B_safety_risk_analyst`, `2-B_dfmea_risk_analyst`, `3-B_code_safety_analyst`, `4-B_residual_risk_evaluator`
     - `rmf_security.json`: `1-C_security_risk_analyst`, `2-C_threat_security_analyst`, `3-B_code_safety_analyst`, `4-B_residual_risk_evaluator`
     - `audit_findings.json`: `0-D_stage0_auditor`, `1-D_stage1_auditor`, `2-D_stage2_auditor`, `3-C_stage3_auditor`, `4-D_stage4_auditor`, `5-B_final_release_auditor`
     - `cm_baselines.json`: `0_orchestrator` (`create-baseline`)
     - `pr_cr_log.json`: `6-A_maintenance_change_analyst`, `4-C_maintenance_change_analyst`
   - Risk analysts (`1-B`, `1-C`) or auditors (`*-D`) never modify requirements or design specifications directly, updating only their respective output files (`rmf_*.json`, `audit_findings.json`), while document owners (`1-A`, `2-A`, `3-A`, `4-A`) consume them as inputs to update their documents (version `v+1`).

4. **Black-box Isolation & AST Signature Contract**
   - `2-A (Architect)` must specify exact `target_file_path`, `callable_name`, `callable_signature`, `parameters_contract`, `return_contract`, and `exception_contract` in `04_sds.json`.
   - `3-A (Developer)` must prepend `# @traces: SDS-xxx@<current_version>` comment at the top of `src/` code and match signatures 100%; `TODO`/`FIXME`, standalone `pass` bodies, and unapproved SOUP `import`s are prohibited.
   - `4-A (Black-box Tester)` authors test code looking solely at `04_sds.json` and upstream specifications **without inspecting `src/` source code**.

5. **Stage Gatekeeper Checkpoints & Independent Subagent Audits (Zero-Trust Independent Audit)**
   - At the conclusion of each Stage (0~5), passing `python3 gatekeeper.py -p projects/<project_slug> check-stage <0~5>` is mandatory.
   - Upon completion of major milestones or releases/maintenance, an **independent auditor subagent with decoupled context** must be launched via `invoke_subagent` to perform third-party audits and verify `PASS`, eliminating author bias (Context Bias).

---

## 2. Specialized Skills Guide

Depending on the task nature, read `SKILL.md` of the following skills packaged in `.agents/skills/` and follow procedures:
- **`samd-orchestrator`**: Full-lifecycle orchestration procedures from new medical device intake through Stage 0~5 execution and post-release maintenance (PR/CR)
- **`samd-dhf-engine`**: Detailed `dhf_cli.py` and `gatekeeper.py` CLI commands, 18-file JSON schema cheat sheet, Suspect Link resolution, and baseline lock management
- **`samd-independent-auditor`**: Standard audit runbook for independent third-party quality/security auditors and red-team verification subagents
