#!/usr/bin/env python3
"""
run_full_audit.py - Automated full-audit verification script for independent SaMD auditors

Usage:
  python3 .agents/skills/samd-independent-auditor/scripts/run_full_audit.py --project-dir projects/<slug> [--max-stage 5]
"""

import sys
import json
import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full independent audit on an isolated SaMD project")
    parser.add_argument("--project-dir", "-p", required=True, help="Target project directory (e.g. projects/pathology_slide_qc)")
    parser.add_argument("--max-stage", type=int, default=5, choices=[0, 1, 2, 3, 4, 5], help="Highest stage to audit (default: 5)")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    workspace_root = script_dir.parent.parent.parent.parent
    sys.path.insert(0, str(workspace_root))

    from dhf_cli import DHFManager
    from gatekeeper import Gatekeeper

    proj_path = Path(args.project_dir).resolve()
    if not proj_path.exists():
        print(f"Error: Project directory not found: {proj_path}", file=sys.stderr)
        sys.exit(1)

    mgr = DHFManager(workspace_root=proj_path)
    gk = Gatekeeper(workspace_root=proj_path)

    report = {
        "project_dir": str(proj_path),
        "max_stage": args.max_stage,
        "checks": {},
        "overall_verdict": "PASS",
        "failures": []
    }

    # 1. Audit History & Store 1:1 Cross-Check
    hist_ok, hist_errs = mgr.verify_audit_history()
    report["checks"]["audit_history_integrity"] = {"passed": hist_ok, "errors": hist_errs}
    if not hist_ok:
        report["overall_verdict"] = "FAIL"
        report["failures"].extend(hist_errs)

    # 2. Traceability & Suspect Links
    trace_doc = mgr.sync_traceability()
    cov = trace_doc.get("coverage_summary", {})
    broken = cov.get("broken_links", [])
    suspects = cov.get("suspect_links", [])
    uncovered = cov.get("uncovered_items", []) if args.max_stage >= 5 else []
    trace_ok = (len(broken) == 0 and len(suspects) == 0 and (args.max_stage < 5 or len(uncovered) == 0))
    report["checks"]["traceability"] = {
        "passed": trace_ok,
        "total_items": cov.get("total_items", 0),
        "broken_links": broken,
        "suspect_links": suspects,
        "uncovered_items": cov.get("uncovered_items", [])
    }
    if not trace_ok:
        report["overall_verdict"] = "FAIL"
        report["failures"].append(f"Traceability failure: broken={len(broken)}, suspect={len(suspects)}, uncovered={len(uncovered)}")

    # 3. Stage 3+ AST Signature Check
    if args.max_stage >= 3:
        ast_ok, ast_errs = gk.check_signatures_and_code_quality()
        report["checks"]["ast_signatures"] = {"passed": ast_ok, "errors": ast_errs}
        if not ast_ok:
            report["overall_verdict"] = "FAIL"
            report["failures"].extend(ast_errs)

    # 4. Stage 4+ Blackbox Tests
    if args.max_stage >= 4:
        test_res = gk.run_blackbox_tests(mask_source=True)
        tests_ok = (test_res["total"] > 0 and test_res["failed"] == 0 and test_res["passed"] == test_res["total"])
        report["checks"]["blackbox_tests"] = {
            "passed": tests_ok,
            "total": test_res["total"],
            "passed_count": test_res["passed"],
            "failed_count": test_res["failed"]
        }
        if not tests_ok:
            report["overall_verdict"] = "FAIL"
            report["failures"].append(f"Blackbox tests failed: {test_res}")

    # 5. Stage 0 ~ max_stage Gate Checks
    stage_results = {}
    for st in range(0, args.max_stage + 1):
        st_ok, st_errs = gk.check_stage_gate(st)
        stage_results[f"stage_{st}"] = {"passed": st_ok, "errors": st_errs}
        if not st_ok:
            report["overall_verdict"] = "FAIL"
            report["failures"].extend([f"[Stage {st}] {e}" for e in st_errs])
    report["checks"]["stage_gates"] = stage_results

    # 6. Regulatory Markdown Docs Check
    expected_docs = [
        "00_SDP_Project_Plan.md",
        "01_URS_User_Requirements_Specification.md",
        "02_SRS_Software_Requirements_Specification.md",
        "03_RMF_Integrated_Risk_and_Security_Report.md",
        "04_SAD_SDS_Design_Specification.md",
        "05_VNV_Verification_Report.md",
        "VT_Manual_Test_Checklist.md",
        "99_RTM_Traceability_Matrix.md"
    ]
    missing_docs = [d for d in expected_docs if not (proj_path / "docs" / d).exists()]
    docs_ok = len(missing_docs) == 0
    report["checks"]["regulatory_docs"] = {"passed": docs_ok, "missing_docs": missing_docs}
    if not docs_ok:
        report["overall_verdict"] = "FAIL"
        report["failures"].append(f"Missing regulatory docs: {missing_docs}")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"=== Independent Full Audit Report for '{proj_path.name}' ===")
        print(f"1. Audit History & Store 1:1 Integrity : {'PASS' if hist_ok else 'FAIL'}")
        print(f"2. Traceability ({cov.get('total_items', 0)} items, 0 suspect) : {'PASS' if trace_ok else 'FAIL'}")
        if args.max_stage >= 3:
            print(f"3. AST Signatures & Code Quality       : {'PASS' if report['checks']['ast_signatures']['passed'] else 'FAIL'}")
        if args.max_stage >= 4:
            bt = report["checks"]["blackbox_tests"]
            print(f"4. Blackbox Tests ({bt['passed_count']}/{bt['total']} passed)         : {'PASS' if bt['passed'] else 'FAIL'}")
        for st in range(0, args.max_stage + 1):
            sr = stage_results[f"stage_{st}"]
            print(f"5.{st} Stage {st} Gate Check                : {'PASS' if sr['passed'] else 'FAIL'}")
        print(f"6. Regulatory Markdown Docs (8 files)  : {'PASS' if docs_ok else 'FAIL'}")
        print(f"------------------------------------------------------------")
        print(f"FINAL AUDIT VERDICT: {report['overall_verdict']}")
        if report["failures"]:
            print("\nFailures:")
            for f in report["failures"]:
                print(f"  - {f}")

    if report["overall_verdict"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
