# optymalizacja-wielokryterialna-dyskretna

## Aplikacja do eksperymentów

Aplikacja webowa w Streamlit:

```bash
conda env create -f environment.yml   # albo: pip install -r requirements.txt
conda activate owd_env
streamlit run app.py
```

Struktura: `app.py` (menu stron), `app_pages/single_experiment.py` (strona „Pojedynczy eksperyment”), `app_pages/experiment_results.py` (strona „Wyniki eksperymentów”), `experiment.py` (uruchamianie algorytmów, kontrola poprawności, CSV), `data_generator.py` (generowanie danych), `run_experiments.py` (seria eksperymentów), `naive_owd_*.py` (algorytmy).

- wybór algorytmu (`ALGORITHMS` w `experiment.py` – nowy algorytm wystarczy tam dopisać jako `(moduł, nazwa_funkcji)`; funkcja przyjmuje listę punktów, minimalizuje wszystkie kryteria, zwraca `(P, liczba_porownan)` i porównuje punkty przez funkcję `dominates(a, b)` z poziomu modułu – aplikacja ją opakowuje, żeby zaznaczyć punkty porównywane),
- generowanie danych: rozkład, N, k, seed (🎲 losuje), zaokrąglanie,
- tabela „Kryteria”: dla każdego kryterium osobno nazwa (domyślnie `f1`, `f2`, ...), kierunek `min`/`max`, średnia i odchylenie; przyciski „Wszystkie min/max”; kryteria maksymalizowane są negowane przed wywołaniem algorytmu,
- „Uruchom wszystkie algorytmy” liczy wszystkie algorytmy na tych samych danych – wybór algorytmu w panelu przełącza wtedy wyświetlany wynik,
- automatyczna kontrola poprawności: każdy wynik jest sprawdzany z definicją dominacji Pareto,
- interaktywny wykres (Plotly) 2D lub 3D z warstwami: zbiór punktów, zdominowane, porównywane, niezdominowane, front Pareto, punkt idealny; po najechaniu widać id i wartości punktu,
- tabela danych ze statusem i liczbą porównań, filtrem i sortowaniem; zaznaczone wiersze są wyróżnione na wykresie,
- pobieranie CSV: wynik (każdy punkt ze statusem i liczbą porównań; metadane w liniach `#` – `pd.read_csv(path, comment="#")`) oraz historia wszystkich uruchomień,
- czas w wynikach mierzony jest w osobnym przebiegu bez zliczania porównań poszczególnych punktów, żeby to śledzenie nie zawyżało czasu.

## Seria eksperymentów (skrypt)

Eksperymenty na wielu losowych zbiorach uruchamia `run_experiments.py`. Parametry są w pliku TOML – nowy eksperyment to kopia `experiments/eksperyment_B.toml` ze zmienionymi wartościami (rozmiary N i liczba powtórzeń K, listy liczby kryteriów, algorytmy, rozkład, kierunki, seed).

```bash
python run_experiments.py experiments/eksperyment_B.toml --quick   # szybki test: 2 powtórzenia na rozmiar
python run_experiments.py experiments/eksperyment_B.toml           # pełny eksperyment
python run_experiments.py --resume results/<katalog>               # dokończenie przerwanego (Ctrl+C)
python run_experiments.py --summarize results/<katalog>            # ponowne przeliczenie podsumowania
```

- każdy zbiór danych ma seed wyliczony z `base_seed`, N, k i numeru powtórzenia – ten sam plik konfiguracji zawsze daje te same dane, a wszystkie algorytmy liczą na identycznych zbiorach,
- wyniki trafiają do `results/<nazwa>_<data>/`: `raw.csv` (każdy zbiór × algorytm, zapisywany na bieżąco), `summary.csv` (średnia, odchylenie, min, max dla N, k, algorytmu), `comparisons.csv` i `time_ms.csv` (tabele średnich do sprawozdania), `report.html` (wykresy),
- `--workers N` liczy kilka zbiorów równolegle – liczba porównań się nie zmienia, ale czasy są wtedy mniej wiarygodne.

### Strona „Wyniki eksperymentów”

Przegląda wyniki `run_experiments.py`: wybór katalogu z `results/` (albo wczytanie pliku `raw.csv`), filtry algorytmów, N i k oraz opcja pominięcia niepoprawnych wyników. Zakładki:

- **Wykresy** – liczba porównań, czas lub |P| w zależności od k albo N (średnia ± odchylenie albo wykres pudełkowy, skala logarytmiczna),
- **Tabele** – wybrana statystyka (średnia, odchylenie, mediana, min, max) dla N, k i algorytmu, także jako iloraz względem wybranego algorytmu; pobieranie CSV,
- **Liczba niezdominowanych** – |P| (albo |P|/N) na zbiór danych, liczone z poprawnych wyników,
- **Poprawność** – odsetek wyników zgodnych z definicją dominacji Pareto,
- **Dane surowe** – przefiltrowany `raw.csv`.

Strona czyta `raw.csv` na bieżąco – przycisk „Odśwież” pokazuje postęp trwającego eksperymentu.
