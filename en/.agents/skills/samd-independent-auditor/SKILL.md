---
name: samd-independent-auditor
description: >-
  Use this skill when acting as an Independent Third-Party Quality/Security Auditor or Red-Team Verifier subagent to audit a SaMD project or the framework itself under Zero-Trust principles (ISO 13485, IEC 62304, ISO/TR 80002-2, FDA CSA).
---

# 🛡️ SaMD Independent Third-Party Auditor & Red-Team Runbook

This skill serves as the standard audit procedure manual for an **Independent Third-Party Quality/Security Auditor** subagent, decoupled from author agents, to verify target projects (`projects/<slug>/`) and the framework engine under Zero-Trust principles.

---

## 1. Auditor Core Code of Conduct (Zero-Trust Rules)

1. **Do not trust author claims at face value**: Always execute commands directly and cross-check raw JSON files and source code on disk.
2. **Non-destructive principle for target projects**: When conducting penetration/tampering attack (Red-Team Attack) tests, always copy the target project to a `tempfile.TemporaryDirectory()` and avoid corrupting original `projects/<slug>/` data.

---

## 2. Standard Comprehensive Audit Script Execution

To empirically measure the full-lifecycle integrity of the target project (`projects/<slug>`) at once, execute the script below:

```bash
python3 .agents/skills/samd-independent-auditor/scripts/run_full_audit.py \
  --project-dir projects/<slug> \
  --max-stage 5
```

This script sequentially measures the following 6 core areas and outputs results:
1. **SHA-256 Hash Chain and Store 1:1 Snapshot Cross-Check** (`verify-history`)
2. **Central Bidirectional Traceability and Verification of 0 Orphan/Broken/Suspect Links** (`sync-trace`)
3. **Stage 3 AST Signature Contracts, `@traces` Version Match, Absence of `TODO`/`pass`/Unapproved SOUP** (`check-signatures`)
4. **Stage 4 Black-box Test Execution and Verification of `test_callable_name` Existence in AST** (`run-tests`)
5. **Verification of Gatekeeper Passes across Stage 0 ~ `max-stage`** (`check-stage`)
6. **Verification of 8 Regulatory Reports (`docs/*.md`) Existence and Fresh Rendering**

---

## 3. Framework Computer Software Assurance (CSA) Self-Validation Execution

When verifying the integrity of the framework engine (`dhf_cli.py`, `gatekeeper.py`, `.agents/` packaging) itself, run the CSA test suite from the root:

```bash
python3 -m pytest -v test_framework_csa.py
```

---

## 4. Audit Result Reporting Format

Upon completing the audit, report to the caller (parent agent) including the following items:
- **Audit Target and Scope**
- **Empirical Measurement Commands and Output Summary Table per Item**
- **Presence of Identified Non-conformities or Vulnerabilities (Count and detailed findings)**
- **Final Audit Verdict (`PASS` or `FAIL`)**
