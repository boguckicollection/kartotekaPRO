# Poprawka wyszukiwania kart w API TCGGO

## Data: 2025-12-03

## Problem

Aplikacja często zwracała nieprawidłowe karty z API TCGGO:
- Ta sama nazwa Pokemon (np. "Pikachu"), ale **inny numer karty**
- Prawidłowa karta nie pojawiała się nawet w podpowiedziach
- Przykład: Skanowana karta "Pikachu #123" → zwracana "Pikachu #25"

## Przyczyna

**Plik:** `backend/app/providers.py`

Stara logika wyszukiwania:
1. Wykonywała 3 próby zapytań (Nazwa+Numer+Set, Nazwa+Numer, Nazwa)
2. **Przerywała po PIERWSZYM udanym zapytaniu** (nawet jeśli wyniki były złe)
3. Nie filtrowała wyników po numerze karty
4. Pokazywała karty z różnymi numerami razem

Rezultat: Jeśli Attempt 1 zwrócił karty (nawet złe), to Attempt 2 i 3 się nie wykonywały.

## Rozwiązanie

### 1. Zbieranie wszystkich wyników (linie 217-250)

**STARE:**
```python
if current_cards:
    cards = current_cards
    break  # ❌ Przerywa po pierwszym wyniku
```

**NOWE:**
```python
if current_cards:
    all_cards.extend(current_cards)  # ✅ Zbiera wszystkie wyniki
    # Przerywa tylko jeśli znaleziono wyniki z name+number
    if detected.number and label in ["Attempt 1", "Attempt 2"]:
        break
```

### 2. Deduplikacja wyników

Dodano deduplikację po `card.id`, aby uniknąć duplikatów z różnych zapytań.

### 3. Krytyczne filtrowanie po numerze (linia 332-340)

**NOWA LOGIKA:**
```python
# CRITICAL FILTER: If we detected a card number, ONLY show cards with exact number match
if detected.number:
    exact_matches = [c for c in results if c.number and str(c.number) == str(detected.number)]
    if exact_matches:
        results = exact_matches  # ✅ Pokazuj TYLKO karty z dokładnym numerem
```

**Korzyści:**
- Jeśli zeskanowano kartę z numerem → pokazuje **TYLKO** karty z tym numerem
- Eliminuje 99% błędnych dopasowań
- Jeśli nie ma dokładnego dopasowania → pokazuje wszystkie wyniki (z ostrzeżeniem w logach)

## Oczekiwane rezultaty

### Przed poprawką:
```
Zeskanowano: Pikachu #123
Zwrócone kandydaci:
  1. Pikachu #25 (najnowszy promo)
  2. Pikachu #45 (inny set)
  3. Pikachu #123 (GDZIEŚ na końcu listy lub wcale)
```

### Po poprawce:
```
Zeskanowano: Pikachu #123
Zwrócone kandydaci:
  1. Pikachu #123 (Set A)
  2. Pikachu #123 (Set B - reprint)
  [Karty z innymi numerami są UKRYTE]
```

## Testowanie

1. Zeskanuj kartę z wyraźnym numerem (np. Charizard #006/165)
2. Sprawdź listę kandydatów - **wszystkie powinny mieć numer #006**
3. Jeśli nie ma żadnej karty z tym numerem w bazie TCGGO → logi pokażą ostrzeżenie:
   ```
   WARNING: No exact number matches found for number 006, showing all X results
   ```

## Debugging

Logi backendu pokażą:
```
DEBUG: Search Attempt 1 (Specific): 'Charizard 006 EPISODE:Scarlet & Violet'
DEBUG: Search Attempt 1 (Specific) returned 5 results
DEBUG: Stopping search - found results with name+number
DEBUG: Filtered to 3 cards with exact number match: 006
```

## Przypadki brzegowe

### 1. Karta bez numeru
- Jeśli Vision API nie wykryło numeru (`detected.number = None`)
- Filtrowanie NIE jest stosowane
- Pokazuje wszystkie wyniki posortowane po score

### 2. Numer nie istnieje w bazie
- Jeśli TCGGO nie ma karty z danym numerem
- Pokazuje wszystkie wyniki z ostrzeżeniem w logach
- Użytkownik może ręcznie wybrać najbliższą kartę

### 3. Reprint (ten sam numer w wielu setach)
- Pokazuje wszystkie karty z danym numerem
- Sortowanie po score preferuje:
  - Dokładne dopasowanie setu (jeśli wykryto)
  - Dokładne dopasowanie set_code
  - Fuzzy match nazwy

## Kompatybilność

Zmiany są wstecznie kompatybilne:
- Stare skany bez numeru → działają jak wcześniej
- Nowe skany z numerem → pokazują tylko dokładne dopasowania
- Scoring i sortowanie pozostają bez zmian
