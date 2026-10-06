"""Points for one prediction. Pure functions, so the rules are easy to test."""

EXACT_SCORE = 3
CORRECT_OUTCOME = 1


def outcome(home: int, away: int) -> int:
    """1 for a home win, 0 for a draw, -1 for an away win."""
    return (home > away) - (home < away)


def points(predicted: tuple[int, int], actual: tuple[int, int]) -> int:
    if predicted == actual:
        return EXACT_SCORE
    if outcome(*predicted) == outcome(*actual):
        return CORRECT_OUTCOME
    return 0
