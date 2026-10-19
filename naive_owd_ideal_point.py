from typing import List, Tuple
Point = List[float, float]


def dominates(p1: Point, p2: Point) -> bool:
    """
    Minimalizing points variant.
    Return True if p1 dominates p2.
    """
    return (p1[0] <= p2[0] and p1[1] <= p2[1]) and (p1[0] < p2[0] or p1[1] < p2[1])



def owd_ideal_point(dataset: List[Point]) -> Tuple[List[Point], int]:
    P: List[Point] = []
    comparison_counter = 0

    if not dataset:
        return P, comparison_counter

    k = len(dataset[0])
    xmin = tuple(min(point[c] for point in dataset) for c in range(k))
    print(f"Punkt idealny xmin: {xmin}")

    def dist_sq(pt: Point) -> float:
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
