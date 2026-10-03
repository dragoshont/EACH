"""Reproduce the small PUBLIC synthetic suite, not an originality service.

Nothing here executes snippets, loads a model, or reads private target stores.
The synthetic holdout is consumed on its first measurement; replay is regression
evidence, never a new blind evaluation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from each.audit.corpus import InMemoryCorpusAdapter
from each.audit.run import run_audit
from each.hashing import sha256_file, sha256_json, sha256_text


def measure_dataset(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["license"] != "Apache-2.0":
        raise ValueError("only the declared self-authored Apache-2.0 suite is supported")
    projects = data["projects"]
    corpus = [p["reference"] for p in projects]
    revision = sha256_json(corpus)
    units = []
    for p in projects:
        for label in ("exact", "whitespace", "renamed", "semantic"):
            source = p["reference"] if label == "exact" else (
                "\n" + p["reference"].replace("    ", "        ") if label == "whitespace"
                else p[label]
            )
            units.append((p["cluster"] + "-" + label, p["cluster"], label, source, p.get("common", False)))
    units.extend((b["id"], b["id"], "benign", b["source"], False) for b in data["benign"])
    records = []
    for uid, cluster, label, source, common in units:
        audit = run_audit(source, corpus=corpus, corpus_revision=revision)
        statuses = {name: check["status"] for name, check in audit["checks"].items()}
        matched = any(s in {"FLAG", "FAIL"} for s in statuses.values())
        # Correct common-code reference matches are attribution, not false
        # matches. Rejecting them on the heuristic alone is a separate error.
        reference_match_expected = label in {"exact", "whitespace", "renamed"}
        records.append({
            "id": uid, "cluster": cluster, "label": label,
            "subjectSha256": sha256_text(source), "commonCode": common,
            "statuses": statuses, "matchExpected": reference_match_expected,
            "matched": matched,
            "falseFlag": matched and not reference_match_expected,
            "missedMatch": reference_match_expected and not matched,
            "defaultReject": any(s == "FAIL" for s in statuses.values()),
        })
    exact = [r for r in records if r["label"] in {"exact", "whitespace"}]
    renamed = [r for r in records if r["label"] == "renamed"]
    benign = [r for r in records if not r["matchExpected"]]
    counts = {
        "units": len(records), "projectClusters": len(projects),
        "exact": {"total": len(exact), "detected": sum(r["matched"] for r in exact)},
        "renamed": {"total": len(renamed), "detected": sum(r["matched"] for r in renamed)},
        "benignSemanticAndNovel": {"total": len(benign), "falseFlags": sum(r["falseFlag"] for r in benign)},
        "commonCorrectMatches": sum(r["commonCode"] and r["matchExpected"] and r["matched"] for r in records),
        "commonDefaultEscalations": sum(
            r["commonCode"] and r["matchExpected"] and r["defaultReject"] for r in records
        ),
        "misses": sum(r["missedMatch"] for r in records),
    }
    passed = (
        counts["exact"]["detected"] == counts["exact"]["total"]
        and counts["renamed"]["detected"] / counts["renamed"]["total"] >= 0.9
        and counts["benignSemanticAndNovel"]["falseFlags"] / len(benign) <= 0.05
    )
    return {
        "dataset": data["id"], "datasetSha256": sha256_file(path),
        "origin": data["origin"], "license": data["license"],
        "corpusRevision": revision, "referenceSnippetHashes": [sha256_text(s) for s in corpus],
        "toolVersions": audit["toolVersions"], "configuration": audit["configuration"],
        "counts": counts, "thresholdsMet": passed,
        "requiredExternalMembershipQualified": False,
        "externalMembership": "UNAVAILABLE", "licenseScanner": "UNAVAILABLE",
        "declaredSetAdapterExactMatches": sum(
            InMemoryCorpusAdapter(corpus).check(p["reference"]).status == "FAIL" for p in projects
        ),
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    print(json.dumps(measure_dataset(args.dataset), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
