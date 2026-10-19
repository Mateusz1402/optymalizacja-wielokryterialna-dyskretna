from typing import List, Tuple
#Point = List[float, float]


def dominates(p1: Tuple[float, ...], p2: Tuple[float, ...]) -> bool:
    """
    Minimalizing points variant, any number of criteria.
    Return True if p1 dominates p2: p1 is not worse in every criterion and better in at least one.
    """
    strictly_better = False
    for a, b in zip(p1, p2):
        if a > b:
            return False
        if a < b:
            strictly_better = True
    return strictly_better



def owd_ideal_point(dataset: List[Tuple[float, float]]) -> Tuple[List[Tuple[float, float]], int]:
    P: List[Tuple[float, float]] = []
    comparison_counter = 0

    if not dataset:
        return P, comparison_counter

    k = len(dataset[0])
    xmin = tuple(min(point[c] for point in dataset) for c in range(k))
    print(f"Punkt idealny xmin: {xmin}")

    def dist_sq(pt: Tuple[float, float]) -> float:
        return sum((pt[c] - xmin[c]) ** 2 for c in range(k))

    sorted_X = sorted(dataset, key=dist_sq)

    surviving_X = list(sorted_X)

    while len(surviving_X) > 0:
        current = surviving_X.pop(0)
        P.append(current)

        filtered_X = []
        for candidate in surviving_X:
            comparison_counter += 1
            if not dominates(current, candidate):
                filtered_X.append(candidate)
        surviving_X = filtered_X

    return P, comparison_counter
