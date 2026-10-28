"""Resume one inactive, failed sampled user; never resample or reset the API ledger."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from negotrain.cases import load_case
from negotrain.evaluation import Experiment, train_user, write_json
from negotrain.llm import ClaudeLLM
from negotrain.profiling.belief import CostModel
from negotrain.virtual_users import VirtualTraits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", type=int, required=True)
    parser.add_argument("--root", type=Path, default=Path("results/sim3/live-v1"))
    parser.add_argument("--case", type=Path, default=Path("data/cases/private/sim3_inferred.json"))
    args = parser.parse_args()
    config = json.loads((args.root / "config.json").read_text())
    if not config["live"] or not 0 <= args.user < config["users"]:
        parser.error("requires an existing live cohort and an original sampled user index")
    seed = config["seed"] + 600000
    rng = random.Random(seed)
    for _ in range(args.user + 1):
        traits = VirtualTraits.sample(rng)
    cal = Path(config["calibration_from"])
    costs = CostModel.model_validate_json((cal / "costs.json").read_text())
    tuning = json.loads((cal / "tuning.json").read_text())
    cp = ClaudeLLM(model=config["counterpart_model"], effort="low")
    user = ClaudeLLM(model=config["user_model"], effort="low")
    exp = Experiment(load_case(args.case), config["role"], args.root, config, cp, user)
    with (exp.raw / f".recover-user{args.user}.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = args.root / f"recovery_user{args.user}.json"
        runs = json.loads(path.read_text()) if path.exists() else []
        source = b"".join(p.read_bytes() for p in sorted(Path("src/negotrain").rglob("*.py")))
        record = {
            "utc": datetime.now(timezone.utc).isoformat(),
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "user": args.user,
            "before": cp.ledger.snapshot(),
            "complete": False,
        }
        runs.append(record)
        write_json(path, runs)
        try:
            train_user(exp, costs, tuning, args.user, traits, seed)
            record["complete"] = True
        except Exception as error:
            record["error_type"] = type(error).__name__
            raise
        finally:
            record.update(
                counterpart=cp.usage.snapshot(),
                user_usage=user.usage.snapshot(),
                after=cp.ledger.snapshot(),
            )
            write_json(path, runs)
            print(json.dumps(record["after"]), flush=True)


if __name__ == "__main__":
    main()
