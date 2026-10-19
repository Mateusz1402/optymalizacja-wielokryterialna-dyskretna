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



def owd_z_filtracja(dataset: List[Tuple[float, float]]) -> Tuple[List[Tuple[float, float]], int]:
    X = list(dataset)
    P: List[Tuple[float, float]] = []
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