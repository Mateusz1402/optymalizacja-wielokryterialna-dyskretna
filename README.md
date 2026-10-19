# optymalizacja-wielokryterialna-dyskretna

## Aplikacja do eksperymentów

```bash
python app.py
```

Wymaga: `numpy`, `matplotlib` (GUI w Tkinter).

- wybór algorytmu (`ALGORITHMS` w `app.py` – nowy algorytm wystarczy tam dopisać; musi przyjmować `(X, compared=None)`, minimalizować wszystkie kryteria i zwracać `(P, liczba_porownan)`),
- kierunek optymalizacji: `min`, `max` albo osobno dla kryteriów, np. `min; max` (kryteria maksymalizowane są negowane przed wywołaniem algorytmu),
- generowanie danych (`data_generator.py`): rozkład, średnia, odchylenie (wspólne lub osobne dla kryteriów, np. `10; 20`), N, k, seed, zaokrąglanie,
- nazwy kryteriów: domyślnie `f1; f2; ...`, można je zmienić w polu „Nazwy kryteriów” (rozdzielone `;`, Enter zatwierdza) albo prawym klikiem w nagłówek tabeli danych; nazwy trafiają na osie wykresu i do CSV,
- przeglądanie danych („Przeglądaj dane”): tabela punktów ze statusem i liczbą porównań, sortowanie po kolumnach, filtr (niezdominowane / zdominowane / porównywane), zaznaczone wiersze są wyróżnione na wykresie,
- wykres 2D (rzut na wybrane kryteria) lub 3D z warstwami: zbiór punktów, zdominowane, porównywane, niezdominowane, front Pareto, punkt idealny,
- zapis do CSV: wynik (każdy punkt ze statusem i liczbą porównań; metadane w liniach `#` – `pd.read_csv(path, comment="#")`) oraz historia wszystkich uruchomień.
- czas w wynikach mierzony jest w osobnym przebiegu bez zliczania porównań poszczególnych punktów, żeby to śledzenie nie zawyżało czasu.
