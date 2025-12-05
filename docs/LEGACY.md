# Legacy code

- Pliki i skrypty ze starej wersji zostały przeniesione do katalogu `legacy/` (np. `legacy/migrate_locations_from_csv.py`).
- Nowa aplikacja działa w katalogach `backend/` (API) i `frontend/` (UI) oraz korzysta z `docker-compose.yml`.
- Środowisko i sekrety dla nowej aplikacji trzymamy w `.env` (wg `.env.example` w katalogu głównym) oraz `backend/.env.example`.
- Stara logika/biblioteki (np. `kartoteka.*`) nie są ładowane przez nowy backend — brak konfliktów w zależnościach.

## Migracja danych
- Magazyn z CSV można zaimportować komendą:
  - `docker compose exec api python -m app.import_inventory --csv /app/storage/magazyn.csv`
- Dane trafią do tabeli `inventory` w `storage/app.db`.

## Sprzątanie
- Jeśli nie planujesz wracać do starych skryptów, możesz usunąć katalog `legacy/` po potwierdzeniu, że wszystkie dane zostały przeniesione.
- Plik `magazyn.csv` jest montowany tylko read‑only do kontenera (nie modyfikujemy go).

