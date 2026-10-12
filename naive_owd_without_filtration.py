from typing import List, Tuple

Point = Tuple[float, float]

def dominates(a: Point, b: Point) -> bool:
    "True if a dominates b in the Pareto approach."
    if ((a[0] <= b[0]) or (a[0] < b[0])) and ((a[1] <= b[1]) or (a[1] < b[1])):
        return True



def naive_owd_without_filtration(points: List[Point]) -> List[Point]:
    X = list(points)
    P: List[Point] = []
    i = 0

    while i < len(X):
        Y = X[i]
        fl = 0

        j = i + 1
        while j < len(X):
            X_j = X[j]
            if dominates(Y, X_j):
                # Y dominates X(j) -> remove X(j)
                X.pop(j)
            elif dominates(X_j, Y):
                # X_j dominates Y --> change Y for new candidate
                if Y in X:
                    Y_idx = X.index(Y)
                    X.pop(Y_idx)

                    if Y_idx < j:
                        j -= 1
                Y = X_j
                fl = 1
                j += 1
            else:
                j += 1

        # Add Y into non-dominated list
        if Y not in P:
            P.append(Y)

        # If fl=0 (inside internal loop the Y remains the same) -> remove Y from the list
        if fl == 0:
            if Y in X:
                X.remove(Y)
        else:
            i += 1
    return P



smoke_test = [
        (5, 5), (3, 6), (4, 4), (5, 3), (3, 3),
        (1, 8), (3, 4), (4, 5), (3, 10), (6, 6),
        (4, 1), (3, 5)
    ]

wynik = naive_owd_without_filtration(smoke_test)
print(wynik)

