import math

import pytest

from binary import extract_probability_from_response_as_percentage_not_decimal
from multiple_choice import (
    extract_option_probabilities_from_response,
    normalize_probabilities,
)
from numeric import (
    clean,
    enforce_strict_increasing,
    extract_percentiles_from_response,
    generate_continuous_cdf,
)


def test_binary_probability_parses_and_clamps_extremes():
    assert extract_probability_from_response_as_percentage_not_decimal("Probability: 75%") == 75
    assert extract_probability_from_response_as_percentage_not_decimal("Probability: 150%") == 99
    assert extract_probability_from_response_as_percentage_not_decimal("Probability: 0%") == 1


def test_mcq_probability_parsing_and_normalization():
    text = "Some output\nProbabilities: [20, 30, 50]\nThanks!"
    parsed = extract_option_probabilities_from_response(text, num_options=3)
    assert parsed == [20.0, 30.0, 50.0]

    normed = normalize_probabilities([0, 50, 150])
    assert pytest.approx(sum(normed), rel=1e-6) == 1.0
    assert all(0 <= p <= 1 for p in normed)


def test_mcq_probability_parsing_rejects_wrong_length():
    with pytest.raises(ValueError):
        extract_option_probabilities_from_response("Probabilities: [10, 20]", num_options=3)


def test_numeric_percentile_parsing_and_cleaning():
    raw = """
    Intro line
    Distribution:
    5: 10
    50: 25
    95: 40
    """
    parsed = extract_percentiles_from_response(raw, verbose=False)
    assert parsed == {5: 10.0, 50: 25.0, 95: 40.0}

    # Ensure cleaning removes bullets/dashes and lowercases
    cleaned = clean(" -\u00a0Example  ")
    assert cleaned.strip() == "example"


def test_numeric_enforce_strict_increasing_adds_jitter():
    adjusted = enforce_strict_increasing({10: 1.0, 20: 1.0, 30: 2.0})
    assert adjusted[20] > adjusted[10]
    assert adjusted[30] > adjusted[20]


def test_numeric_cdf_generation_is_monotonic_and_bounded():
    percentiles = {5: 10.0, 50: 25.0, 95: 40.0}
    cdf = generate_continuous_cdf(
        percentiles,
        open_upper_bound=False,
        open_lower_bound=False,
        upper_bound=50.0,
        lower_bound=0.0,
        zero_point=None,
    )
    assert len(cdf) == 201
    assert cdf[0] == 0.0
    assert math.isclose(cdf[-1], 1.0, rel_tol=1e-6)
    assert all(0.0 <= v <= 1.0 for v in cdf)
    assert all(a <= b for a, b in zip(cdf, cdf[1:]))
