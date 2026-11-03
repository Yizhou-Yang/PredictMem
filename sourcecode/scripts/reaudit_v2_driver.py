"""v2 重审驱动：修订版审计器 + 冻结版 run_verified_reproduction（真实 ROOT），只读 manifest，不写任何文件。"""
import sys
import json

sys.path.insert(0, "/tmp/v2test/scripts")
sys.path.insert(1, "/data/workspace/PredictMem/scripts")

from collect_verified_results import audit_arm  # noqa: E402

MANIFEST = "/data/workspace/PredictMem/outputs/verified_20261017_relayfix/manifest.json"
ARM_ID = sys.argv[1] if len(sys.argv) > 1 else "appworld_baseline"

manifest = json.load(open(MANIFEST))
arm = next(a for a in manifest["arms"] if a["id"] == ARM_ID)
result = audit_arm(arm, require_finished=False)
print(json.dumps({
    "arm": result["arm"],
    "status": result["status"],
    "execution_verified": result["execution_verified"],
    "official_full_test_execution_verified": result["official_full_test_execution_verified"],
    "scoring_channel": result["scoring_channel"],
    "same_source_comparison_verified": result["same_source_comparison_verified"],
    "wrapper_changed_during_run": result["wrapper_changed_during_run"],
    "issues": result["issues"],
    "retried_attempts": result["retried_attempts"],
    "retried_attempt_count": result["retried_attempt_count"],
    "num_completed_calls": result["num_completed_calls"],
    "total_token_count": result["total_token_count"],
    "success_rate_per_run": result["success_rate_per_run"],
    "MSR": result["MSR"],
    "pass_pow_5": result["pass_pow_5"],
    "pass_at_5": result["pass_at_5"],
}, ensure_ascii=False, indent=2))
