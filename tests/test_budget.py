from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from negotrain.budget import BudgetExceeded, SpendLedger
from negotrain.llm import ClaudeLLM


def test_reservations_are_atomic_across_independent_connections(tmp_path):
    path = tmp_path / "budget.sqlite3"
    SpendLedger(path, 10)

    def reserve(_):
        ledger = SpendLedger(path, 10)
        try:
            return ledger.reserve("test", 1)
        except BudgetExceeded:
            return None

    with ThreadPoolExecutor(max_workers=8) as pool:
        identifiers = list(pool.map(reserve, range(40)))
    assert sum(x is not None for x in identifiers) == 10
    assert SpendLedger(path).snapshot()["accounted_usd"] == 10


def test_restart_and_unknown_failure_do_not_release_reservation(tmp_path):
    path = tmp_path / "budget.sqlite3"
    ledger = SpendLedger(path, 10)
    failed = ledger.reserve("test", 8)
    ledger.uncertain(failed, "Timeout")
    restarted = SpendLedger(path)
    assert restarted.snapshot()["remaining_usd"] == 2
    with pytest.raises(BudgetExceeded):
        restarted.reserve("test", 3)
    successful = restarted.reserve("test", 2)
    restarted.settle(successful, 0.5, {"input_tokens": 1})
    assert restarted.snapshot()["accounted_usd"] == 8.5
    with pytest.raises(ValueError):
        restarted.settle(successful, 0, {})
    with pytest.raises(ValueError):
        SpendLedger(tmp_path / "other", 151)


class FakeClient:
    def __init__(self, ledger, fail=False):
        self.ledger, self.fail = ledger, fail
        self.beta = SimpleNamespace(messages=self)
        self.options = {}
        self.requests = []

    def with_options(self, **options):
        self.options = options
        return self

    def create(self, **request):
        assert self.ledger.snapshot()["accounted_usd"] > 8
        self.requests.append(request)
        if self.fail:
            raise TimeoutError("uncertain")
        return SimpleNamespace(
            usage=SimpleNamespace(input_tokens=100, output_tokens=10),
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text="hello")],
        )


def test_gateway_reserves_before_network_and_settles_provider_usage(tmp_path):
    ledger = SpendLedger(tmp_path / "budget")
    client = FakeClient(ledger)
    llm = ClaudeLLM(client=client, ledger=ledger)
    assert llm.complete("s", [{"role": "user", "content": "hi"}], max_tokens=100) == "hello"
    assert client.options["max_retries"] == 0
    assert "fallbacks" not in client.requests[0]
    assert ledger.snapshot()["actual_usd"] == pytest.approx(0.0006)
    assert ledger.snapshot()["unresolved_requests"] == 0


def test_gateway_retains_bound_after_network_failure(tmp_path):
    ledger = SpendLedger(tmp_path / "budget")
    llm = ClaudeLLM(client=FakeClient(ledger, fail=True), ledger=ledger)
    with pytest.raises(TimeoutError):
        llm.complete("s", [], max_tokens=100)
    assert ledger.snapshot()["accounted_usd"] == pytest.approx(8.002, abs=0.000002)
    with pytest.raises(ValueError):
        ClaudeLLM(model="unpriced-model")
