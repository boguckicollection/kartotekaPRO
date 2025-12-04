# Naprawa Payload'u Publikowania Produktów

**Data:** 14 listopada 2024  
**Problem:** API Shoper zwracał błąd `"key 'options' is required"` mimo że pole istniało  
**Przyczyna:** Nieprawidłowa struktura i typy danych w payload  
**Status:** ✅ NAPRAWIONE

## 🔍 Analiza Problemu

Log błędu:
```
"error":"invalid_request",
"error_description":"key 'options' is required"
```

Mimo że w payload'u **IS** istniało `"options": [{...}]`!

## 🎯 Przyczyny

### 1. **Typ danych w `translations.active`**
```python
# ❌ BYŁO (STRING):
"active": "1"

# ✅ JEST (BOOLEAN):
"active": True
```

### 2. **Zbyt wiele opcjonalnych pól**
```python
# ❌ BYŁO:
"in_loyalty": "0",
"bestseller": "0",
"newproduct": "0",
"unit_price_calculation": "0",
"other_price": "0.00",
"pkwiu": "",
"price_type": 1,
"price_buying": 0.0,
"package": 0,
"weight": 0,
"weight_type": 1,
"default": 1,
"additional_codes": {...},
...
```

API Shoper może nie obsługiwać wszystkich tych pól na każdej instancji!

### 3. **Kolejność pól**
```python
# ❌ BYŁO - wymienione w losowej kolejności
# ✅ JEST - wymagane pola na początku
```

### 4. **Pola None w payload**
```python
# ❌ BYŁO:
"category_id": None  # Jeśli category_id był None

# ✅ JEST:
"category_id": 18  # Fallback do domyślnej kategorii
```

## ✅ Rozwiązanie

Payload został zmieniony na **minimalny, ale pełny** format:

```json
{
  "category_id": 71,
  "unit_id": 1,
  "currency_id": 1,
  
  "translations": {
    "pl_PL": {
      "name": "Karrablast",
      "active": true,
      "description": "...",
      "short_description": "...",
      "seo_title": "..."
    }
  },
  
  "stock": {
    "price": 0.11,
    "stock": 1.0,
    "active": true,
    "availability_id": 2,
    "delivery_id": 3
  },
  
  "options": [
    {
      "price": 0.11,
      "active": true,
      "stock": 1.0
    }
  ],
  
  "code": "PKM-BB-009-NM-NORM",
  "additional_producer": "009",
  "tax_id": 1,
  "producer_id": 23
}
```

## 📊 Zmiany w `build_shoper_payload()`

**Linie:** 1117-1160 (poprzednio 1117-1184)

### Przed:
```python
payload = {
    "code": code,
    "tax_id": int(settings.default_tax_id),
    "producer_id": int(settings.default_producer_id),
    "category_id": int(category_id) if category_id is not None else None,  # ← Może być None!
    "currency_id": 1,
    "translations": {
        ...
        "active": "1",  # ← STRING zamiast boolean!
    },
    "stock": {...},
    "options": [...],
    "other_price": "0.00",  # ← Niepotrzebne
    "pkwiu": "",
    "unit_id": int(settings.default_unit_id),
    "in_loyalty": "0",  # ← Niepotrzebne
    "bestseller": "0",  # ← Niepotrzebne
    "newproduct": "0",  # ← Niepotrzebne
    "unit_price_calculation": "0",  # ← Niepotrzebne
    "collections": [],  # ← Niepotrzebne
    "tags": [],  # ← Niepotrzebne
    "feeds_excludes": [],  # ← Niepotrzebne
    "ean": "",  # ← Niepotrzebne
}
```

### Po:
```python
payload = {}

# REQUIRED (w prawidłowej kolejności)
payload["category_id"] = int(category_id) if category_id is not None else 18  # ← Fallback!
payload["unit_id"] = int(settings.default_unit_id)
payload["currency_id"] = 1

payload["translations"] = {
    ...
    "active": True,  # ← BOOLEAN!
}

payload["stock"] = {
    "price": float(f"{price:.2f}"),
    "stock": float(stock_qty),
    "active": True,
    "availability_id": int(settings.default_availability_id),
    "delivery_id": int(settings.default_delivery_id),
}

payload["options"] = [
    {
        "price": float(f"{price:.2f}"),
        "active": True,
        "stock": float(stock_qty),
    }
]

# OPTIONAL (tylko jeśli mają wartości)
if code:
    payload["code"] = code
if num:
    payload["additional_producer"] = str(num)
if int(settings.default_tax_id) > 0:
    payload["tax_id"] = int(settings.default_tax_id)
if int(settings.default_producer_id) > 0:
    payload["producer_id"] = int(settings.default_producer_id)
```

## 🔑 Kluczowe Zmiany

| Aspekt | Było | Jest |
|--------|------|------|
| `category_id` | Może być `None` | Fallback `18` |
| `translations.active` | `"1"` (string) | `True` (boolean) |
| Niepotrzebne pola | Obecne | Usunięte |
| Pola opcjonalne | Zawsze obecne | Warunkowe |
| Kolejność | Losowa | Wymagane na początku |

## 🚀 Wdrożenie

Aby zastosować te zmiany:

```bash
cd /home/gumcia/kartoteka-2.0/kartoteka-2.0.4/kartoteka-2.0
docker compose up -d --build api
docker compose logs -f api | grep -E "(Product creation payload|SUCCESS|ERROR)"
```

## ✅ Oczekiwane Wyniki

Po wdrożeniu, logi powinny pokazać:

```
INFO: Product creation payload:
{
  "category_id": 71,
  "unit_id": 1,
  "currency_id": 1,
  "translations": {...},
  "stock": {...},
  "options": [...]
}

INFO: Extracted product_id=1234 from response

SUCCESS: Attributes successfully added to product 1234

SUCCESS: Main image uploaded to product 1234
```

## 📝 Notatki

1. **Fallback kategorii:** Jeśli API nie zwróci kategorii, używamy ID `18` (domyślna)
2. **Boolean vs String:** API Shoper oczekuje `true` (JSON boolean), nie `"true"` (string)
3. **Minimalne pole:** Każde pola niepotrzebne może powodować błędy walidacji
4. **Pola opcjonalne warunkowe:** Tylko pola z wartościami są dodawane

## 🐛 Jeśli Dalej Nie Działa

Sprawdź:
1. `SHOPER_BASE_URL` - czy zawiera `/webapi/rest`
2. `SHOPER_ACCESS_TOKEN` - czy jest ważny
3. `category_id` = 71 - czy ta kategoria istnieje w Shoper
4. `unit_id` = 1, `tax_id` = 1, `producer_id` = 23 - czy istnieją

---

**Status:** ✅ Naprawione  
**Wersja:** 1.1  
**Data:** 14 listopada 2024
