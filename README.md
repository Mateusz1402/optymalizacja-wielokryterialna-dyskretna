# optymalizacja-wielokryterialna-dyskretna

## Aplikacja do eksperymentów

Aplikacja webowa w Streamlit:

```bash
conda env create -f environment.yml   # albo: pip install -r requirements.txt
conda activate owd_env
streamlit run app.py
```

Struktura: `app.py` (interfejs), `experiment.py` (uruchamianie algorytmów, kontrola poprawności, CSV), `data_generator.py` (generowanie danych), `naive_owd_*.py` (algorytmy).

- wybór algorytmu (`ALGORITHMS` w `experiment.py` – nowy algorytm wystarczy tam dopisać jako `(moduł, nazwa_funkcji)`; funkcja przyjmuje listę punktów, minimalizuje wszystkie kryteria, zwraca `(P, liczba_porownan)` i porównuje punkty przez funkcję `dominates(a, b)` z poziomu modułu – aplikacja ją opakowuje, żeby zaznaczyć punkty porównywane),
- generowanie danych: rozkład, N, k, seed (🎲 losuje), zaokrąglanie,
- tabela „Kryteria”: dla każdego kryterium osobno nazwa (domyślnie `f1`, `f2`, ...), kierunek `min`/`max`, średnia i odchylenie; przyciski „Wszystkie min/max”; kryteria maksymalizowane są negowane przed wywołaniem algorytmu,
- „Uruchom wszystkie algorytmy” liczy wszystkie algorytmy na tych samych danych – wybór algorytmu w panelu przełącza wtedy wyświetlany wynik,
- automatyczna kontrola poprawności: każdy wynik jest sprawdzany z definicją dominacji Pareto,
- interaktywny wykres (Plotly) 2D lub 3D z warstwami: zbiór punktów, zdominowane, porównywane, niezdominowane, front Pareto, punkt idealny; po najechaniu widać id i wartości punktu,
- tabela danych ze statusem i liczbą porównań, filtrem i sortowaniem; zaznaczone wiersze są wyróżnione na wykresie,
- pobieranie CSV: wynik (każdy punkt ze statusem i liczbą porównań; metadane w liniach `#` – `pd.read_csv(path, comment="#")`) oraz historia wszystkich uruchomień,
- czas w wynikach mierzony jest w osobnym przebiegu bez zliczania porównań poszczególnych punktów, żeby to śledzenie nie zawyżało czasu.
