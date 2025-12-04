# Przewodnik migracji na serwer produkcyjny Linux

## 📦 Co migrować

Cały system jest w kontenerach Docker, więc migracja jest prosta:

### Pliki do skopiowania:
- **Katalog projektu** - cały folder `kartoteka-2.0/`
- **Baza danych i pliki** - folder `storage/` (SQLite + uploady + ntfy cache)
- **Konfiguracja** - plik `.env` (zawiera wszystkie ustawienia)

---

## 🚀 Kroki migracji (5 minut)

### 1. Backup środowiska testowego

```bash
# Na obecnym serwerze (WSL/test)
cd kartoteka-2.0
tar -czf ~/kartoteka-backup-$(date +%Y%m%d).tar.gz \
  docker-compose.yml \
  backend/ \
  frontend/ \
  storage/ \
  .env \
  .gitignore \
  README*.md
```

### 2. Transfer na nowy serwer

```bash
# Skopiuj na nowy serwer
scp ~/kartoteka-backup-*.tar.gz user@new-server:~

# Lub użyj USB/FTP/innej metody
```

### 3. Instalacja na nowym serwerze Linux

```bash
# Na nowym serwerze
ssh user@new-server

# Instalacja Docker (jeśli nie ma)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# Wyloguj się i zaloguj ponownie

# Rozpakuj backup
tar -xzf kartoteka-backup-*.tar.gz
cd kartoteka-2.0
```

### 4. Aktualizuj konfigurację

```bash
# Edytuj .env - TYLKO te linijki:
nano .env

# Znajdź i zmień IP na nowe (serwera Linux):
APP_BASE_URL=http://192.168.0.NEW_IP:5173
# LUB użyj domeny:
APP_BASE_URL=https://kartoteka.twojadomena.pl

# Reszta zostaje bez zmian!
```

### 5. Uruchom kontenery

```bash
# Uruchom wszystko
docker compose up -d

# Sprawdź status
docker compose ps

# Sprawdź logi
docker compose logs -f api
```

### 6. Test połączenia

```bash
# Z komputera w sieci LAN
curl http://NEW_IP:8000/health
curl http://NEW_IP:5173
curl http://NEW_IP:8080/v1/health
```

---

## 📱 Zmiana w aplikacji ntfy na telefonie

Po migracji na serwer Linux **nie potrzebujesz już ADB reverse**!

### W aplikacji ntfy:

1. Otwórz ustawienia subskrypcji tematu `kartoteka_orders_mobile_priv_71`
2. Zmień serwer z:
   - `http://localhost:8080` (stary - przez ADB)
   - NA: `http://192.168.0.NEW_IP:8080` (nowy - bezpośrednio)
3. Zapisz

**To wszystko!** Powiadomienia będą działać bez ADB.

---

## ⚙️ Opcjonalnie: Domena i HTTPS (produkcja)

Jeśli chcesz dostęp z Internetu lub HTTPS:

### Dodaj Caddy do docker-compose.yml:

```yaml
services:
  # ... istniejące serwisy ...
  
  caddy:
    image: caddy:latest
    container_name: kartoteka_caddy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - ./caddy-data:/data
      - ./caddy-config:/config
    restart: unless-stopped
```

### Utwórz Caddyfile:

```
# Główna aplikacja
kartoteka.twojadomena.pl {
    reverse_proxy frontend:5173
}

# API
api.kartoteka.twojadomena.pl {
    reverse_proxy api:8000
}

# Powiadomienia ntfy
notifications.kartoteka.twojadomena.pl {
    reverse_proxy ntfy:80
}
```

### Uruchom ponownie:

```bash
docker compose up -d
```

Caddy automatycznie pobierze certyfikaty SSL z Let's Encrypt!

W aplikacji ntfy użyj: `https://notifications.kartoteka.twojadomena.pl`

---

## 🔐 Bezpieczeństwo

### Dla dostępu publicznego (Internet):

1. **Firewall:**
   ```bash
   sudo ufw allow 22/tcp    # SSH
   sudo ufw allow 80/tcp    # HTTP
   sudo ufw allow 443/tcp   # HTTPS
   sudo ufw enable
   ```

2. **ntfy z hasłem** (jeśli expozycja do Internetu):
   ```bash
   docker exec -it kartoteka_ntfy sh
   ntfy user add admin
   # Wpisz hasło
   exit
   ```

3. **Backup automatyczny:**
   ```bash
   # Cron co tydzień
   0 2 * * 0 cd /path/to/kartoteka-2.0 && tar -czf ~/backups/kartoteka-$(date +\%Y\%m\%d).tar.gz storage/
   ```

---

## 📋 Checklist migracji

- [ ] Backup środowiska testowego
- [ ] Transfer plików na nowy serwer
- [ ] Instalacja Docker na nowym serwerze
- [ ] Rozpakowanie projektu
- [ ] Aktualizacja `APP_BASE_URL` w `.env`
- [ ] Uruchomienie `docker compose up -d`
- [ ] Test endpointów (8000, 5173, 8080)
- [ ] Zmiana serwera w aplikacji ntfy (z localhost na IP)
- [ ] Test powiadomień
- [ ] (Opcjonalnie) Konfiguracja domeny + Caddy
- [ ] (Opcjonalnie) Firewall i backup

---

## ❓ Troubleshooting

**"Port already in use"**
```bash
# Sprawdź co zajmuje port
sudo netstat -tlnp | grep :8080
# Zatrzymaj konfliktujący proces lub zmień port w docker-compose.yml
```

**"Permission denied" przy Docker**
```bash
# Dodaj użytkownika do grupy docker
sudo usermod -aG docker $USER
# Wyloguj się i zaloguj ponownie
```

**"Cannot connect to ntfy"**
```bash
# Sprawdź czy kontener działa
docker compose ps
# Sprawdź logi
docker compose logs ntfy
# Test z serwera
curl http://localhost:8080/v1/health
```

**"Database locked"**
```bash
# SQLite może być zablokowany podczas kopiowania
# Zatrzymaj kontenery przed backupem
docker compose down
# Zrób backup
# Uruchom ponownie
docker compose up -d
```

---

## 🎯 Podsumowanie

**Testowe (WSL):** ADB reverse `localhost:8080`  
**Produkcyjne (Linux):** Bezpośredni dostęp `http://IP:8080` lub `https://domena`

**Czas migracji:** ~5 minut (bez domeny) | ~15 minut (z domeną i SSL)

**Co się zmienia:** Tylko adres serwera w aplikacji ntfy (jednorazowo)

**Co pozostaje:** Cała historia, baza, konfiguracja, ustawienia
