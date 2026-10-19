# optymalizacja-wielokryterialna-dyskretna

## Aplikacja do eksperymentów

```bash
python app.py
```

Wymaga: `numpy`, `matplotlib` (GUI w Tkinter).

- wybór algorytmu (`ALGORITHMS` w `app.py` – nowy algorytm wystarczy tam dopisać jako `(moduł, nazwa_funkcji)`; funkcja przyjmuje listę punktów, minimalizuje wszystkie kryteria, zwraca `(P, liczba_porownan)` i porównuje punkty przez funkcję `dominates(a, b)` z poziomu modułu – aplikacja ją opakowuje, żeby zaznaczyć punkty porównywane),
- automatyczna kontrola poprawności: każdy wynik jest sprawdzany z definicją dominacji Pareto (kolumna „poprawny” w historii),
- sekcja „Kryteria”: dla każdego kryterium osobno nazwa (domyślnie `f1`, `f2`, ...; Enter zatwierdza) i kierunek `min`/`max`, plus przyciski „Wszystkie min/max”; kryteria maksymalizowane są negowane przed wywołaniem algorytmu,
- generowanie danych (`data_generator.py`): rozkład, średnia, odchylenie (wspólne lub osobne dla kryteriów, np. `10; 20`), N, k, seed, zaokrąglanie,
- nazwę kryterium można też zmienić prawym klikiem w nagłówek tabeli danych; nazwy trafiają na osie wykresu i do CSV,
- przeglądanie danych („Przeglądaj dane”): tabela punktów ze statusem i liczbą porównań, sortowanie po kolumnach, filtr (niezdominowane / zdominowane / porównywane), zaznaczone wiersze są wyróżnione na wykresie,
- wykres 2D (rzut na wybrane kryteria) lub 3D z warstwami: zbiór punktów, zdominowane, porównywane, niezdominowane, front Pareto, punkt idealny,
- zapis do CSV: wynik (każdy punkt ze statusem i liczbą porównań; metadane w liniach `#` – `pd.read_csv(path, comment="#")`) oraz historia wszystkich uruchomień.
- czas w wynikach mierzony jest w osobnym przebiegu bez zliczania porównań poszczególnych punktów, żeby to śledzenie nie zawyżało czasu.
