#!/usr/bin/env python3
from flask import Flask, render_template_string, request, redirect, url_for, flash
import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# --- KONFIGURACJA APLIKACJI ---
app = Flask(__name__)
app.secret_key = 'super_tajny_klucz_pokemon'
SHOPS_FILE = 'shops_config.json'

# --- DOMYŚLNA KONFIGURACJA SKLEPÓW (NA PODSTAWIE TWOICH DANYCH) ---
DEFAULT_SHOPS = [
    {
        "name": "BoosterPoint",
        "domain": "boosterpoint.pl",
        # URL z parametrem ceny
        "search_url": "https://boosterpoint.pl/wszystkie-produkty/?s={query}&post_type=product&ct_product_price=1",
        "item_selector": ".product", 
        "title_selector": ".woocommerce-loop-product__title",
        "link_selector": ".woocommerce-loop-product__link",
        "price_selector": ".price ins .amount bdi, .price .amount bdi",
        "price_type": "text",
        # Sprawdzamy klasę kontenera pod kątem braku towaru
        "stock_check_class": "outofstock" 
    },
    {
        "name": "LootQuest",
        "domain": "lootquest.pl",
        # URL z parametrem dgwt_wcas
        "search_url": "https://lootquest.pl/?s={query}&post_type=product&dgwt_wcas=1",
        "item_selector": ".product",
        "title_selector": ".woocommerce-loop-product__title",
        "link_selector": ".woocommerce-loop-product__link",
        "price_selector": ".price ins .amount bdi, .price .amount bdi",
        "price_type": "text",
        "stock_check_class": "outofstock"
    },
    {
        "name": "JuniorKurczak",
        "domain": "juniorkurczak.pl",
        "search_url": "https://juniorkurczak.pl/products/search?keyword={query}",
        # Wrapper wewnętrzny
        "item_selector": ".grid-product__wrap-inner",
        "title_selector": ".grid-product__title-inner",
        "link_selector": "a.grid-product__link", 
        "price_selector": ".details-product-price__value",
        "price_type": "text"
    },
    {
        "name": "PokeShop",
        "domain": "pokeshop.pl",
        # Specyficzny URL szukaj.html/szukaj=...
        "search_url": "https://pokeshop.pl/szukaj.html/szukaj={query}",
        # Kontener produktu to .Okno (zawiera .ElementListingRamka)
        "item_selector": ".Okno", 
        "title_selector": ".ProdCena h3 a",
        "link_selector": ".ProdCena h3 a", # Link jest tam gdzie tytuł
        "price_selector": ".CenaAktualna",
        "price_type": "text"
    },
    {
        "name": "TCG Love",
        "domain": "tcglove.pl",
        # URL searchquery z parametrami
        "search_url": "https://www.tcglove.pl/pl/searchquery/{query}/1/full/5?url={query_commas}",
        # Custom element
        "item_selector": "product-tile",
        "title_selector": ".product-tile__name",
        "link_selector": "a", 
        "price_selector": ".price__value",
        "price_type": "text"
    },
    {
        "name": "PokeKarty",
        "domain": "pokekarty.pl",
        "search_url": "https://pokekarty.pl/?s={query}&post_type=product",
        "item_selector": "div.product-wrapper",
        "title_selector": "h3.wd-entities-title a",
        "link_selector": "h3.wd-entities-title a",
        "price_selector": ".price ins .amount bdi, .price .amount bdi",
        "price_type": "text",
        "stock_check_class": "outofstock"
    }
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
}

# --- FUNKCJE POMOCNICZE ---

def load_shops():
    if not os.path.exists(SHOPS_FILE):
        save_shops(DEFAULT_SHOPS)
        return DEFAULT_SHOPS
    with open(SHOPS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_shops(data):
    with open(SHOPS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def clean_price(text):
    if not text: return 0.0
    # Usuwamy wszystko co nie jest cyfrą lub przecinkiem/kropką
    clean = re.sub(r'[^\d,.]', '', str(text))
    clean = clean.replace(',', '.')
    try:
        val = float(clean.strip('.'))
        return val
    except ValueError:
        return 0.0

def make_search_url(url_template, query):
    # Standardowe kodowanie spacje -> +
    query_plus = urllib.parse.quote_plus(query)
    # Specjalne dla TCG Love (przecinki zamiast spacji w parametrze url=)
    query_commas = urllib.parse.quote(query.replace(" ", ","))
    
    url = url_template.replace("{query}", query_plus)
    url = url.replace("{query_commas}", query_commas)
    return url

# --- LOGIKA FILTROWANIA ---

def is_valid_match(title, query):
    title_lower = title.lower()
    query_lower = query.lower()
    
    # 1. Sprawdzenie słów kluczowych
    query_words = query_lower.split()
    significant_words = [w for w in query_words if len(w) > 2]
    
    if significant_words:
        matches = 0
        for word in significant_words:
            if word in title_lower:
                matches += 1
        # Musi pasować większość słów
        if matches < len(significant_words) * 0.5:
             return False, "Nie pasuje do nazwy"

    # 2. SŁOWA ZAKAZANE
    # Dodano 'break', 'kushi', 'live' aby wykluczyć te oferty zgodnie z życzeniem
    exclusion_list = [
        "box", "display", "bundle", "etb", "elite trainer box", "zestaw", "case", 
        "puszka", "tin", "album", "poster", "collection",
        "break", "kushi", "live", "otwieranie", "otwieramy"
    ]
    
    user_wants_excluded = any(ex in query_lower for ex in exclusion_list)
    
    if not user_wants_excluded:
        found_forbidden = [word for word in exclusion_list if word in title_lower]
        if found_forbidden:
            return False, f"Wykluczone słowo: {found_forbidden[0]}"
            
    return True, "OK"

# --- SILNIK WYSZUKIWANIA ---

def process_shop(shop, query):
    result = {
        "shop_name": shop['name'],
        "domain": shop['domain'],
        "found": False,
        "product_name": "Brak produktu / Niedostępny",
        "price": 0.0,
        "link": "#",
        "error": None,
        "available": False
    }

    try:
        search_url = make_search_url(shop['search_url'], query)
        # Timeout nieco dłuższy dla bezpieczeństwa
        resp_search = requests.get(search_url, headers=HEADERS, timeout=15)
        
        if resp_search.status_code != 200:
            result['error'] = f"Błąd HTTP {resp_search.status_code}"
            return result

        soup = BeautifulSoup(resp_search.content, 'html.parser')
        
        item_selector = shop.get('item_selector')
        items = []
        
        if item_selector:
            items = soup.select(item_selector)
        else:
            # Fallback
            link_el = soup.select_one(shop['link_selector'])
            if link_el: items = [link_el.parent]

        if not items:
            return result 

        # Pętla po wynikach (szukamy pierwszego pasującego)
        for item in items[:6]:
            # 1. Tytuł
            title_selector = shop.get('title_selector', shop['link_selector'])
            title_el = item.select_one(title_selector)
            if not title_el: continue
            
            title_text = title_el.get_text(strip=True)
            
            # 2. Filtr
            is_valid, msg = is_valid_match(title_text, query)
            if not is_valid: continue
            
            # 3. Link
            link_el = item.select_one(shop['link_selector'])
            if not link_el and item.name == 'a': link_el = item
            if not link_el: link_el = item.find('a')
            if not link_el or not link_el.has_attr('href'): continue
            
            product_url = link_el['href']
            if not product_url.startswith("http"):
                base_domain = shop['domain']
                path = product_url.lstrip('/')
                product_url = f"https://{base_domain}/{path}"
            
            # 4. Sprawdzenie dostępności NA LIŚCIE (Optymalizacja)
            # Jeśli element ma klasę 'outofstock', to od razu wiemy, że brak.
            is_available = True
            stock_class = shop.get('stock_check_class')
            if stock_class:
                # Sprawdzamy klasy samego itemu i jego rodziców/dzieci w prosty sposób
                item_classes = item.get('class', [])
                if stock_class in item_classes:
                    is_available = False
                # Czasami klasa jest głębiej
                elif item.select_one(f".{stock_class}"):
                    is_available = False

            # Jeśli produkt jest oznaczony jako niedostępny na liście,
            # to i tak go wyświetlamy (jako wyszarzony), ale nie musimy wchodzić głębiej po cenę
            # CHYBA ŻE cena nie jest widoczna na liście.
            # W podanych przykładach, cena jest zazwyczaj na liście, ale
            # dla pewności wchodzimy na stronę produktu, żeby pobrać świeżą cenę i status.
            
            try:
                time.sleep(0.2)
                resp_product = requests.get(product_url, headers=HEADERS, timeout=10)
                soup_product = BeautifulSoup(resp_product.content, 'html.parser')
                
                # A. Potwierdzenie dostępności na karcie produktu
                # (Czasami lista kłamie, karta mówi prawdę)
                if shop.get('stock_selector'):
                    oos_el = soup_product.select_one(shop['stock_selector'])
                    if oos_el: is_available = False
                
                # Dodatkowe sprawdzenie tekstu dla pewności
                if is_available:
                    text_content = soup_product.get_text().lower()
                    if "brak w magazynie" in text_content or "produkt niedostępny" in text_content:
                        # Uwaga: to może dać false positive z menu, ale spróbujmy
                        pass

                # B. Cena
                val = 0.0
                selectors = shop['price_selector'].split(',')
                price_el = None
                for sel in selectors:
                    price_el = soup_product.select_one(sel.strip())
                    if price_el: break

                if price_el:
                    if price_el.has_attr('content'):
                        val = clean_price(price_el['content'])
                    else:
                        val = clean_price(price_el.get_text(strip=True))
                
                # Fallbacki
                if val == 0.0:
                    fallback = soup_product.select_one(".woocommerce-Price-amount bdi")
                    if fallback: val = clean_price(fallback.get_text(strip=True))
                if val == 0.0:
                    fallback = soup_product.select_one(".price__value")
                    if fallback: val = clean_price(fallback.get_text(strip=True))
                if val == 0.0:
                    meta = soup_product.select_one("meta[property='product:price:amount']")
                    if meta: val = clean_price(meta['content'])

                if val > 0:
                    result['found'] = True
                    result['product_name'] = title_text
                    result['link'] = product_url
                    result['price'] = val
                    result['available'] = is_available
                    result['error'] = None
                    return result
                
            except Exception:
                continue

        if not result['found']:
            result['error'] = "Nie znaleziono (filtrowanie)"

    except Exception as e:
        result['error'] = str(e)
    
    return result

# --- HTML TEMPLATES ---

HTML_BASE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PokeCena - Monitor TCG</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Poppins', sans-serif; }
        .loader-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(255, 255, 255, 0.95);
            z-index: 9999;
            display: flex; justify-content: center; align-items: center; flex-direction: column;
            backdrop-filter: blur(5px);
        }
        .pokeball-spinner {
            width: 80px; height: 80px;
            border: 8px solid #333;
            border-radius: 50%;
            border-top-color: #ef4444;
            border-bottom-color: #fff;
            animation: spin 1s linear infinite;
            background: linear-gradient(to bottom, #ef4444 48%, #333 48%, #333 52%, #fff 52%);
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
    <script>
        function showLoader() { document.getElementById('loader').classList.remove('hidden'); }
    </script>
</head>
<body class="bg-gray-50 text-gray-800 min-h-screen flex flex-col">
    <div id="loader" class="loader-overlay hidden">
        <div class="pokeball-spinner mb-6"></div>
        <h2 class="text-2xl font-bold text-gray-800 animate-pulse">Przeszukuję sklepy...</h2>
    </div>
    <nav class="bg-white shadow-sm sticky top-0 z-50">
        <div class="container mx-auto px-4 py-4 flex justify-between items-center">
            <a href="/" class="text-2xl font-bold flex items-center gap-2 text-indigo-600">
                <i class="fa-solid fa-fire text-orange-500"></i> PokeCena
            </a>
            <div class="flex gap-4">
                <a href="/" class="flex items-center gap-2 px-4 py-2 rounded-lg transition {{ 'bg-indigo-50 text-indigo-700 font-semibold' if active=='home' else 'text-gray-500 hover:bg-gray-100' }}">Szukaj</a>
                <a href="/shops" class="flex items-center gap-2 px-4 py-2 rounded-lg transition {{ 'bg-indigo-50 text-indigo-700 font-semibold' if active=='shops' else 'text-gray-500 hover:bg-gray-100' }}">Sklepy</a>
            </div>
        </div>
    </nav>
    <div class="container mx-auto px-4 py-8 flex-grow">
        {{ content|safe }}
    </div>
</body>
</html>
"""

HTML_HOME = """
<div class="max-w-5xl mx-auto">
    <div class="text-center mb-10">
        <h1 class="text-4xl font-extrabold text-gray-900 mb-3">Znajdź najlepsze okazje TCG</h1>
        <p class="text-gray-500 text-lg">Szukam w {{ shop_count }} sklepach.</p>
    </div>
    <div class="bg-white rounded-2xl shadow-xl p-2 mb-12 max-w-3xl mx-auto border border-gray-100 transform transition hover:scale-[1.01]">
        <form action="/search" method="POST" class="flex gap-2 relative" onsubmit="showLoader()">
            <div class="relative flex-grow">
                <div class="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none"><i class="fa-solid fa-search text-gray-400"></i></div>
                <input type="text" name="query" value="{{ query if query else '' }}" placeholder="Wpisz nazwę (np. Prismatic Evolutions Booster)" class="w-full pl-12 pr-4 py-4 rounded-xl focus:outline-none text-lg text-gray-700" required autocomplete="off">
            </div>
            <button type="submit" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-8 rounded-xl transition shadow-lg flex items-center gap-2"><span>Szukaj</span></button>
        </form>
    </div>

    {% if results is defined and results %}
        {% set found_count = results|selectattr('found')|list|length %}
        <div class="mb-6 flex justify-between items-end px-2">
            <span class="bg-indigo-100 text-indigo-800 text-xs font-semibold px-3 py-1 rounded-full">Znaleziono: {{ found_count }} / {{ results|length }}</span>
        </div>
        <div class="grid grid-cols-1 gap-4">
            {% set available_results = results|selectattr('available')|list %}
            {% set best = available_results|sort(attribute='price')|first if available_results else None %}
            
            {% for item in results|sort(attribute='price') %}
            <div class="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden transition hover:shadow-lg flex flex-col sm:flex-row 
                {{ 'ring-2 ring-green-500 ring-offset-2 scale-[1.01]' if item == best else '' }}
                {{ 'opacity-70 bg-gray-50 grayscale-[0.5]' if not item.available and item.found else '' }}">
                <div class="p-6 sm:w-1/4 flex flex-col justify-center items-start border-b sm:border-b-0 sm:border-r border-gray-100 bg-gray-50/50">
                    <div class="flex items-center gap-3 mb-2">
                        <img src="https://www.google.com/s2/favicons?domain={{ item.domain }}&sz=32" alt="icon" class="w-6 h-6 rounded-sm shadow-sm">
                        <span class="font-bold text-gray-800 text-lg">{{ item.shop_name }}</span>
                    </div>
                    {% if item == best %}<span class="bg-green-100 text-green-700 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wide border border-green-200 shadow-sm">Najtaniej</span>{% endif %}
                </div>
                <div class="p-6 sm:w-2/4 flex flex-col justify-center">
                    {% if item.found %}
                        <h3 class="font-semibold text-gray-800 text-lg leading-tight mb-3">{{ item.product_name }}</h3>
                        <div class="flex flex-wrap gap-2">
                            {% if item.available %}
                                <div class="text-xs text-green-700 bg-green-50 px-2 py-1 rounded font-semibold border border-green-200 flex items-center gap-1"><i class="fa-solid fa-check-circle"></i> Produkt dostępny</div>
                            {% else %}
                                <div class="text-xs text-red-700 bg-red-50 px-2 py-1 rounded font-semibold border border-red-200 flex items-center gap-1"><i class="fa-solid fa-ban"></i> Niedostępny / Brak</div>
                            {% endif %}
                        </div>
                    {% else %}
                        <div class="text-gray-400 italic flex items-center gap-2"><i class="fa-solid fa-circle-xmark text-gray-300"></i><span>{{ item.product_name }}</span></div>
                        {% if item.error %}<p class="text-xs text-red-300 mt-1 pl-6">{{ item.error }}</p>{% endif %}
                    {% endif %}
                </div>
                <div class="p-6 sm:w-1/4 flex flex-col justify-center items-end bg-gray-50/30">
                    {% if item.found %}
                        <span class="text-3xl font-bold text-gray-900 mb-3 tracking-tight">{{ "%.2f"|format(item.price) }} zł</span>
                        {% if item.available %}
                            <a href="{{ item.link }}" target="_blank" class="w-full sm:w-auto text-center bg-white border border-gray-300 hover:border-indigo-600 hover:text-indigo-600 text-gray-700 font-semibold py-2 px-6 rounded-lg transition shadow-sm hover:shadow text-sm group">Idź do sklepu</a>
                        {% else %}
                             <span class="w-full sm:w-auto text-center bg-gray-100 text-gray-400 border border-gray-200 font-semibold py-2 px-6 rounded-lg text-sm cursor-not-allowed">Wyprzedany</span>
                        {% endif %}
                    {% else %}
                        <span class="text-gray-300 font-bold text-xl mb-2">---</span>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
    {% endif %}
</div>
"""

HTML_SHOPS = """
<div class="max-w-4xl mx-auto">
    <div class="flex justify-between items-center mb-8">
        <h1 class="text-3xl font-bold text-gray-900">Sklepy</h1>
        <button onclick="document.getElementById('addShopForm').classList.toggle('hidden')" class="bg-indigo-600 text-white px-5 py-2.5 rounded-lg hover:bg-indigo-700 font-medium flex items-center gap-2"><i class="fa-solid fa-plus"></i> Dodaj Sklep</button>
    </div>
    <div class="grid grid-cols-1 gap-4">
        {% for shop in shops %}
        <div class="bg-white p-5 rounded-xl shadow-sm border border-gray-200 flex justify-between items-center transition hover:shadow-md">
            <div class="flex items-center gap-4">
                <div class="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center"><img src="https://www.google.com/s2/favicons?domain={{ shop.domain }}&sz=32" alt="icon" class="w-6 h-6"></div>
                <div><h3 class="font-bold text-gray-800 text-lg">{{ shop.name }}</h3><a href="https://{{ shop.domain }}" target="_blank" class="text-sm text-indigo-500 hover:underline">{{ shop.domain }}</a></div>
            </div>
            <a href="/shops/delete/{{ loop.index0 }}" class="text-gray-400 hover:text-red-500 p-2 transition" onclick="return confirm('Usunąć?')"><i class="fa-solid fa-trash-can text-lg"></i></a>
        </div>
        {% endfor %}
    </div>
    <div id="addShopForm" class="hidden mt-8 bg-white p-8 rounded-2xl shadow-xl border border-gray-100">
        <form action="/shops/add" method="POST" class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <input type="text" name="name" placeholder="Nazwa" class="border p-3 rounded-lg" required>
            <input type="text" name="domain" placeholder="Domena" class="border p-3 rounded-lg" required>
            <input type="text" name="search_url" placeholder="URL {query}" class="border p-3 rounded-lg md:col-span-2" required>
            <input type="text" name="item_selector" placeholder="Item Selector" class="border p-3 rounded-lg" required>
            <input type="text" name="title_selector" placeholder="Title Selector" class="border p-3 rounded-lg" required>
            <input type="text" name="link_selector" placeholder="Link Selector" class="border p-3 rounded-lg" required>
            <input type="text" name="price_selector" placeholder="Price Selector" class="border p-3 rounded-lg" required>
            <button type="submit" class="md:col-span-2 bg-indigo-600 text-white font-bold py-3 rounded-lg">Zapisz</button>
        </form>
    </div>
</div>
"""

# --- ROUTING ---

@app.route('/')
def home():
    shops = load_shops()
    inner_html = render_template_string(HTML_HOME, shop_count=len(shops))
    return render_template_string(HTML_BASE, active='home', content=inner_html)

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query')
    shops = load_shops()
    results = []
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_shop, shop, query) for shop in shops]
        for future in futures:
            results.append(future.result())
            
    inner_html = render_template_string(HTML_HOME, shop_count=len(shops), query=query, results=results)
    return render_template_string(HTML_BASE, active='home', content=inner_html)

@app.route('/shops')
def shops_list():
    shops = load_shops()
    inner_html = render_template_string(HTML_SHOPS, shops=shops)
    return render_template_string(HTML_BASE, active='shops', content=inner_html)

@app.route('/shops/add', methods=['POST'])
def add_shop():
    new_shop = {
        "name": request.form.get('name'),
        "domain": request.form.get('domain'),
        "search_url": request.form.get('search_url'),
        "item_selector": request.form.get('item_selector'),
        "title_selector": request.form.get('title_selector'),
        "link_selector": request.form.get('link_selector'),
        "price_selector": request.form.get('price_selector'),
        "stock_check_class": request.form.get('stock_check_class'), # Opcjonalnie
        "price_type": "text"
    }
    shops = load_shops()
    shops.append(new_shop)
    save_shops(shops)
    return redirect('/shops')

@app.route('/shops/delete/<int:index>')
def delete_shop(index):
    shops = load_shops()
    if 0 <= index < len(shops):
        del shops[index]
        save_shops(shops)
    return redirect('/shops')

if __name__ == '__main__':
    # Wymuszamy aktualizację pliku konfiguracyjnego, 
    # aby nowe ustawienia sklepów (URL-e, klasy) weszły w życie
    if os.path.exists(SHOPS_FILE):
        os.remove(SHOPS_FILE) 
        
    print("Uruchamianie PokeCena Search Engine v2.8 (Full Fixed Config)...")
    app.run(debug=True, port=5000)
