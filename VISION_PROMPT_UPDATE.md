# Aktualizacja promptu OpenAI Vision - Precyzyjna analiza kart Pokemon

## Data: 2025-12-04

## Źródło wiedzy

Prompt został przepisany na podstawie szczegółowej dokumentacji technicznej kart Pokemon (`opisKart.md`), która zawiera:
- Dokładne pozycje pól na karcie (TOP LEFT, TOP RIGHT, BOTTOM, etc.)
- Precyzyjne opisy symboli rzadkości (●◆★)
- Specyfikę mechanik kart (EX, V, VMAX, VSTAR, GX)
- Zasady rozpoznawania typów energii
- Formatowanie numerów kart (XXX/YYY, SWSH092)

---

## Porównanie: STARY vs NOWY prompt

### 📊 Statystyki

| Metryka | STARY | NOWY | Zmiana |
|---------|-------|------|--------|
| **Długość (linie)** | ~82 linie | ~175 linie | +113% |
| **Struktura** | Lista instrukcji | Sekcje tematyczne | +Organizacja |
| **Symbole wizualne** | Brak | Emoji, ASCII art | +Czytelność |
| **Szczegółowość** | Ogólna | Precyzyjna (pozycje pól) | +Dokładność |
| **Rzadkości** | 5 typów | 9 typów + ACE SPEC | +80% pokrycie |
| **Mechaniki kart** | Ogólne | Szczegółowe (Prize count!) | +Różnicowanie |

---

## Kluczowe ulepszenia

### 1. ✅ Struktura oparta na pozycjach pól

**STARY:**
```
"3. **Card Name**: Located at the top of the card."
"4. **Card Number**: Look for numbers like '102/102'..."
```

**NOWY:**
```
📍 **TOP LEFT CORNER:**
   • Card Name: Large bold text (e.g., 'Charizard')
   • Mechanic Tag: Look for 'EX', 'ex', 'V', 'VMAX', 'VSTAR', 'GX'
   • Stage: Small text below name (e.g., 'Basic Pokémon V')

📍 **TOP RIGHT CORNER:**
   • HP: Format '230 HP' or 'HP 230'
   • Type Icon: Small icon next to HP
```

**Rezultat:** Vision API wie DOKŁADNIE gdzie szukać każdego pola (jak OCR template).

---

### 2. ✅ Precyzyjne symbole rzadkości

**STARY (5 typów):**
```
- Circle = Common
- Diamond = Uncommon
- Star = Rare
- PINK/MAGENTA STAR = ACE SPEC
- White Star = Rare Holo
```

**NOWY (9 typów + opis wizualny):**
```
● Black circle = 'Common'
◆ Black diamond = 'Uncommon'
★ Black star = 'Rare'
★★ Two black stars = 'Double Rare'
★★ Two silver stars = 'Ultra Rare'
★ One gold star = 'Illustration Rare'
★★ Two gold stars = 'Special Illustration Rare'
★★★ Three gold stars = 'Hyper Rare'
★ PINK/MAGENTA star = 'ACE SPEC'
★ with 'PROMO' text = 'Promo'
```

**Rezultat:** 
- Rozróżnia liczbę gwiazdek (1 vs 2 vs 3)
- Rozróżnia kolory (czarne vs srebrne vs złote)
- Wykrywa tekst PROMO obok symbolu

---

### 3. ✅ Szczegółowe mechaniki kart (Z ZASADAMI!)

**STARY:**
```
"- Pokemon cards may have 'EX', 'V', 'VMAX', 'VSTAR', 'GX'..."
```

**NOWY (z różnicowaniem):**
```
🔷 **VMAX Cards:**
   • Name contains 'VMAX'
   • Stage: 'Pokémon VMAX' + 'Evolves from [Name] V'
   • Rule Box: 'opponent takes 3 Prize cards' (NOT 2!)  ← KLUCZOWE!
   • Gigantic/oversized Pokémon artwork

🔷 **VSTAR Cards:**
   • Name contains 'VSTAR'
   • Stage: 'Pokémon VSTAR' + 'Evolves from [Name] V'
   • Rule Box: 'opponent takes 2 Prize cards' (NOT 3!)  ← RÓŻNICA!
   • Has 'VSTAR Power' section (special colored bar)
   • White/pearl border with gold accents
```

**Rezultat:** Vision API wie, że:
- **VMAX = 3 Prize cards** (nie 2!)
- **VSTAR = 2 Prize cards** + VSTAR Power
- Może je odróżnić nawet jeśli obraz jest nieostry

---

### 4. ✅ Numery promocyjne (PEŁNY PREFIX)

**STARY:**
```
"Return ONLY the numerator (XX)."
"Return the FULL number INCLUDING the prefix (e.g., 'SWSH092', NOT just '92')."
```

**NOWY (z wizualnym opisem):**
```
• **Collector Number**: Format 'XXX/YYY' (e.g., '045/198' or 'SWSH092')
  ⚠️ CRITICAL: For promo cards with YELLOW BOX, return FULL prefix: 'SWSH092', 'SV092', 'SWSH023'
  ⚠️ Do NOT strip prefix! Return exactly as printed.
```

**Rezultat:** 
- Podkreśla "YELLOW BOX" jako wizualny marker
- Powtarza CRITICAL warning (2x zamiast 1x)
- Przykłady: 'SWSH092' zamiast '92'

---

### 5. ✅ Organizacja wizualna (ASCII separatory)

**NOWY (tylko w nowym promptcie):**
```
═══════════════════════════════════════════════════════════════
CARD STRUCTURE (Field Positions):
═══════════════════════════════════════════════════════════════

[Sekcje z emoji i punktorami]

═══════════════════════════════════════════════════════════════
SPECIAL MECHANICS IDENTIFICATION:
═══════════════════════════════════════════════════════════════

[Szczegółowe opisy mechanik]
```

**Rezultat:** 
- Vision model łatwiej "parsuje" strukturę promptu
- Sekcje są wyraźnie oddzielone
- Emoji 📍🔷⚠️ pomagają w nawigacji

---

### 6. ✅ Typy energii z ikonami

**STARY:**
```
"Determine the card's energy type (e.g., Grass, Fire, Water...)"
```

**NOWY (z emoji):**
```
🍃 Grass (leaf), 🔥 Fire (flame), 💧 Water (droplet), ⚡ Lightning (bolt),
👁️ Psychic (eye), 👊 Fighting (fist), 🌙 Darkness (crescent moon),
⚙️ Metal (gear - dark gray/silver), 🧚 Fairy (pink star - older sets),
🐉 Dragon (dual-color background), ⭐ Colorless (white star)

⚠️ CRITICAL: 'Metal' is DARK gray with metallic texture. 'Colorless' is LIGHT/WHITE.
```

**Rezultat:** 
- Emoji pomagają Vision API "zapamiętać" wygląd ikon
- Wyraźne rozróżnienie Metal (ciemny) vs Colorless (jasny)

---

### 7. ✅ Zasady walidacji (RULES section)

**NOWY (nie było w starym):**
```
═══════════════════════════════════════════════════════════════
RULES:
═══════════════════════════════════════════════════════════════
1. ❌ NO GUESSING: If text is unclear, return null. Better null than wrong.
2. ❌ NO DEFAULT VALUES: Do not assume 'Pikachu' or any default name.
3. ✅ READ EXACTLY: Extract text character-by-character from designated positions.
4. ✅ PRESERVE PREFIXES: 'SWSH092' must stay 'SWSH092', NOT '92'.
5. ✅ DISTINGUISH SYMBOLS: Pink star ≠ Black star. Two stars ≠ One star.
6. ✅ CHECK PRIZE COUNT: VMAX takes 3 prizes, VSTAR/V/GX/EX take 2 prizes.
7. ✅ JSON ONLY: Respond with valid JSON. No explanations, no markdown.
```

**Rezultat:** 
- Końcowe podsumowanie najważniejszych zasad
- Emoji ❌✅ wyraźnie oznaczają zakazy i nakazy
- Punkt 6: Kluczowa różnica między VMAX (3) a VSTAR (2)

---

## Format odpowiedzi JSON

### STARY:
```json
{
  "name": string,
  "number": string,
  "set": string,
  "rarity": string,
  "energy": string,
  "card_type": string,
  "variant": string or null
}
```

### NOWY (z opisem wartości):
```json
{
  "name": "string (Pokemon name only, e.g., 'Charizard')",
  "number": "string (FULL number with prefix, e.g., 'SWSH092' or '045')",
  "set": "string (set symbol description or set name if recognizable)",
  "rarity": "string (exact terms: 'Common', 'Uncommon', 'Rare', 'Double Rare', ...)",
  "energy": "string (type from icon: 'Grass', 'Fire', 'Water', ...)",
  "card_type": "string ('Pokemon', 'Trainer', or 'Energy')",
  "variant": "string or null ('EX', 'ex', 'V', 'VMAX', 'VSTAR', 'GX', 'Shiny', ...)"
}
```

**Rezultat:** Vision API wie jakie wartości są dozwolone (enum-like).

---

## Oczekiwane rezultaty

### ✅ Przed zmianą (problemy):
1. **VMAX vs VSTAR** - mylił te mechaniki (obie mają "V" w nazwie)
2. **Rzadkości** - nie rozróżniał 1 gwiazdka vs 2 gwiazdki
3. **ACE SPEC** - oznaczał jako "Rare" (różowa gwiazdka = zwykła gwiazdka)
4. **Numery promo** - zwracał "92" zamiast "SWSH092"
5. **Metal vs Colorless** - mylił ciemny szary z jasnym szarym

### ✅ Po zmianie (rozwiązania):
1. **VMAX vs VSTAR** - sprawdza Prize count (3 vs 2) + VSTAR Power
2. **Rzadkości** - liczy gwiazdki (★ vs ★★ vs ★★★) i kolory
3. **ACE SPEC** - wykrywa różową gwiazdkę jako osobną rzadkość
4. **Numery promo** - zachowuje pełny prefix (SWSH092)
5. **Metal vs Colorless** - explicit warning o kolorach (dark vs light)

---

## Testy do wykonania

### 1. Test mechanik kart

| Karta | Oczekiwany variant | Oczekiwana rarity | Prize count |
|-------|-------------------|-------------------|-------------|
| Charizard V | `V` | `Double Rare` | 2 |
| Charizard VMAX | `VMAX` | `Ultra Rare` | 3 |
| Charizard VSTAR | `VSTAR` | `Ultra Rare` | 2 + VSTAR Power |
| Pikachu ex (SV) | `ex` | `Double Rare` | 2 |
| Mewtwo GX | `GX` | `Rare` | 2 + GX attack |

**Jak testować:**
1. Zeskanuj każdą kartę
2. Sprawdź czy `variant` jest poprawny
3. Sprawdź czy `rarity` odpowiada liczbie gwiazdek
4. Backend: Zweryfikuj logikę Rule Box (2 vs 3 Prize cards)

---

### 2. Test symboli rzadkości

| Symbol | Oczekiwana wartość |
|--------|-------------------|
| ● | `Common` |
| ◆ | `Uncommon` |
| ★ (czarna) | `Rare` |
| ★★ (czarne) | `Double Rare` |
| ★★ (srebrne) | `Ultra Rare` |
| ★ (złota) | `Illustration Rare` |
| ★★ (złote) | `Special Illustration Rare` |
| ★★★ (złote) | `Hyper Rare` |
| ★ (różowa) | `ACE SPEC` |
| ★ + PROMO | `Promo` |

**Jak testować:**
1. Przygotuj karty z różnymi symbolami
2. Zeskanuj każdą
3. Sprawdź czy `rarity` dokładnie odpowiada symbolowi
4. Specjalna uwaga: różowa gwiazdka → ACE SPEC (NIE Rare!)

---

### 3. Test numerów promocyjnych

| Numer na karcie | Oczekiwany `number` |
|-----------------|---------------------|
| SWSH092 (yellow box) | `SWSH092` |
| SV023 (yellow box) | `SV023` |
| 045/198 (normal) | `045` |
| PR-SW 123 | `PR-SW 123` |

**Jak testować:**
1. Zeskanuj karty promocyjne z żółtym pudełkiem
2. Sprawdź czy `number` zawiera PEŁNY prefix
3. Backend: Sprawdź czy `providers.py` dopasowuje SWSH092 do 092

---

### 4. Test typów energii

| Ikona | Kolor | Oczekiwany `energy` |
|-------|-------|---------------------|
| ⚙️ | Ciemny szary/srebrny | `Metal` |
| ⭐ | Jasny szary/biały | `Colorless` |
| 🍃 | Zielony | `Grass` |
| 👁️ | Fioletowy | `Psychic` |

**Jak testować:**
1. Zeskanuj karty Metal i Colorless (trudne przypadki)
2. Sprawdź czy Vision nie myli tych typów
3. Sprawdź czy inne typy są poprawnie wykrywane

---

## Logi debug do monitorowania

### Backend (podczas analizy):
```python
print(f"DEBUG: Vision detected variant: {detected.get('variant')}")
print(f"DEBUG: Vision detected rarity: {detected.get('rarity')}")
print(f"DEBUG: Vision detected number: {detected.get('number')}")
```

### Przykładowe logi po zmianie:
```
DEBUG: Vision detected variant: VSTAR
DEBUG: Vision detected rarity: Ultra Rare
DEBUG: Vision detected number: SWSH092
DEBUG: Attribute mapping: variant=VSTAR → Shoper type_id=XX
```

---

## Znane ograniczenia nowego promptu

### 1. Długość promptu (+113%)
- **Problem:** Dłuższy prompt = więcej tokenów = wyższy koszt API
- **Oszacowanie:** ~2000 tokenów (był ~900 tokenów)
- **Koszt:** gpt-4o-mini: $0.00030 za 2k tokenów input (~2x więcej)
- **Rozwiązanie:** Akceptowalne (wciąż bardzo tanie: <$0.001 za skan)

### 2. Emoji mogą być ignorowane przez model
- **Problem:** Vision API może nie "widzieć" emoji w promptcie
- **Rozwiązanie:** Emoji są tylko dla czytelności, tekst pozostaje kluczowy

### 3. Wymaga GPT-4 Vision lub nowszego
- **Problem:** Starsze modele (GPT-3.5) mogą nie obsłużyć tak złożonego promptu
- **Obecny model:** gpt-4o-mini (wspiera Vision i złożone prompty)
- **Status:** ✅ Kompatybilne

### 4. Może wymagać fine-tuningu na Twojej bazie
- **Problem:** Niektóre sety mają niestandardowe layouty (np. WOTC, EX era)
- **Rozwiązanie przyszłościowa:** Zbierać przykłady błędów i dodawać do promptu

---

## Wsteczna kompatybilność

✅ **TAK - pełna kompatybilność:**
- Format JSON wyjściowy: **IDENTYCZNY**
- Klucze: `name`, `number`, `set`, `rarity`, `energy`, `card_type`, `variant`
- Wartości null: **OBSŁUGIWANE** (jeśli pole nieczytelne)
- Backend: **BEZ ZMIAN** (tylko prompt się zmienił)
- Frontend: **BEZ ZMIAN** (odbiera ten sam JSON)

---

## Rollback (jeśli coś pójdzie nie tak)

Jeśli nowy prompt powoduje problemy:

```bash
cd /home/gumcia/kartoteka-2.0
git diff backend/app/vision.py > vision_prompt_new.patch
git checkout HEAD -- backend/app/vision.py  # Przywróć stary prompt
```

Lub manualnie przywróć stary prompt z commita przed zmianą.

---

## Następne kroki (opcjonalne ulepszenia)

### 1. A/B Testing
- Uruchom 50 skanów ze starym promptem, 50 z nowym
- Porównaj dokładność (accuracy rate)
- Metryki: % correct name, % correct rarity, % correct variant

### 2. Dodaj przykłady kart do promptu
- GPT-4 Vision wspiera "few-shot learning"
- Dodaj 2-3 przykładowe karty (base64) z poprawnymi odpowiedziami
- Format: `[Example 1: Image of Charizard V → Expected JSON]`

### 3. Rozszerz o Trainer cards
- Obecnie prompt skupia się na Pokemon
- Dodaj sekcję dla Trainer cards (Supporter, Item, Stadium, Tool)
- Format: TOP CENTER (nazwa), BOTTOM LEFT (typ: Supporter/Item)

### 4. Dodaj confidence score
- Poproś Vision API o zwrócenie `confidence` (0.0-1.0) dla każdego pola
- Backend: Jeśli confidence < 0.7 → pokaż warning użytkownikowi
- Format JSON: `{"name": "Charizard", "name_confidence": 0.95, ...}`

---

## Podsumowanie zmian

| Kategoria | Zmiana | Impact |
|-----------|--------|--------|
| **Struktura** | Lista → Sekcje tematyczne z emoji | +++Czytelność |
| **Rzadkości** | 5 → 9 typów + ACE SPEC | +++Dokładność |
| **Mechaniki** | Ogólne → Szczegółowe (Prize count) | +++Różnicowanie |
| **Numery** | Generyczne → Yellow box + prefix | +++Promo cards |
| **Energia** | Lista → Ikony + kolory | ++Metal vs Colorless |
| **Zasady** | Brak → 7-punktowa lista | ++Konsystencja |
| **Długość** | 82 → 175 linii | -Koszt (+113%) |
| **Koszt API** | ~$0.0003 → ~$0.0006 | -Budget (2x) |
| **Dokładność** | ~85% → ???% | ??(do testowania) |

---

## Autor

**Data:** 2025-12-04  
**Źródło:** `opisKart.md` (dokumentacja techniczna kart Pokemon)  
**Wersja:** 2.0  
**Status:** ✅ Gotowe do testowania  
**Model:** gpt-4o-mini (GPT-4 Vision)

---

## Changelog

- **v2.0 (2025-12-04):** Kompletny rewrite promptu na podstawie opisKart.md
  - Dodano sekcje strukturalne (TOP LEFT, TOP RIGHT, BOTTOM)
  - Rozszerzono rzadkości (9 typów)
  - Dodano szczegółowe mechaniki (VMAX 3 prizes, VSTAR 2 prizes + Power)
  - Dodano zasady walidacji (RULES section)
  - Dodano emoji i ASCII art dla czytelności

- **v1.0 (2025-12-04):** Poprzednia wersja
  - Podstawowe instrukcje
  - 5 typów rzadkości
  - Ogólne opisy mechanik
