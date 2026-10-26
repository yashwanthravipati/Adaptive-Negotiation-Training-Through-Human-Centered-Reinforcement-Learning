"""The counterpart: the LLM agent (agent.py), its rule-based twin (rule_based.py), the
concession schedule both obey (aspiration.py), and behavioral profiles (profiles.py)."""

from negotrain.counterpart.agent import CounterpartAgent, CounterpartMove
from negotrain.counterpart.aspiration import aspiration
from negotrain.counterpart.profiles import TIERS, describe, sample_profile
from negotrain.counterpart.rule_based import Counterpart, RuleBasedCounterpart

__all__ = [
    "TIERS",
    "Counterpart",
    "CounterpartAgent",
    "CounterpartMove",
    "RuleBasedCounterpart",
    "aspiration",
    "describe",
    "sample_profile",
]
