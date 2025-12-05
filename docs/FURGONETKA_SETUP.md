# 🚚 Furgonetka Integration - Setup Guide

Pełna instrukcja konfiguracji integracji z Furgonetka.pl dla automatycznego drukowania listów przewozowych.

## 📋 Spis treści

1. [Wymagania wstępne](#wymagania-wstępne)
2. [Konfiguracja środowiska](#konfiguracja-środowiska)
3. [OAuth - Autoryzacja aplikacji](#oauth---autoryzacja-aplikacji)
4. [Mapowanie kurierów](#mapowanie-kurierów)
5. [Pierwsze użycie](#pierwsze-użycie)
6. [Drukowanie etykiet](#drukowanie-etykiet)
7. [Rozwiązywanie problemów](#rozwiązywanie-problemów)

---

## Wymagania wstępne

✅ **Co musisz mieć:**
1. Konto w serwisie **Furgonetka.pl** (sandbox lub produkcyjne)
2. Połączone konto Furgonetka ze sklepem Shoper
3. Client ID i Client Secret z panelu Furgonetka
4. Dane adresowe magazynu (nadawca)
5. Drukarka (termiczna lub laserowa PDF)

---

## Konfiguracja środowiska

### Krok 1: Dodaj zmienne do `.env`

Skopiuj poniższy szablon i uzupełnij danymi:

```bash
# ===== FURGONETKA API =====
# Sandbox (testowe środowisko)
FURGONETKA_CLIENT_ID=twoj_sandbox_client_id
FURGONETKA_CLIENT_SECRET=twoj_sandbox_secret
FURGONETKA_BASE_URL=https://sandbox.furgonetka.pl
FURGONETKA_SANDBOX_MODE=true
FURGONETKA_REDIRECT_URI=http://localhost:8000/furgonetka/oauth/callback

# Mapowanie metod dostawy (Shoper ID -> Furgonetka kod)
FURGONETKA_SERVICE_MAP={"15": "inpost", "16": "dpd_pickup", "17": "orlen", "18": "dhl"}

# Dane nadawcy (magazyn)
FURGONETKA_SENDER_NAME=Twój Sklep Pokemon
FURGONETKA_SENDER_STREET=Magazynowa 7
FURGONETKA_SENDER_CITY=Warszawa
FURGONETKA_SENDER_POSTCODE=00-123
FURGONETKA_SENDER_PHONE=123456789
FURGONETKA_SENDER_EMAIL=sklep@twojadomena.pl
```

### Krok 2: Uzyskaj Client ID i Secret

**Sandbox (testy):**
1. Zarejestruj się na https://sandbox.furgonetka.pl
2. Przejdź do **Ustawienia → Integracje → API**
3. Utwórz nową aplikację
4. Skopiuj Client ID i Secret

**Produkcja:**
1. Zaloguj się na https://furgonetka.pl
2. Przejdź do **Ustawienia → Integracje → API**
3. Utwórz aplikację produkcyjną
4. Zmień w `.env`:
   - `FURGONETKA_BASE_URL=https://api.furgonetka.pl`
   - `FURGONETKA_SANDBOX_MODE=false`

---

## OAuth - Autoryzacja aplikacji

### Krok 1: Uruchom aplikację

```bash
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

### Krok 2: Autoryzuj aplikację

1. **Otwórz w przeglądarce:**
   ```
   http://localhost:8000/furgonetka/oauth/authorize
   ```

2. **Skopiuj URL** z odpowiedzi JSON:
   ```json
   {
     "authorization_url": "https://sandbox.furgonetka.pl/oauth/authorize?..."
   }
   ```

3. **Wklej URL w przeglądarce** → zaloguj się do Furgonetka → **Zatwierdź**

4. **Zostaniesz przekierowany** na:
   ```
   http://localhost:8000/furgonetka/oauth/callback?code=ABC123...
   ```

5. **Zobacz potwierdzenie**:
   ```json
   {
     "message": "✅ Authorization successful! You can now create shipments.",
     "expires_in_days": 30
   }
   ```

✅ **Gotowe!** Token jest zapisany w bazie danych i odświeża się automatycznie.

---

## Mapowanie kurierów

### Jak znaleźć ID metody dostawy w Shoperze?

1. **Zło\u017C testowe zamówienie** ze wszystkimi metodami dostawy
2. **Wywołaj API**:
   ```bash
   curl http://localhost:8000/api/orders?limit=1
   ```
3. **Znajdź pole** `delivery.id` lub `delivery_method.id`
4. **Zmapuj do kodów Furgonetka:**

| Shoper ID | Furgonetka kod | Opis |
|-----------|----------------|------|
| 15 | `inpost` | InPost Paczkomaty |
| 16 | `dpd_pickup` | DPD Pickup |
| 17 | `orlen` | Orlen Paczka |
| 18 | `dhl` | DHL Kurier |
| 19 | `inpostkurier` | InPost Kurier |
| 20 | `poczta` | Poczta Polska |

### Gdzie Shoper przechowuje ID Paczkomatu?

**⚠️ KRYTYCZNE**: Musisz sprawdzić to ręcznie!

1. Złóż testowe zamówienie z Paczkomatem (wybierz np. WAW22A)
2. Wywołaj:
   ```bash
   curl http://localhost:8000/api/orders/{order_id}
   ```
3. Szukaj "WAW22A" w polach:
   - `delivery_address.additional_info`
   - `delivery_address.address2`
   - `order.comment`
   - `order.notes`

4. **Zaktualizuj** `backend/app/furgonetka_mapper.py` funkcję `_extract_parcel_locker_id()` jeśli potrzeba.

---

## Pierwsze użycie

### Test 1: Sprawdź status

```bash
curl http://localhost:8000/furgonetka/status
```

**Oczekiwana odpowiedź:**
```json
{
  "configured": true,
  "authorized": true,
  "token_expires_in_days": 30,
  "service_mapping_configured": true,
  "ready": true
}
```

### Test 2: Utwórz przesyłkę

1. **W frontend (Orders.tsx):** Kliknij na zamówienie
2. **Kliknij "📦 Utwórz list przewozowy"**
3. **Czekaj na potwierdzenie:** "✅ Shipment created successfully!"
4. **Kliknij "🖨️ Pobierz etykietę PDF"**

**Lub przez API:**
```bash
curl -X POST http://localhost:8000/furgonetka/shipments \
  -H "Content-Type: application/json" \
  -d '{"order_id": 12345}'
```

---

## Drukowanie etykiet

### Opcja A: PDF w przeglądarce (zalecane na start)

1. Kliknij "Pobierz etykietę"
2. PDF otwiera się w nowej karcie
3. **Ctrl+P** → Wybierz drukarkę → **Drukuj**

**Format etykiety:** A4 (4 etykiety na stronie) lub 10x15 cm (pojedyncza)

### Opcja B: Drukarka termiczna (ZPL)

**Jeśli masz drukarkę Zebra/TSC:**

1. Zmień parametr w URL:
   ```
   /furgonetka/shipments/{id}/label?format=zpl
   ```
2. Plik ZPL możesz:
   - Wysłać bezpośrednio na drukarkę (raw printing)
   - Użyć Furgonetka Printing Assistant (auto-print w tle)

### Opcja C: Printing Assistant (pełna automatyzacja)

1. **Pobierz aplikację:** https://furgonetka.pl/furgonetka-printing-assistant
2. **Zainstaluj** na komputerze z drukarką
3. **Skonfiguruj:** Połącz z kontem Furgonetka
4. **Od teraz:** Aplikacja automatycznie wykrywa nowe etykiety i drukuje!

---

## Rozwiązywanie problemów

### Błąd: "Authorization error"

**Przyczyna:** Token wygasł  
**Rozwiązanie:** Ponownie autoryzuj aplikację (Krok OAuth)

---

### Błąd: "Shipment validation failed"

**Typowe przyczyny:**

1. **Błędny kod pocztowy** → Sprawdź format XX-XXX
   ```json
   {"receiver.postcode": ["Kod pocztowy jest nieprawidłowy"]}
   ```

2. **Brak ID Paczkomatu** dla InPost
   ```json
   {"receiver.point": ["Pole jest wymagane dla tego kuriera"]}
   ```
   **Fix:** Zobacz sekcję "Mapowanie kurierów"

3. **Przekroczone wymiary** paczki dla Paczkomatu
   ```json
   {"parcels.weight": ["Maksymalna waga to 25 kg"]}
   ```

---

### Błąd: "Unknown delivery method ID: 42"

**Przyczyna:** Brak mapowania w `FURGONETKA_SERVICE_MAP`  
**Rozwiązanie:**
1. Sprawdź ID metody: `curl http://localhost:8000/api/orders/{id}`
2. Dodaj do `.env`:
   ```bash
   FURGONETKA_SERVICE_MAP={"15": "inpost", "42": "dpd"}
   ```
3. **Restart backendu**

---

### Błąd 402: "Payment Required"

**Przyczyna:** Brak środków na koncie Furgonetka (prepaid)  
**Rozwiązanie:** Doładuj konto w panelu Furgonetka

---

### Przesyłka utworzona, ale brak ID Paczkomatu

**Diagnoza:**
```bash
# Sprawdź surowe dane zamówienia
curl http://localhost:8000/api/orders/12345 | jq .
```

**Jeśli ID Paczkomatu nie ma w odpowiedzi:**
- Sprawdź integrację Shoper z InPost
- Upewnij się, że klient wybrał Paczkomat (a nie "dowolny")
- Może trzeba zaimportować dane z Furgonetka API (see dokumentacja)

---

## Produkcja - Checklist

Przed wdrożeniem na produkcję:

- [ ] Zmień `FURGONETKA_BASE_URL` na `https://api.furgonetka.pl`
- [ ] Zmień `FURGONETKA_SANDBOX_MODE=false`
- [ ] Użyj **produkcyjnych** Client ID/Secret
- [ ] **Ponownie autoryzuj** aplikację (OAuth flow)
- [ ] Doładuj konto Furgonetka (prepaid)
- [ ] Przetestuj wszystkie metody dostawy
- [ ] Skonfiguruj Printing Assistant (jeśli używasz)
- [ ] Utwórz pierwszą prawdziwą przesyłkę (sprawdź czy etykieta działa)

---

## API Endpoints - Referenc ja

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/furgonetka/status` | GET | Status integracji i tokena |
| `/furgonetka/oauth/authorize` | GET | Generuj URL autoryzacji |
| `/furgonetka/oauth/callback` | GET | Callback OAuth (auto) |
| `/furgonetka/shipments` | POST | Utwórz przesyłkę |
| `/furgonetka/shipments` | GET | Lista przesyłek |
| `/furgonetka/shipments/{id}/label` | GET | Pobierz etykietę |

---

## Potrzebujesz pomocy?

1. **Logi backendu:** `docker-compose logs -f backend`
2. **Logi Furgonetka API:** Zapisywane w `request_payload` / `response_payload` w bazie
3. **Dokumentacja Furgonetka:** https://furgonetka.pl/api
4. **GitHub Issues:** Zgłoś problem w repozytorium

---

**Status:** ✅ Gotowe do użycia w Sandbox  
**Ostatnia aktualizacja:** 2025-12-02
