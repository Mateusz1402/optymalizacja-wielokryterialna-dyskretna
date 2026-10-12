def dominates(y, x):
    return all(vy <= vx for vy, vx in zip(y, x)) and any(vy < vx for vy, vx in zip(y, x))

def algorytm_z_filtracja(X):
    P = [] # zbiór rozwiązań niezdominowanych
    X_kandydaci = list(X)
    liczba_porownan = 0
    
    while X_kandydaci:
        Y = X_kandydaci[0]
        j = 1
        
        while j < len(X_kandydaci):
            liczba_porownan += 1
            if dominates(Y, X_kandydaci[j]):
                X_kandydaci.pop(j)
            else:
                liczba_porownan += 1
                if dominates(X_kandydaci[j], Y):
                    X_kandydaci.remove(Y)
                    Y = X_kandydaci[j - 1]
                else:
                    j += 1
                    
        P.append(Y)
        
        nowi_kandydaci = []
        # Filtracja punktów zdominowanych przez Y
        for x in X_kandydaci:
            if x != Y:
                liczba_porownan += 1
                if not dominates(Y, x):
                    nowi_kandydaci.append(x)
        X_kandydaci = nowi_kandydaci
        
        if len(X_kandydaci) == 1:
            P.append(X_kandydaci[0])
            break
            
    return P, liczba_porownan

if __name__ == "__main__":
    X_input = [
        (5,5), (3,6), (4,4), (5,3), (3,3), (1,8), (3,4), (4,5), (3,10), (6,6), (4, 1), (3, 5)
    ]
    
    punkty_niezdominowane, porownania = algorytm_z_filtracja(X_input)
    print(f"Zbiór rozwiązań niezdominowanych: {punkty_niezdominowane}")
    print(f"Liczba wykonanych porównań punktów: {porownania}")