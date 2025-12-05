# 🎯 Auction API Documentation

## Backend Endpoints (Port 8000)

Wszystkie endpointy licytacji są dostępne pod prefiksem `/api/auctions`.

---

## 📋 Endpointy Aukcji

### 1. **GET /api/auctions/** - Lista aukcji

Pobiera listę aukcji z paginacją.

**Query Parameters:**
- `status` (optional): Filtruj po statusie (`draft`, `active`, `ended`, `cancelled`)
- `page` (optional, default: 1): Numer strony
- `per_page` (optional, default: 20, max: 100): Elementów na stronę

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "title": "Pikachu VMAX Rainbow Rare PSA 10",
      "current_price": 160.0,
      "start_price": 150.0,
      "status": "active",
      "end_time": "2025-12-11T20:00:00",
      "bid_count": 1,
      "time_remaining": 633986,
      "is_active": true
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20,
  "has_next": false,
  "has_prev": false
}
```

**Przykład:**
```bash
curl http://localhost:8000/api/auctions/?status=active&per_page=10
```

---

### 2. **POST /api/auctions/** - Utwórz aukcję (Admin)

Tworzy nową aukcję.

**Request Body:**
```json
{
  "title": "Pikachu VMAX Rainbow Rare PSA 10",
  "description": "Piękna karta w gradingu PSA 10",
  "image_url": "https://example.com/image.jpg",
  "start_price": 150.00,
  "min_increment": 5.00,
  "buyout_price": 300.00,
  "start_time": "2024-12-04T12:00:00",
  "end_time": "2025-12-11T20:00:00",
  "status": "active",
  "auto_publish_to_shoper": false
}
```

**Walidacje:**
- `end_time` musi być po `start_time`
- `end_time` musi być w przyszłości
- `start_price` > 0
- `min_increment` > 0

**Response:** `201 Created` + obiekt aukcji

---

### 3. **GET /api/auctions/{auction_id}** - Szczegóły aukcji

Pobiera szczegóły aukcji wraz ze wszystkimi bidami.

**Response:**
```json
{
  "id": 1,
  "title": "Pikachu VMAX Rainbow Rare PSA 10",
  "description": "...",
  "current_price": 160.0,
  "status": "active",
  "bid_count": 1,
  "time_remaining": 633986,
  "is_active": true,
  "bids": [
    {
      "id": 1,
      "auction_id": 1,
      "kartoteka_user_id": 1,
      "username": "admin",
      "amount": 160.0,
      "timestamp": "2025-12-04T11:53:29.162177"
    }
  ],
  "product_name": null,
  "card_name": null
}
```

---

### 4. **PUT /api/auctions/{auction_id}** - Aktualizuj aukcję (Admin)

Aktualizuje szczegóły aukcji.

**Request Body:** (wszystkie pola opcjonalne)
```json
{
  "title": "Nowy tytuł",
  "description": "Nowy opis",
  "end_time": "2025-12-15T20:00:00",
  "status": "active"
}
```

**Ograniczenia:**
- Nie można edytować aukcji w statusie `ended` lub `cancelled`

**Response:** Zaktualizowany obiekt aukcji

---

### 5. **DELETE /api/auctions/{auction_id}** - Usuń aukcję (Admin)

Usuwa aukcję.

**Ograniczenia:**
- Tylko aukcje w statusie `draft` mogą być usunięte
- Dla aktywnych aukcji użyj `/cancel`

**Response:** `204 No Content`

---

### 6. **POST /api/auctions/{auction_id}/cancel** - Anuluj aukcję (Admin)

Anuluje aktywną aukcję.

**Response:** Obiekt aukcji z `status: "cancelled"`

---

## 💰 Endpointy Licytacji

### 7. **POST /api/auctions/{auction_id}/bids** - Złóż ofertę

Użytkownicy Kartoteka App licytują przez ten endpoint.

**Request Body:**
```json
{
  "amount": 160.0,
  "kartoteka_user_id": 1,
  "username": "admin"
}
```

**Walidacje:**
- Aukcja musi być `active`
- Aukcja musi być w przedziale `start_time` - `end_time`
- `amount` >= `current_price + min_increment`
- Jeśli `amount` >= `buyout_price`: aukcja kończy się natychmiast

**Response:** `201 Created` + obiekt bida

**Przykład:**
```bash
curl -X POST http://localhost:8000/api/auctions/1/bids \
  -H "Content-Type: application/json" \
  -d '{"amount": 165.0, "kartoteka_user_id": 1, "username": "admin"}'
```

---

### 8. **GET /api/auctions/{auction_id}/bids** - Lista bidów

Pobiera wszystkie bidy dla aukcji (sortowane od najnowszych).

**Response:** Tablica obiektów bidów

---

## 📊 Statystyki

### 9. **GET /api/auctions/stats/overview** - Statystyki aukcji

Dashboard stats dla admina.

**Response:**
```json
{
  "total_auctions": 1,
  "active_auctions": 1,
  "ended_auctions": 0,
  "total_bids": 1,
  "total_value": 0.0,
  "avg_bids_per_auction": 1.0
}
```

---

## 👤 Synchronizacja Użytkowników

### 10. **POST /api/auctions/sync-user** - Sync użytkownika

Kartoteka App wywołuje ten endpoint aby zsynchronizować użytkownika do cache.

**Request Body:**
```json
{
  "kartoteka_user_id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "is_active": true
}
```

**Response:**
```json
{
  "status": "ok",
  "user_id": 1,
  "kartoteka_user_id": 1,
  "username": "admin"
}
```

---

## 🔄 Statusy Aukcji

| Status | Opis |
|--------|------|
| `draft` | Szkic - nie widoczna publicznie |
| `active` | Aktywna - przyjmuje bidy |
| `ended` | Zakończona - ma zwycięzcę |
| `cancelled` | Anulowana przez admina |

---

## 🧪 Testy API

### Test 1: Utwórz aukcję
```bash
curl -X POST http://localhost:8000/api/auctions/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Charizard VMAX",
    "start_price": 200.0,
    "min_increment": 10.0,
    "start_time": "2024-12-04T12:00:00",
    "end_time": "2025-12-11T20:00:00",
    "status": "active"
  }'
```

### Test 2: Lista aukcji
```bash
curl http://localhost:8000/api/auctions/?status=active
```

### Test 3: Licytuj
```bash
curl -X POST http://localhost:8000/api/auctions/1/bids \
  -H "Content-Type: application/json" \
  -d '{"amount": 210.0, "kartoteka_user_id": 1, "username": "user1"}'
```

### Test 4: Szczegóły
```bash
curl http://localhost:8000/api/auctions/1
```

### Test 5: Statystyki
```bash
curl http://localhost:8000/api/auctions/stats/overview
```

---

## 📦 Struktura Bazy Danych

### Tabela `auctions`
```sql
id                     INTEGER PRIMARY KEY
product_id             INTEGER (FK: products.id)
catalog_id             INTEGER (FK: card_catalog.id)
title                  VARCHAR(255)
description            TEXT
image_url              TEXT
start_price            FLOAT
current_price          FLOAT
min_increment          FLOAT
buyout_price           FLOAT
start_time             DATETIME
end_time               DATETIME
status                 VARCHAR(32)
winner_kartoteka_user_id INTEGER
auto_publish_to_shoper BOOLEAN
published_shoper_id    INTEGER
created_at             DATETIME
updated_at             DATETIME
ended_at               DATETIME
```

### Tabela `auction_bids`
```sql
id                 INTEGER PRIMARY KEY
auction_id         INTEGER (FK: auctions.id)
kartoteka_user_id  INTEGER
username           VARCHAR(255)
amount             FLOAT
timestamp          DATETIME
```

### Tabela `kartoteka_users` (cache)
```sql
id                 INTEGER PRIMARY KEY
kartoteka_user_id  INTEGER UNIQUE (ID from kartoteka.db)
username           VARCHAR(255)
email              VARCHAR(255)
is_active          BOOLEAN
synced_at          DATETIME
```

---

## ✅ Ukończone Funkcje

- ✅ CRUD aukcji (Create, Read, Update, Delete)
- ✅ Licytacja z walidacją
- ✅ Buyout (natychmiastowy zakup)
- ✅ Paginacja listy aukcji
- ✅ Filtrowanie po statusie
- ✅ Statystyki aukcji
- ✅ Cache użytkowników z Kartoteka App
- ✅ Obliczanie czasu pozostałego
- ✅ Historia bidów

## 🔜 Do Implementacji

- ⏳ Scheduler auto-zamykania aukcji
- ⏳ Automatyczne publikowanie do Shoper po zakończeniu
- ⏳ Powiadomienia dla zwycięzcy
- ⏳ WebSocket live updates
- ⏳ Frontend UI (zakładka Licytacje)
- ⏳ Admin Panel

---

## 🌐 Integracja z Frontendem

Frontend (port 5173) będzie używał tych endpointów poprzez Axios/Fetch:

```javascript
// Przykład w React
const fetchAuctions = async () => {
  const response = await fetch('http://localhost:8000/api/auctions/?status=active');
  const data = await response.json();
  return data.items;
};

const placeBid = async (auctionId, amount, userId, username) => {
  const response = await fetch(`http://localhost:8000/api/auctions/${auctionId}/bids`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ amount, kartoteka_user_id: userId, username })
  });
  return await response.json();
};
```

---

**Data utworzenia:** 2024-12-04  
**Status:** ✅ Backend GOTOWY do użycia  
**Następny krok:** Frontend UI
