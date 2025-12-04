Instrukcja: uruchomienie podglądu kamery na Androidzie bez kabla (ADB przez Wi‑Fi)

Cel: włączyć live‑skanowanie w przeglądarce mobilnej tak, aby przeglądarka działała w „secure context” (dla kamery) i aplikacja była dostępna pod `http://localhost:5173` na telefonie.

Wymagania
- Telefon z Androidem i ta sama sieć Wi‑Fi co komputer.
- Włączone Opcje programistyczne i Debugowanie USB (Ustawienia → Informacje o telefonie → kliknij 7× „Numer kompilacji”, następnie Ustawienia → System → Opcje programistyczne).
- Zainstalowany ADB (Android Platform Tools) na komputerze.
- Frontend i API uruchomione lokalnie (np. przez Docker Compose) i zmapowane na porty hosta: `5173` (frontend), `8000` (API).

Opcja A: Wireless debugging (Android 11+)
1) Włącz „Debugowanie bezprzewodowe” (Wireless debugging)
   - Ustawienia → System → Opcje programistyczne → Wireless debugging (włącz).
2) Sparuj urządzenie:
   - W Wireless debugging wybierz „Pair device with pairing code” – zobaczysz IP:PORT oraz kod parowania.
   - Na komputerze uruchom parowanie ADB:
     - `adb pair IP_URZĄDZENIA:PORT_PAROWANIA`
     - Wpisz kod parowania.
3) Po sparowaniu połącz ADB:
   - `adb connect IP_URZĄDZENIA:PORT_DEBUG` (PORT_DEBUG widać w liście „Paired devices”).
4) Ustaw reverse portów (aby telefon widział usługi hosta pod localhost):
   - `adb reverse tcp:5173 tcp:5173`
   - `adb reverse tcp:8000 tcp:8000`
   - `adb reverse tcp:8080 tcp:8080` (dla powiadomień ntfy)
5) Na telefonie otwórz w Chrome: `http://localhost:5173`
   - Pojawi się prośba o dostęp do aparatu, wybierz „Zezwól”.

Opcja B: Klasyczne ADB over Wi‑Fi (uniwersalne)
1) Podłącz telefon kablem USB (jednorazowo), zatwierdź zaufanie.
2) Przełącz ADB na TCP/IP:
   - `adb devices`
   - `adb tcpip 5555`
3) Odłącz kabel, sprawdź IP telefonu (w ustawieniach Wi‑Fi lub: `adb shell ip -f inet addr show wlan0`).
4) Połącz ADB po Wi‑Fi:
   - `adb connect IP_URZĄDZENIA:5555`
5) Reverse portów i uruchomienie jak wyżej:
   - `adb reverse tcp:5173 tcp:5173`
   - `adb reverse tcp:8000 tcp:8000`
   - `adb reverse tcp:8080 tcp:8080` (dla powiadomień ntfy)
   - Otwórz: `http://localhost:5173` na telefonie.

Dlaczego to działa
- Dla dostępu do kamery wymagana jest strona w HTTPS lub `http://localhost` na urządzeniu. `adb reverse` sprawia, że usługi z komputera są widoczne na telefonie pod `localhost`, dzięki czemu kamera działa bez certyfikatów.

Uruchomienie kontenerów (PowerShell)
- PowerShell nie obsługuje `&&`. Użyj średnika `;` lub odpal po kolei:
  - `docker compose build frontend; docker compose up -d frontend`
  - `docker compose build api; docker compose up -d api`

Rozwiązywanie problemów
- Brak promptu aparatu: upewnij się, że wchodzisz przez `http://localhost:5173` (ADB) lub przez HTTPS (tunel). Wejdź w kłódkę/„i” obok adresu → Uprawnienia → Aparat → „Zezwól”.
- „Urządzenie offline”/ADB nie łączy: zrestartuj `adb kill-server; adb start-server`, ponów `adb connect`, sprawdź, czy PC i telefon są w tej samej sieci.
- „Kamera zajęta”: zamknij aplikacje aparatów, WhatsApp, itp., które mogą trzymać kamerę w tle.
- Alternatywa bez ADB: tunel HTTPS (np. `cloudflared tunnel --url http://localhost:5173` lub `ngrok http 5173`) i otwarcie linku https na telefonie.

Uwagi dla Windows
- W PowerShell 5.x używaj średnika `;` między poleceniami.
- Jeśli firewall blokuje ADB over Wi‑Fi, tymczasowo zezwól na połączenia/porty lub użyj tunelu HTTPS.
kartoteka 2.0


Na komputerze:
Zaktualizuj ADB (wymagane platform‑tools ≥ 30): adb --version.
Zrestartuj ADB: adb kill-server.
Sparuj z portem: adb pair 192.168.111.114:37099 → wprowadź 6‑cyfrowy kod z telefonu.
Po sparowaniu: adb connect 192.168.111.114:NNNNN (port debugowania widoczny w "Paired devices").
Reverse portów: adb reverse tcp:5173 tcp:5173 i adb reverse tcp:8000 tcp:8000 i adb reverse tcp:8080 tcp:8080.
Na telefonie otwórz: http://localhost:5173.

---

## Powiadomienia mobilne o zamówieniach (ntfy)

System wspiera **self-hosted powiadomienia push** o nowych zamówieniach z Shoper.

**Dla środowiska testowego (WSL/Docker Desktop na Windows):**
1. Ustaw w `.env`: `NTFY_ENABLED=true`, `NTFY_TOPIC=kartoteka-orders-UNIQUE`
2. Użyj ADB reverse: `adb reverse tcp:8080 tcp:8080`
3. Zainstaluj aplikację ntfy na telefonie (Android/iOS)
4. W aplikacji dodaj serwer: `http://localhost:8080`
5. Subskrybuj temat: `kartoteka-orders-UNIQUE` (ten sam co w .env)
6. Otrzymuj powiadomienia z danymi klienta, wartością zamówienia i klikalnymi akcjami

**Dla serwera produkcyjnego (Linux):**
- Użyj IP serwera: `http://192.168.X.X:8080` (bez ADB reverse)
- Wszystko działa natywnie przez sieć LAN

Szczegóły: patrz `README-LOCAL.md` → sekcja "Powiadomienia mobilne"
