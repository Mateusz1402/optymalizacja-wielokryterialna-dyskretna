def porownaj(y, x):
    # Porównanie dwóch punktów w jednym przebiegu po współrzędnych:
    #  1 -> y dominuje x (wszystkie y_i <= x_i i co najmniej jedna ostro mniejsza)
    # -1 -> x dominuje y
    #  0 -> punkty nieporównywalne lub równe
    y_lepszy = x_lepszy = False
    for vy, vx in zip(y, x):
        if vy < vx:
            y_lepszy = True
        elif vx < vy:
            x_lepszy = True
        if y_lepszy and x_lepszy:
            return 0
    if y_lepszy:
        return 1
    if x_lepszy:
        return -1
    return 0

def algorytm_z_filtracja(X, compared=None):
    # compared: optional Counter - counts how many comparisons each point took part in
    P = [] # zbiór rozwiązań niezdominowanych
    X_kandydaci = list(X)
    liczba_porownan = 0
    
    while X_kandydaci:
        i_Y = 0 # indeks kandydata na punkt niezdominowany
        j = 1
        
        while j < len(X_kandydaci):
            liczba_porownan += 1
            if compared is not None:
                compared[X_kandydaci[i_Y]] += 1
                compared[X_kandydaci[j]] += 1
            wynik = porownaj(X_kandydaci[i_Y], X_kandydaci[j])
            if wynik == 1:
                X_kandydaci.pop(j)
            elif wynik == -1:
                # X(j) dominuje Y -> usuwamy Y, nowym kandydatem jest X(j) (po usunięciu na pozycji j - 1)
                X_kandydaci.pop(i_Y)
                i_Y = j - 1
            else:
                j += 1
                    
        Y = X_kandydaci[i_Y]
        P.append(Y)
        
        # Filtracja punktów zdominowanych przez Y.
        # Punkty za Y zostały już porównane z Y w pętli powyżej (zdominowane usunięto),
        # więc wystarczy sprawdzić tylko punkty leżące przed Y.
        nowi_kandydaci = []
        for x in X_kandydaci[:i_Y]:
            liczba_porownan += 1
            if compared is not None:
                compared[Y] += 1
                compared[x] += 1
            if porownaj(Y, x) != 1:
                nowi_kandydaci.append(x)
        X_kandydaci = nowi_kandydaci + X_kandydaci[i_Y + 1:]
            
    return P, liczba_porownan

if __name__ == "__main__":
    X_input = [
        (5,5), (3,6), (4,4), (5,3), (3,3), (1,8), (3,4), (4,5), (3,10), (6,6), (4, 1), (3, 5)
    ]
    
    punkty_niezdominowane, porownania = algorytm_z_filtracja(X_input)
    print(f"Zbiór rozwiązań niezdominowanych: {punkty_niezdominowane}")
    print(f"Liczba wykonanych porównań punktów: {porownania}")
