# Aktualizacja rozpoznawania typu karty i domyślnych wartości

## Data: 2025-12-03

## Wprowadzone zmiany

### 1. Rozpoznawanie typu karty przez OpenAI Vision

**Plik:** `backend/app/vision.py`

#### Zmiany w prompcie AI:
- Dodano punkt 9 do instrukcji: **Special Card Variant**
- AI teraz rozpoznaje:
  - **Pokemon specjalne**: EX, V, VMAX, VSTAR, GX, ex (małe litery), -ex
  - **Trenerzy**: Supporter, Item, Stadium, Tool, ACE SPEC
  - **Energie**: Basic Energy, Special Energy
  
#### Przykłady rozpoznawania:
- `Pikachu ex` → variant='ex'
- `Professor Sada` (Supporter) → variant='Supporter'
- `Rare Candy` (Item) → variant='Item'
- `Path to the Peak` (Stadium) → variant='Stadium'

#### Zwracane dane:
- Nowy klucz w JSON: `variant`
- Jeśli nie wykryto specjalnego typu: `variant=null`

### 2. Mapowanie wariantów do Typu karty

**Plik:** `backend/app/attributes.py`

Zaktualizowano funkcję `map_detected_to_form_ids()`:
- Używa nowego pola `variant` z Vision API
- Mapuje wykryte warianty do opcji atrybutu "Typ karty" w Shoper
- Pomija generyczne typy ("normal", "regular")
- Jeśli nie znaleziono dopasowania → domyślnie "Nie dotyczy"

### 3. Domyślne wartości atrybutów

**Weryfikacja we wszystkich miejscach:**

#### Frontend (`frontend/src/views/Scan.tsx`):
✅ Linia 294-305: Domyślne wartości dla nowych skanów
- Język (`64`): `'142'` (Angielski)
- Jakość (`66`): `'176'` (Near Mint)
- Wykończenie (`65`): `'184'` (Normal)
- Typ karty (`39`): `'182'` (Nie dotyczy)

#### Backend - Duplikaty (`backend/app/main.py`):
✅ Linia 2063-2070: Domyślne wartości przy wykrytym duplikacie
- Język: `'142'` (English)
- Jakość: `'176'` (Near Mint)
- Wykończenie: `'184'` (Normal)
- Typ karty: `'182'` (Nie dotyczy)

#### Backend - Nowe skany (`backend/app/main.py`):
✅ Linia 2529-2530: Domyślny typ karty w candidate_details
- Typ karty: `'182'` (Nie dotyczy)

#### Backend - Batch Scan (`backend/app/main.py`):
✅ Linia 5421-5427: Domyślne wartości dla skanowania katalogowego
- Język: `'142'` (English)
- Jakość: `'176'` (Near Mint)
- Wykończenie: `'184'` (Normal)
- Typ karty: `'182'` (Nie dotyczy)

## Oczekiwane rezultaty

### Pojedyncze skanowanie:
1. Po załadowaniu karty, OpenAI Vision rozpoznaje specjalne oznaczenia (EX, V, GX, etc.)
2. System próbuje zmapować wykryty wariant do opcji "Typ karty"
3. Jeśli nie znaleziono dopasowania → ustawia "Nie dotyczy"
4. Wszystkie inne pola (Język, Stan, Wykończenie) mają sensowne domyślne wartości

### Skanowanie katalogowe (Batch):
1. Każda karta ma ustawione domyślne wartości
2. Jeśli AI wykryje specjalny typ → zostanie zmapowany
3. W przeciwnym razie → "Nie dotyczy"

### Przykładowe przypadki:

| Karta | Rozpoznany variant | Zmapowany Typ karty |
|-------|-------------------|---------------------|
| Pikachu ex | "ex" | Pokemon ex (lub Nie dotyczy jeśli nie ma w opcjach) |
| Charizard V | "V" | Pokemon V |
| Professor's Research (Supporter) | "Supporter" | Supporter |
| Rare Candy (Item) | "Item" | Trainer - Item |
| Zwykły Pokemon | null | Nie dotyczy |

## Testowanie

1. Zeskanuj kartę Pokemon EX/V/GX
2. Sprawdź pole "Typ karty" - powinno być zmapowane lub "Nie dotyczy"
3. Zeskanuj Trenera z podtytułem (np. Supporter)
4. Sprawdź czy został rozpoznany prawidłowo
5. Zeskanuj zwykłą kartę Pokemon
6. Sprawdź czy ma "Nie dotyczy"

## Debug

Jeśli typ karty nie jest rozpoznawany:
1. Sprawdź logi backendu - powinny pokazać co Vision API zwrócił w polu `variant`
2. Sprawdź czy w Shoper są opcje odpowiadające wykrytemu wariantowi
3. Zweryfikuj czy normalizacja nazw działa (funkcja `_norm()`)

## Kompatybilność

Zmiany są wstecznie kompatybilne:
- Stare skany bez pola `variant` → domyślnie "Nie dotyczy"
- Nowe skany z wykrytym wariantem → próba mapowania
- Jeśli mapowanie się nie uda → "Nie dotyczy"
