import os
import json
from dotenv import load_dotenv
from shoper_client import ShoperClient

# Wczytaj konfigurację z pliku .env
load_dotenv()

def inspect_categories():
    """
    Pobiera i wyświetla strukturę kategorii ze sklepu Shoper.
    """
    try:
        print("Łączenie z API Shoper...")
        client = ShoperClient()
        print("Połączono. Pobieranie kategorii...")

        # Pobierz wszystkie kategorie, obsługując paginację
        all_categories = []
        page = 1
        while True:
            response = client.get('categories', params={'page': page, 'limit': 250})
            if not response or 'list' not in response or not response['list']:
                break
            all_categories.extend(response['list'])

            if int(response.get('page', 1)) >= int(response.get('pages', 1)):
                break
            page += 1

        print(f"Pobrano {len(all_categories)} kategorii. Przetwarzanie danych...\n")

        if not all_categories:
            print("Nie znaleziono żadnych kategorii.")
            return

        print("-" * 80)
        print(f"{'ID':<10} | {'Parent ID':<10} | {'Pełna ścieżka kategorii'}")
        print("-" * 80)

        # Stwórz mapę ID -> dane kategorii dla łatwiejszego budowania ścieżek
        cat_map = {int(cat['category_id']): cat for cat in all_categories}

        def get_category_name(category_data):
            """Bezpiecznie wyciąga nazwę kategorii z tłumaczeń."""
            translations = category_data.get('translations', {})
            if isinstance(translations, dict):
                # Spróbuj dla 'pl_PL'
                if 'pl_PL' in translations and isinstance(translations['pl_PL'], dict):
                    return translations['pl_PL'].get('name', 'Brak nazwy')
                # Jeśli nie, weź pierwszą lepszą
                for lang_data in translations.values():
                    if isinstance(lang_data, dict):
                        return lang_data.get('name', 'Brak nazwy')
            return 'Brak nazwy'

        def get_full_path(category_id, category_map):
            """Rekurencyjnie buduje pełną ścieżkę dla danej kategorii."""
            if category_id not in category_map:
                return f"Nieznana kategoria (ID: {category_id})"

            category = category_map[category_id]
            parent_id = int(category.get('parent_id', 0))
            name = get_category_name(category)

            if parent_id == 0:
                return name
            else:
                return get_full_path(parent_id, category_map) + " > " + name

        # Sortuj kategorie po ID dla czytelności
        sorted_ids = sorted(cat_map.keys())

        for cat_id in sorted_ids:
            category = cat_map[cat_id]
            parent_id = category.get('parent_id', '0')
            full_path = get_full_path(cat_id, cat_map)

            print(f"{str(cat_id):<10} | {str(parent_id):<10} | {full_path}")

        print("-" * 80)

        # Zapisz pełną odpowiedź API do pliku dla głębszej analizy
        with open('categories_dump.json', 'w', encoding='utf-8') as f:
            json.dump(all_categories, f, indent=2, ensure_ascii=False)
        print("\nPełna odpowiedź z API została zapisana do pliku 'categories_dump.json'")


    except Exception as e:
        print(f"\nWYSTĄPIŁ BŁĄD: {e}")
        print("Upewnij się, że plik .env jest poprawnie skonfigurowany i masz uprawnienia do odczytu kategorii.")

if __name__ == "__main__":
    inspect_categories()