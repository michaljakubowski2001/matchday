import pytest

from matchday.scoring import points


@pytest.mark.parametrize(
    ("predicted", "actual", "expected"),
    [
        ((2, 1), (2, 1), 3),  # exact score
        ((0, 0), (0, 0), 3),  # exact draw
        ((3, 1), (1, 0), 1),  # right winner
        ((1, 1), (2, 2), 1),  # right draw
        ((0, 2), (1, 3), 1),  # right away win
        ((2, 1), (1, 2), 0),  # wrong winner
        ((1, 1), (1, 0), 0),  # predicted draw, home won
    ],
)
def test_points(predicted, actual, expected):
    assert points(predicted, actual) == expected
