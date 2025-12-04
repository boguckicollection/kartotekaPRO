# Card Scanner MVP (Local Network)

## Składniki
- Backend: FastAPI (`/scan`, `/health`)
- Frontend: React + Vite (PWA-ready, kamera przez `input capture`)
- Docker Compose: `api` (8000), `frontend` (5173)
- Baza: SQLite (plik `storage/app.db`)
 - Legacy: stare skrypty przeniesione do `legacy/` (nie wpływają na nową aplikację)

## Uruchomienie
1. W katalogu repo: `docker compose up -d --build`
2. Otwórz: `http://<IP_SERWERA>:5173` z telefonu/komputera w tej samej sieci LAN
3. Backend zdrowie: `http://<IP_SERWERA>:8000/health`

Uwaga o zmianach schematu DB: w SQLite działa lekka migracja (ALTER TABLE) dodająca brakujące kolumny, ale jeśli coś pójdzie nie tak, możesz ręcznie usunąć `storage/app.db` (utrata historii) i uruchomić ponownie, aby utworzyć świeżą bazę.

## Synchronizacja magazynu z Shoper
- Ustaw w `.env` backendu: `SHOPER_BASE_URL` (np. `https://twojsklep.shoparena.pl/webapi/rest`) oraz `SHOPER_ACCESS_TOKEN` (Bearer token API).
- Uruchom synchronizację:
  - `curl -X POST http://<IP_SERWERA>:8000/sync/shoper`
- Efekt: produkty zostaną pobrane z Shoper i zapisane do tabeli `products` w `storage/app.db`.
 - Opcjonalnie ustaw `SHOPER_IMAGE_BASE` (np. `https://twojsklep.shoparena.pl/upload/images`) aby budować URL głównego obrazka z pól `main_image.gfx_id` i `extension`.

## Sesje skanowania i publikacja batchowa
- Rozpocznij sesję: `POST /sessions/start` → zwraca `session_id`.
- Wysyłaj skany z `session_id` (frontend robi to automatycznie po uruchomieniu sesji) — endpoint `/scan?session_id=<id>`.
- Podsumowanie: `GET /sessions/{id}/summary`.
- Publikacja: `POST /sessions/{id}/publish` — tworzy produkty w Shoper dla skanów z wybranym kandydatem. Domyślnie `PUBLISH_DRY_RUN=false` (wykonuje publikację). Ustaw `true` aby testować bez tworzenia produktów.
- Podgląd payloadów przed publikacją: `GET /sessions/{id}/publish/preview` — zwraca listę payloadów (zawiera `scan_id` i `payload`).
- Mapowanie kategorii wg nazwy setu możesz nadpisać przez `SET_CATEGORY_MAP` (JSON), np. `{"Paldean Fates":65,"Surging Sparks":58}`.
- Kod produktu budowany jako `CODE_PREFIX-SETCODE-NUMBER` (domyślnie `PKM-...`).
- Cena z wyceny: `price_pln_final`.
- Obraz: jeśli ustawisz `SHOPER_IMAGE_BASE`, obrazek pod `SHOPER_IMAGE_BASE/{IMAGE_NAME_TEMPLATE}` (dom. `{name}-{number}.jpg`, slugowane). Upewnij się, że plik istnieje pod stałym adresem.

## Uwaga: PWA i HTTPS w LAN
- Service Worker/PWA instalacja wymagają bezpiecznego kontekstu (HTTPS) lub `localhost`.
- W sieci LAN po HTTP serwis zadziała, ale SW może się nie zarejestrować, a „Dodaj do ekranu głównego” może nie być dostępne.
- Rozwiązania:
  - VPN (Tailscale/WireGuard) + domena z ważnym certyfikatem (Let’s Encrypt) → pełne PWA.
  - Lub lokalny reverse-proxy (Caddy) + lokalny certyfikat zaufany na urządzeniach (mkcert/Caddy internal CA).

## Dalsze kroki
- Integracja OpenAI Vision + TCGGO w backendzie w miejscu mocka. [ZROBIONE: Vision + fallback PokemonTCG]
- UI „Top-3 + korekta” + zapis decyzji.
- Publikacja do Shoper (po potwierdzeniu użytkownika).
 - Historia skanów: [ZROBIONE] endpoint `/scans` i prosty widok w UI (lista ostatnich).

## Powiadomienia mobilne (ntfy)
System może wysyłać **bogate powiadomienia mobilne** o nowych zamówieniach przez self-hosted ntfy.

### Szybki start (w 4 krokach):
1. **Ustaw w `.env`:**
   ```bash
   NTFY_ENABLED=true
   NTFY_URL=http://ntfy
   NTFY_TOPIC=kartoteka-orders-TWOJ_UNIKALNY_KLUCZ
   APP_BASE_URL=https://twoja-domena.com  # lub http://IP:5173
   ```

2. **Uruchom ponownie:**
   ```bash
   docker compose restart api
   ```

3. **Zainstaluj aplikację ntfy na telefonie:**
   - Android: [Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy)
   - iOS: [App Store](https://apps.apple.com/us/app/ntfy/id1625396347)

4. **Subskrybuj temat:**
   - W aplikacji dodaj serwer: `http://TWOJE_IP:8080`
   - Subskrybuj temat: `kartoteka-orders-TWOJ_UNIKALNY_KLUCZ`

### Co dostajesz w powiadomieniach:
- **Dane klienta:** imię, email, telefon
- **Podsumowanie zamówienia:** wartość, liczba pozycji
- **Top 3 najdroższe karty** w zamówieniu
- **Klikalne akcje:** „Zobacz szczegóły", „Przyjmij zamówienie"
- **GDPR-compliant:** wszystkie dane pozostają na Twoim serwerze

### Dostęp przez przeglądarkę:
Możesz też przeglądać powiadomienia w przeglądarce: `http://TWOJE_IP:8080`

### Zaawansowane (opcjonalne):
Jeśli chcesz zabezpieczyć ntfy hasłem/tokenem:
```bash
# Utwórz użytkownika w kontenerze ntfy:
docker exec -it kartoteka_ntfy sh -c 'ntfy user add admin'
# (wprowadź hasło interaktywnie)

# Lub wygeneruj token:
docker exec kartoteka_ntfy ntfy token add admin
# Skopiuj token do NTFY_AUTH_TOKEN w .env
```

## Zmienne środowiska
- Backend: zobacz `backend/.env.example`
- Frontend: opcjonalnie `VITE_API_BASE_URL` (domyślnie sam wykryje `:8000` względem hosta)
- `DATABASE_URL` domyślnie `sqlite:////app/storage/app.db`
- `EUR_PLN_RATE` (domyślnie 4.3) — przelicznik EUR→PLN do cen z Cardmarket
- `PRICE_MULTIPLIER` (domyślnie 1.24) — mnożnik końcowy ceny

### Vision (OpenAI)
- Ustaw `OPENAI_API_KEY` w środowisku kontenera `api`. Gdy klucz nie jest ustawiony, backend użyje fallbacku z nazwą na podstawie pliku.

### Provider kart (tymczasowo PokemonTCG)
- Provider preferowany: RapidAPI (tcggopro / pokemon-tcg-api). Ustaw w backend `.env`:
  - `RAPIDAPI_KEY=...`
  - `RAPIDAPI_HOST=pokemon-tcg-api.p.rapidapi.com` (domyślne)
  - `TCGGO_BASE_URL=https://pokemon-tcg-api.p.rapidapi.com`
  - `TCGGO_SEARCH_PATH=/cards`
  - `TCGGO_SEARCH_SEARCH_PATH=/cards/search`
  - `TCGGO_SORT=episode_newest`
  Backend wyśle nagłówki `x-rapidapi-key` i `x-rapidapi-host`.
- Fallback: `https://api.pokemontcg.io/v2/cards` (jeśli RapidAPI nie skonfigurowany). Klucz opcjonalnie w `TCGGO_API_KEY` (`X-Api-Key`).
### Jakie endpointy/parametry są potrzebne
- Szukanie kart: endpoint pozwalający filtrować po `name`, `number` i (jeśli możliwe) `set`/`set_code`. Preferujemy zapytanie typu `q=name:<NAME> number:<NUM> set.id:<SET_CODE>` lub równoważne parametry.
- W RapidAPI możemy używać `GET /cards/search?search=<terms>&sort=episode_newest` gdzie `<terms>` to połączenie pól: `name number set/set_code`.
- Detale karty (opcjonalnie na przyszłość): endpoint do pobrania szczegółów po `id` (obrazy, warianty, przypisania setu).
- Ceny (na etap wyceny): jeśli API zwraca pola cen (np. normal/holofoil/reverse, market/avg), proszę o info gdzie one są w odpowiedzi lub dedykowany endpoint.
### Wycena (założenia aktualne)
- Bierzemy `prices.cardmarket.7d_average` (waluta domyślnie EUR), przeliczamy po `EUR_PLN_RATE`, na końcu mnożymy przez `PRICE_MULTIPLIER` (1.24).
- Jeśli dostępne `graded.psa.psa10`, zapisujemy jako informację dodatkową (bez przeliczenia waluty, o ile API nie wskazuje inaczej).
- `/confirm` zwraca pole `pricing` z wartościami: `cardmarket_currency`, `cardmarket_7d_average`, `eur_pln_rate`, `multiplier`, `price_pln`, `price_pln_final`, `graded_psa10`, `graded_currency`.

Uwaga: jeśli masz inny endpoint/strukturę pól cen na RapidAPI, podeślij przykład (request/response) — dostosuję mapowanie.
