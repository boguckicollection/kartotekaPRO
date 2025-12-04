# Jak przywrócić stary wygląd skanowania

## Backup
Stary plik został zapisany jako:
```
/home/gumcia/kartoteka-2.0/frontend/src/views/Scan.tsx.backup
```

## Przywrócenie starego UI

Aby wrócić do starego wyglądu, wykonaj:

```bash
cd /home/gumcia/kartoteka-2.0/frontend/src/views
cp Scan.tsx.backup Scan.tsx
```

## Zmiany w nowym UI

### Co zostało zmienione:
1. **Przyciski do wgrywania plików przeniesione na górę** - teraz są od razu widoczne bez przewijania
2. **Większe, bardziej wyraziste przyciski** - gradient, efekty hover, ikony
3. **Przycisk "Wyślij do analizy"** - większy, pełna szerokość, z ikonami
4. **Podglądy wyświetlane tylko po załadowaniu skanu** - lepsza organizacja przestrzeni

### Zachowana funkcjonalność:
- Wszystkie funkcje działają identycznie jak wcześniej
- Żadne callbacki ani logika nie zostały zmienione
- Tylko wizualna reorganizacja elementów UI

## Data backupu
- Data: 2025-12-03
- Wersja: Przed zmianą układu UI skanowania
