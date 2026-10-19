def dominates(y, x):
    # Weryfikacja dominacji Pareto w jednym przebiegu po współrzędnych
    ostro_mniejszy = False
    for vy, vx in zip(y, x):
        if vy > vx:
            return False
        if vy < vx:
            ostro_mniejszy = True
    return ostro_mniejszy

def algorytm_punkt_idealny(X, compared=None):
    # compared: optional Counter - counts how many comparisons each point took part in
    if not X:
        return [], 0

    # Ilość kryteriów
    k = len(X[0])
    
    # Wyznaczenie punktu idealnego xmin
    xmin = [min(x[i] for x in X) for i in range(k)]
    
    # Obliczenie kwadratów odległości i sortowanie względem odległości od punktu idealnego
    kandydaci = sorted(
        ((sum((x[i] - xmin[i]) ** 2 for i in range(k)), x) for x in X),
        key=lambda para: para[0],
    )
    
    P = []
    liczba_porownan = 0
    
    while kandydaci:
        d_Y, Y = kandydaci[0]
        P.append(Y)
        
        nowi_kandydaci = []
        # Filtracja punktów zdominowanych przez Y z inkrementacją licznika.
        # Jeśli Y dominuje x, to d(Y) < d(x) ostro, więc punktów o tej samej
        # odległości co Y nie trzeba porównywać.
        for d_x, x in kandydaci[1:]:
            if d_x > d_Y:
                liczba_porownan += 1
                if compared is not None:
                    compared[Y] += 1
                    compared[x] += 1
                if dominates(Y, x):
                    continue
            nowi_kandydaci.append((d_x, x))
                
        kandydaci = nowi_kandydaci
        
    return P, liczba_porownan

if __name__ == "__main__":
    X_input = [
            (5,5), (3,6), (4,4), (5,3), (3,3), (1,8), (3,4), (4,5), (3,10), (6,6), (4, 1), (3, 5)
        ]
    punkty_niezdominowane, porownania = algorytm_punkt_idealny(X_input)
    print(f"Zbiór rozwiązań niezdominowanych: {punkty_niezdominowane}")
    print(f"Liczba wykonanych porównań punktów: {porownania}")
