import random

from negotrain.counterpart.profiles import DIALS, TIERS, describe, sample_profile


def test_tiers_get_harder():
    for tier in range(1, 5):
        assert TIERS[tier + 1].concession_rate < TIERS[tier].concession_rate
        assert TIERS[tier + 1].anchoring > TIERS[tier].anchoring


def test_sample_profile_is_seeded_and_bounded():
    a = sample_profile(3, random.Random(0))
    b = sample_profile(3, random.Random(0))
    assert a == b
    for dial in DIALS:
        assert 0 <= getattr(a, dial) <= 1
        assert abs(getattr(a, dial) - getattr(TIERS[3], dial)) <= 0.1


def test_describe_reflects_dials():
    assert "Concede readily" in describe(TIERS[1])
    assert "Concede rarely" in describe(TIERS[5])
