from typing import List, Tuple

#Point = Tuple[float, float]

def dominates(a: Tuple[float, ...], b: Tuple[float, ...]) -> bool:
    "True if a dominates b in the Pareto approach (minimization, any number of criteria)."
    strictly_better = False
    for a_c, b_c in zip(a, b):
        if a_c > b_c:
            return False
        if a_c < b_c:
            strictly_better = True
    return strictly_better



def naive_owd_without_filtration(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    X = list(points)
    P: List[Tuple[float, float]] = []
    i = 0
    matches = 0

    while i < len(X):
        Y = X[i]
        fl = 0

        j = i + 1
        while j < len(X):
            X_j = X[j]
            matches += 1
            if dominates(Y, X_j):
                # Y dominates X(j) -> remove X(j)
                X.pop(j)
            elif dominates(X_j, Y):
                matches += 1
                # X_j dominates Y --> change Y for new candidate
                if Y in X:
                    Y_idx = X.index(Y)
                    X.pop(Y_idx)
                    # When reducing the size of table of one element (on the left side of "j" indexer), the indexer "j" has to be based.  
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
    return P, matches


if __name__ == "__main__":
    smoke_test = [
        (5, 5), (3, 6), (4, 4), (5, 3), (3, 3),
        (1, 8), (3, 4), (4, 5), (3, 10), (6, 6),
        (4, 1), (3, 5)
    ]

    wynik, porownania = naive_owd_without_filtration(smoke_test)
    print(f"Zbiór niezdominowany: {wynik}\nLiczba Porównania: {porownania}")
