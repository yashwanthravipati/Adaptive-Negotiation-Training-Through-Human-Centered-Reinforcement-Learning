"""Build a private, reproducible finite-case projection from a directory of materials."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from negotrain.cases.documents import SUPPORTED, extract_documents
from negotrain.cases.offers import feasible_best_points, space_size
from negotrain.cases.parser import parse_documents
from negotrain.llm import ClaudeLLM


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(
            "Output already exists; inspect and reuse it instead of paying to recreate it."
        )
    files = sorted(p for p in args.directory.rglob("*") if p.suffix.lstrip(".") in SUPPORTED)
    uploads = [(str(p.relative_to(args.directory)), p.read_bytes()) for p in files]
    documents, warnings = extract_documents(uploads)
    if warnings:
        raise ValueError(warnings)
    client = ClaudeLLM(effort="low")
    case = parse_documents(
        documents,
        client,
        source="Private class materials; simulation projection.",
        instructions="""Produce a compact finite evaluation model with at most SIX issues,
each with at most THREE meaningful, complete options (at most 729 packages). These are
qualitative materials, not official scoring sheets. Clearly state that ALL numeric
utilities and both walk-away values are inferred experimental assumptions. Do not present
them as official scores. Infer the missing Mayor role ONLY from shared_data, never from
the private Officer role or the private Central Authority message. Preserve the Officer's
actual constraints, distinguishing mandatory legal red lines from negotiable implementation
preferences. Include lawful, practical alternatives grounded in the protocols. Permit
tradeoffs on process, timing, resources and safeguards; do not invent a third party.
Choose additive scores with some mutually acceptable packages and positive feasible surplus
for each role, without weakening hard red lines. Explain these assumptions in scoring_notes.
Files under shared_data are public. The Officer rolecard and Central Authority message are
private to the Officer. Do not leak private claims or estimates into the public brief or
the inferred Mayor briefing. Treat rumours and conflicting reports as contested claims.
""",
    )
    if space_size(case) > 729:
        raise ValueError("projection exceeds the declared finite-space limit")
    for role in case.roles:
        if feasible_best_points(case, role.id) <= role.reservation_value:
            raise ValueError(f"no positive feasible surplus for {role.id}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(case.model_dump_json(indent=2))
    manifest = {
        "source_files": {name: hashlib.sha256(data).hexdigest() for name, data in uploads},
        "case_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "scoring": "inferred experimental utilities; not official scoring",
        "model": client.model,
        "usage": client.usage.snapshot(),
        "budget": client.ledger.snapshot(),
    }
    args.output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    print(
        json.dumps(
            {
                "case": str(args.output),
                "issues": len(case.issues),
                "packages": space_size(case),
                "roles": [r.id for r in case.roles],
                "usage": client.usage.snapshot(),
                "budget": client.ledger.snapshot(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
