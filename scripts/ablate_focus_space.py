"""Offline diagnostic: restrict planner actions to the six specified errors."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import negotrain.evaluation as evaluation
from negotrain.cases import load_case
from negotrain.profiling.belief import CostModel, choose_focus
from negotrain.profiling.observations import ERRORS


def error_only_focus(belief, costs, **kwargs):
    return choose_focus(belief, costs, candidates=list(ERRORS), **kwargs)


def main():
    root = Path("results/sim3/offline-v1")
    case = load_case(Path("results/sim3/numeric_case.json"))
    source = b"".join(p.read_bytes() for p in sorted(Path("src/negotrain").rglob("*.py")))
    experiment = evaluation.Experiment(
        case,
        "officer",
        Path("results/sim3/validation/errors_only"),
        {
            "seed": 602822,
            "users": 128,
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "action_space": list(ERRORS),
            "calibration": "Primary costs and tuning held fixed; exploratory diagnostic",
        },
    )
    costs = CostModel.model_validate_json((root / "costs.json").read_text())
    tuning = json.loads((root / "tuning.json").read_text())
    # This process-local ablation leaves the app and all running live workers unchanged.
    evaluation.choose_focus = error_only_focus
    evaluation.grounded_training(experiment, costs, tuning, 128, 602822)


if __name__ == "__main__":
    main()
