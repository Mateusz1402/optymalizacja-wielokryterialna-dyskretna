from typing import List, Tuple
Point = List[float, float]


def dominates(p1: Point, p2: Point) -> bool:
    """
    Minimalizing points variant.
    Return True if p1 dominates p2.
    """
    return (p1[0] <= p2[0] and p1[1] <= p2[1]) and (p1[0] < p2[0] or p1[1] < p2[1])



def owd_z_filtracja(dataset: List[Point]) -> Tuple[List[Point], int]:
    X = list(dataset)
    P: List[Point] = []
    comparison_counter = 0

    while len(X) > 0:
        Y = X[0]
        j = 1

        while j < len(X):
            comparison_counter += 1
            if dominates(Y, X[j]):
                X.pop(j)
            else:
                comparison_counter += 1
                if dominates(X[j], Y):
                    X.remove(Y)
                    Y = X[j - 1]
                else:
                    j += 1

        if Y not in P:
            P.append(Y)

        filtered_X = []
        for point in X:
            if point != Y:
                comparison_counter += 1
                if not dominates(Y, point):
                    filtered_X.append(point)
        X = filtered_X

        if len(X) == 1:
            if X[0] not in P:
                P.append(X[0])
            break

    return P, comparison_counter