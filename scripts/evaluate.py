"""Reproducible sim3 evaluations. Live mode uses the globally bounded API gateway."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from negotrain.cases import load_case
from negotrain.evaluation import (
    Experiment,
    calibrate,
    grounded_training,
    oracle_evaluate,
    recovery,
    steering,
    tune_oracle,
    write_json,
)
from negotrain.llm import ClaudeLLM
from negotrain.profiling.belief import CostModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, default=Path("data/cases/private/sim3_inferred.json"))
    parser.add_argument("--role", default="officer")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2822)
    parser.add_argument("--users", type=int, default=128)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--calibration-users", type=int, default=8)
    parser.add_argument("--steering-users", type=int, default=32)
    parser.add_argument("--recovery-users", type=int, default=64)
    parser.add_argument("--reference-sessions", type=int, default=30)
    parser.add_argument("--oracle-users", type=int, default=512)
    parser.add_argument("--development-users", type=int, default=64)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--calibration-from", type=Path)
    parser.add_argument(
        "--stage",
        nargs="+",
        choices=["all", "calibration", "steering", "oracle", "recovery", "training"],
        default=["all"],
    )
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or args.users < 1:
        parser.error("workers must be 1–8 and users must be positive")
    if args.live and args.calibration_from is None:
        parser.error("live evaluation requires independent offline --calibration-from")
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / ".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source = b"".join(p.read_bytes() for p in sorted(Path("src/negotrain").rglob("*.py")))
        config = {
            k: str(v) if isinstance(v, Path) else v
            for k, v in vars(args).items()
            if k not in ("stage", "output", "case")
        }
        config["source_sha256"] = hashlib.sha256(source).hexdigest()
        config["counterpart_model"] = "claude-opus-5-5" if args.live else "rule-based"
        config["user_model"] = "claude-sonnet-5-5" if args.live else "grounded-scripted"
        opponent = ClaudeLLM(effort="low") if args.live else None
        user = ClaudeLLM(model="claude-sonnet-5-5", effort="low") if args.live else None
        experiment = Experiment(
            load_case(args.case), args.role, args.output, config, opponent, user
        )
        try:
            stages = (
                {"calibration", "steering", "oracle", "recovery", "training"}
                if "all" in args.stage
                else set(args.stage)
            )
            calibration_root = args.calibration_from or args.output
            if "calibration" in stages:
                if args.live:
                    parser.error("population calibration is an offline experiment")
                costs = calibrate(experiment, args.calibration_users, args.seed + 100000)
            elif (calibration_root / "costs.json").exists():
                costs = CostModel.model_validate_json((calibration_root / "costs.json").read_text())
            else:
                costs = None
            if "oracle" in stages:
                if costs is None:
                    parser.error("run calibration first")
                tuning = tune_oracle(costs, args.seed + 200000, args.development_users)
                write_json(args.output / "tuning.json", tuning)
                rows, summary = oracle_evaluate(
                    costs, tuning, args.oracle_users, args.seed + 300000
                )
                write_json(args.output / "oracle_rows.json", rows)
                write_json(args.output / "oracle.json", summary)
            else:
                tuning = (
                    json.loads((calibration_root / "tuning.json").read_text())
                    if (calibration_root / "tuning.json").exists()
                    else None
                )
            if "steering" in stages:
                steering(experiment, args.steering_users, args.seed + 400000)
            if "recovery" in stages:
                recovery(
                    experiment,
                    args.recovery_users,
                    args.seed + 500000,
                    tuning["selected"]["forgetting"] if tuning else 0.8,
                    args.reference_sessions,
                )
            if "training" in stages:
                if costs is None or tuning is None:
                    parser.error("run calibration and oracle tuning first")
                grounded_training(
                    experiment, costs, tuning, args.users, args.seed + 600000, args.workers
                )
            print(
                json.dumps(
                    {"completed_stages": sorted(stages), "output": str(args.output)}, indent=2
                )
            )
        finally:
            if args.live:
                write_json(
                    args.output / "usage.json",
                    {
                        "counterpart": opponent.usage.snapshot(),
                        "user": user.usage.snapshot(),
                        "global_ledger": opponent.ledger.snapshot(),
                    },
                )


if __name__ == "__main__":
    main()
