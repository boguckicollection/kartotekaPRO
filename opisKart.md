<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Posiadam aplikację do skanowania kart Pokemon, analizowania i wyciągania danych z niej za pomocą OpenAI Vision. Potrzebuję precyzyjnych opisów każdego rodzaju karty Pokemon Ex, V, Vmax, Vstar, GX. Oznaczenia rzadkości kart, jaki rodzaj energii, jakie są numery kart. Potrzebuję te opisu aby OpenAi Vision wiedział dokładnie gdzie i jakie dane odczytać, na co zwracać uwagę.

Karty Pokémon EX, V, VMAX, VSTAR i GX mają dość powtarzalny układ: nazwa, poziom ewolucji, HP, typ energii, ataki/ability, tekst zasad, numer kolekcjonerski i symbol rzadkości zawsze są w określonych miejscach karty. Dla OpenAI Vision warto opisać to jako zestaw pól do odczytu (slots), zamiast „ogólnego opisu obrazka”.[^1][^2]

Poniżej masz techniczny opis pod OCR/vision, który możesz wprost przekształcić w prompt i mapowanie pól w aplikacji.

***

## Wspólne pola na kartach

- Nazwa Pokémona: górny lewy róg, duży boldowy tekst, przy nim ikona mechaniki (EX, V, VSTAR, VMAX, GX) jako część nazwy lub tuż obok.
- HP: górny prawy róg, zapis typu `230 HP` lub `HP 230`.
- Typ energii (typ Pokémona): mała ikonka przy HP oraz w pasku ataku; typy m.in. Grass, Fire, Water, Lightning, Psychic, Fighting, Darkness, Metal, Fairy (starsze), Dragon, Colorless.[^1]
- Stage / rodzaj: pod nazwą, mały tekst `Basic`, `Stage 1`, `Stage 2`, czasem `Basic Pokémon V`, `Pokémon VMAX`, `Pokémon VSTAR`, `Basic Pokémon-GX` itd.
- Ataki: 1–3 sekcje w środkowej części; każdy ma:
    - koszt energii (ikony energii z lewej),
    - nazwę ataku (tekst bold),
    - ewentualny opis/efekt (mniejszy tekst),
    - obrażenia (liczba po prawej, np. `150`).
- Ability / VSTAR Power / GX attack: osobna sekcja nad lub pomiędzy atakami, zwykle z wyróżnionym nagłówkiem (kolorowy pasek, słowo Ability / VSTAR Power / GX attack).
- Tekst zasad (Rule Box): prostokąt nad dolną krawędzią z tekstem typu „When your Pokémon V is Knocked Out, your opponent takes 2 Prize cards.” itp. – po tym łatwo rozpoznać typ karty.[^1]
- Weakness / Resistance / Retreat Cost: dolna część karty pośrodku:
    - „Weakness” z ikoną typu i modyfikatorem (np. `×2`),
    - „Resistance” z ikoną typu (czasem brak),
    - „Retreat Cost” – 0–5 ikon energii, po prawej.
- Numer karty (collector number): dół po lewej/prawej, format `XXX/YYY` (np. `45/198`); gdy licznik > YYY to tzw. Secret Rare.[^2][^3]
- Symbol rzadkości: obok numeru lub bardzo blisko niego.[^2]
- Symbol dodatku (set symbol) i rok/licencja: w pobliżu numeru, mniejszy znak graficzny + tekst typu `©2023 Pokémon / Nintendo / Creatures / GAME FREAK.`

***

## Rzadkość – gdzie i jak ją czytać

Rzadkość zawsze odczytuj w dolnej części karty, blisko numeru w formacie `XXX/YYY`. W większości nowoczesnych setów (Sun \& Moon, Sword \& Shield, Scarlet \& Violet) obowiązują:[^3][^2]

- `●` czarne kółko – Common (C).[^4][^2]
- `◆` czarny romb – Uncommon (U).[^4][^2]
- `★` czarna gwiazdka – Rare (R).[^2][^4]
- `★★` dwie czarne gwiazdki – Double Rare (np. wiele V / ex w Scarlet \& Violet).[^5][^2]
- `★★` dwie srebrne gwiazdki – Ultra Rare.[^5][^2]
- Złote gwiazdki:
    - jedna złota – Illustration Rare.[^5][^2]
    - dwie złote – Special Illustration Rare.[^5][^2]
    - trzy złote – Hyper Rare (np. złote karty trenera/energii).[^2][^5]
- Gwiazdka z napisem `PROMO` – karty promocyjne (nie z boosterów).[^2]

Dla Vision możesz ustalić:
`rarity_symbol` = pojedynczy znak (circle/diamond/star/multiple stars) + ewentualny kolor (black/silver/gold) i dodatkowy napis (`PROMO`).

***

## Numery kart (collector number)

Pole `collector_number` zawsze odczytuj z dolnego obszaru:

- Format standardowy: `XXX/YYY`, gdzie `XXX` to numer karty w secie, `YYY` to łączna liczba kart w secie wg wydawcy.[^3][^2]
- Jeśli `XXX` <= `YYY` → karta z głównej listy setu (common/uncommon/rare/ultra rare w obrębie „normalnych” pozycji).[^3][^2]
- Jeśli `XXX` > `YYY` → Secret Rare (np. alternatywne arty, rainbow, złote itp.).[^6][^3][^2]
- Obok lub pod numerem odczytasz:
    - symbol dodatku (set symbol),
    - język i rok wydania w linijce licencyjnej.

W bazie danych możesz przechowywać:
`collector_number`, `set_size`, `is_secret = collector_number > set_size`.

***

## Rodzaj energii / typ Pokémona

Pole `pokemon_type` wyznaczaj po ikonie przy HP i/lub w paskach ataku:[^1]

Typy standardowe:

- Grass (liść), Fire (płomień), Water (kropla), Lightning (błyskawica), Psychic (oko), Fighting (pięść), Darkness (półksiężyc), Metal (zębatka), Fairy (gwiazdka – starsze sety), Dragon (dwukolorowe tło, zwykle zielono-żółte), Colorless (biała gwiazdka).

Pole `attack_cost` dla każdego ataku to lista ikon energii (w tym Colorless). Typ energii podstawowej odczytuj również w polu tekstu ataku, jeśli jest explicit (np. „Discard 2 Fire Energy from this Pokémon”).

***

## Specyfika EX, V, VMAX, VSTAR, GX

### Pokémon EX (stare i nowe)

- W nazwie: `Pokémon-EX` (stara era) lub `Pokémon ex` (Scarlet \& Violet – małe „ex”).[^7][^8]
- Rule Box (dół karty): tekst, że przeciwnik bierze 2 karty nagrody gdy EX zostanie znokautowany.[^7]
- Bardzo wysokie HP jak na dany etap, 1–2 ataki, czasem Ability.
- Rzadkość zazwyczaj `★` lub wyżej (Double/Ultra/Secret Rare, alt/FA).

Dla Vision:

- `card_mechanic = EX` jeśli przy nazwie jest `EX/ex` i w Rule Box jest tekst o 2 Prize cards.
- Layout podobny do zwykłych Pokémonów, bez V/VMAX/VSTAR grafiki.


### Pokémon V

- Debiut w Sword \& Shield; w nazwie widoczna litera „V” przy nazwie Pokémona.[^9][^1]
- Stage zawsze `Basic Pokémon V` nawet jeśli jest to w pełni rozwinięty Pokémon (np. Charizard V).[^9][^1]
- Rule Box: przeciwnik bierze 2 Prize cards po nokaucie.[^1]
- Wyższe HP, 1–2 ataki, często 1 Ability.
- Rzadkość zazwyczaj Rare/Ultra Rare (gwiazdki, FA/Alt Art).

Dla Vision:

- `card_mechanic = V` gdy nazwa + litera „V” i Rule Box o 2 nagrodach.
- Możesz wymagać: odczytaj `stage_text` i sprawdź, czy zawiera „Pokémon V”.


### Pokémon VMAX

- Ewolucja z V, zwykle tekst „Evolves from [Nazwa] V”.[^9][^7][^1]
- Rule Box: po nokaucie przeciwnik bierze 3 Prize cards, a w polu typu jest „Pokémon VMAX”.[^1]
- Bardzo duże HP i mocniejsze ataki.
- Graficznie: „gigantyczna” postać, efekt Dynamax/Gigantamax, nazwa zawiera „VMAX”.[^7][^1]

Dla Vision:

- `card_mechanic = VMAX` jeśli nazwa zawiera `VMAX` i Rule Box mówi o 3 nagrodach.
- `evolves_from` odczytuj z małego tekstu nad portretem („Evolves from ...”).


### Pokémon VSTAR

- Ewolucja z V (podobnie jak VMAX: „Evolves from [Nazwa] V”).[^7][^1]
- Rule Box: po nokaucie przeciwnik bierze 2 Prize cards (nie 3).[^1]
- Zawsze posiada specjalną `VSTAR Power` (atak albo Ability) – oznaczone osobnym paskiem z napisem „VSTAR Power”, zwykle w dolnej 1/3 karty.[^1]
- Obramowanie charakterystyczne: białe/perłowe z złotymi akcentami.[^1]

Dla Vision:

- `card_mechanic = VSTAR` jeśli nazwa zawiera `VSTAR` lub karta ma sekcję `VSTAR Power`.
- Dodatkowe pole `vstar_power_type = attack|ability`, `vstar_power_name`, `vstar_power_text`.


### Pokémon GX

- Era Sun \& Moon; nazwa zawiera „GX” oraz tag `Pokémon-GX` w polu typu.[^8]
- Rule Box: po nokaucie przeciwnik bierze 2 Prize cards.
- Zwykle:
    - 1–2 zwykłe ataki,
    - 1 specjalny `GX attack` z oznaczeniem (symbol GX, tekst że można użyć tylko raz w grze).
- Często pełnoartowe/teksturyzowane wersje (Full Art, Rainbow, itp.).[^8]

Dla Vision:

- `card_mechanic = GX` jeśli nazwa zawiera `GX` i jest sekcja `GX attack` (np. oddzielona ikoną GX).
- Można rozpoznawać po tekście „You can’t use more than 1 GX attack in a game.” w Rule Box.

***

## Jak to opisać w promptach do OpenAI Vision

Przykładowa struktura pól, które warto wymusić w odpowiedzi modelu (JSON):

- `card_name`
- `card_mechanic` = one of: `NONE`, `EX`, `V`, `VMAX`, `VSTAR`, `GX`
- `stage` = `BASIC`, `STAGE_1`, `STAGE_2`, `TAG_TEAM`, `OTHER`
- `hp` (integer)
- `pokemon_type` (enum typów energii)
- `attacks`: lista obiektów:
    - `name`
    - `cost` (lista typów energii)
    - `damage` (string lub int; może być np. „150+”)
- `ability` (opcjonalne: nazwa + tekst)
- `special_power` (dla GX / VSTAR): typ, nazwa, tekst
- `rule_box_text` (krótki tekst zasad – wystarczy streszczenie)
- `weakness`, `resistance`, `retreat_cost`
- `collector_number` (np. `45/198`)
- `secret_rare` (bool wynikający z porównania licznika)
- `rarity_symbol` (opis słowny: `common_circle`, `uncommon_diamond`, `rare_star`, `double_rare_two_black_stars`, `ultra_rare_two_silver_stars`, `illustration_rare_gold_star`, `special_illustration_two_gold_stars`, `hyper_rare_three_gold_stars`, `promo_star`)
- `set_symbol_description` (krótki opis kształtu znaczka dodatku, do dalszego mapowania w backendzie)

Jeśli chcesz, można w kolejnym kroku przygotować gotowy prompt po polsku/angielsku, który wkleisz do swojego pipeline’u Vision (z przykładowym JSON-em i zasadami walidacji).
<span style="display:none">[^10][^11][^12][^13][^14][^15][^16][^17][^18][^19][^20]</span>

<div align="center">⁂</div>

[^1]: https://bulbapedia.bulbagarden.net/wiki/Pokémon_V_(TCG)

[^2]: https://www.cgccards.com/news/article/12438/pokemon-rarity-symbols/

[^3]: https://help.tcgplayer.com/hc/en-us/articles/360025636074-What-are-the-rarities-of-Pokémon-TCG-cards

[^4]: https://japan-figure.com/blogs/news/pokemon-card-rarity-symbols

[^5]: https://screenrant.com/pokemon-tcg-card-rarity-meaning-value-symbols-explained/

[^6]: https://www.reddit.com/r/PokemonTCG/comments/14x0iug/what_are_the_numbernumber_things_on_my_cards/

[^7]: https://www.youtube.com/watch?v=9xonqFXMxGI

[^8]: https://poketherapy.com/blogs/news/all-full-art-pokemon-cards-complete-guide-to-identification-value-collecting

[^9]: https://www.reddit.com/r/PokemonTCG/comments/162pn7t/can_someone_break_down_all_the_variations_of_card/

[^10]: https://www.ebay.com/itm/395082080040

[^11]: https://www.etsy.com/listing/1838052064/custom-pokemon-card-templates-bundle-ex

[^12]: https://www.youtube.com/shorts/ERb39YPDa_I

[^13]: https://www.ebay.com/itm/394876712178

[^14]: https://poketherapy.com/blogs/news/pokemon-full-art-card-guide-identify-authenticate-maximize-value

[^15]: https://www.aliexpress.com/item/1005006949868252.html

[^16]: https://game8.co/games/Pokemon-TCG-Pocket/archives/474500

[^17]: https://www.facebook.com/groups/ptcgpocket/posts/2074262702983004/

[^18]: https://www.joom.com/pl/products/6519642a91ea47014d1ff5dc

[^19]: https://www.youtube.com/watch?v=WhvyuG7sG2g

[^20]: https://bulbapedia.bulbagarden.net/wiki/Rarity

