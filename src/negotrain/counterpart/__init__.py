"""The counterpart agent (agent.py) and its behavioral profiles and curriculum (profiles.py)."""

from negotrain.counterpart.agent import CounterpartAgent, CounterpartMove
from negotrain.counterpart.profiles import TIERS, describe, sample_profile

__all__ = ["TIERS", "CounterpartAgent", "CounterpartMove", "describe", "sample_profile"]
