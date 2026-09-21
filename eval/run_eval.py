"""
Eval harness for diagnose_incident's root-cause accuracy.

Calls the (mocked) RCA service directly over HTTP — bypassing the MCP
transport entirely, since we're evaluating the classifier's accuracy, not
the MCP plumbing. Computes precision/recall/support per root-cause class
and writes eval/eval_report.md.

Ground rule from the project brief: report the honest number, even if
mediocre. Do not cherry-pick scenarios or reinterpret results to look
better. See eval_report.md's discussion section for what this run actually
tells us given that rca_mock.py returns a uniformly random root_cause
regardless of the metrics it's given.
"""
import json
import os
from collections import defaultdict
from pathlib import Path

import httpx

EVAL_DIR = Path(__file__).parent
SCENARIOS_PATH = EVAL_DIR / "synthetic_incidents.json"
REPORT_PATH = EVAL_DIR / "eval_report.md"

RCA_SERVICE_URL = os.environ.get("RCA_SERVICE_URL", "http://localhost:8001")


def load_scenarios() -> list[dict]:
    with open(SCENARIOS_PATH) as f:
        return json.load(f)


def run_scenarios(scenarios: list[dict]) -> list[dict]:
    results = []
    with httpx.Client(timeout=10.0) as client:
        for scenario in scenarios:
            response = client.post(
                f"{RCA_SERVICE_URL}/rca/diagnose",
                json={"service_name": scenario["service_name"], "metrics": scenario["metrics"]},
            )
            response.raise_for_status()
            body = response.json()
            results.append(
                {
                    **scenario,
                    "predicted_root_cause": body["root_cause"],
                    "confidence": body["confidence"],
                }
            )
    return results


def compute_metrics(results: list[dict]) -> tuple[dict, float]:
    classes = sorted(
        {r["expected_root_cause"] for r in results} | {r["predicted_root_cause"] for r in results}
    )
    true_positives: dict[str, int] = defaultdict(int)
    false_positives: dict[str, int] = defaultdict(int)
    false_negatives: dict[str, int] = defaultdict(int)

    for r in results:
        expected, predicted = r["expected_root_cause"], r["predicted_root_cause"]
        if expected == predicted:
            true_positives[expected] += 1
        else:
            false_positives[predicted] += 1
            false_negatives[expected] += 1

    per_class = {}
    for c in classes:
        tp, fp, fn = true_positives[c], false_positives[c], false_negatives[c]
        support = tp + fn
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        per_class[c] = {"precision": precision, "recall": recall, "support": support}

    accuracy = sum(1 for r in results if r["expected_root_cause"] == r["predicted_root_cause"]) / len(results)
    return per_class, accuracy


def write_report(results: list[dict], per_class: dict, accuracy: float) -> None:
    n = len(results)
    n_classes = len(per_class)
    random_baseline = 1 / n_classes if n_classes else 0.0

    lines = []
    lines.append("# diagnose_incident eval report\n")
    lines.append(
        f"Ran {n} labeled synthetic incidents against the mocked RCA service "
        f"(`{RCA_SERVICE_URL}`), calling it directly over HTTP (bypassing MCP transport).\n"
    )
    lines.append(f"**Overall accuracy: {accuracy:.1%}** ({sum(1 for r in results if r['expected_root_cause'] == r['predicted_root_cause'])}/{n} correct)\n")

    lines.append("## Per-class precision / recall\n")
    lines.append("| Root cause | Precision | Recall | Support |")
    lines.append("|---|---|---|---|")
    for cls, m in sorted(per_class.items()):
        precision = f"{m['precision']:.2f}" if m["precision"] is not None else "n/a"
        recall = f"{m['recall']:.2f}" if m["recall"] is not None else "n/a"
        lines.append(f"| {cls} | {precision} | {recall} | {m['support']} |")
    lines.append("")

    lines.append("## Discussion\n")
    lines.append(
        f"This eval measures `rca_mock.py`, not a real classifier — and it shows. "
        f"With {n_classes} root-cause classes, random guessing would score about "
        f"{random_baseline:.1%} accuracy, and the observed {accuracy:.1%} is in that "
        "same range, because the mock picks `root_cause` via `random.choice()` and "
        "never looks at the `metrics` payload at all. The per-class numbers bounce "
        "around based on which labels happened to get lucky matches in this run, not "
        "because the mock is better at diagnosing some root causes than others."
    )
    lines.append(
        "\nThis result is expected and, per the project's ground rules, reported "
        "honestly rather than reframed to look better: at this stage there is no "
        "real signal to evaluate. This eval becomes meaningful once `RCA_SERVICE_URL` "
        "points at the real upstream RCA service — rerunning it then, unmodified, is "
        "the actual test of whether diagnose_incident works."
    )
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines))


def main() -> None:
    scenarios = load_scenarios()
    results = run_scenarios(scenarios)
    per_class, accuracy = compute_metrics(results)
    write_report(results, per_class, accuracy)
    print(f"Accuracy: {accuracy:.1%} ({len(results)} scenarios). Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
