import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
}

DEFAULT_SHOPS = [
    {
        "name": "BoosterPoint",
        "domain": "boosterpoint.pl",
        "search_url": "https://boosterpoint.pl/wszystkie-produkty/?s={query}&post_type=product&ct_product_price=1",
        "item_selector": ".product", 
        "title_selector": ".woocommerce-loop-product__title",
        "link_selector": ".woocommerce-loop-product__link",
        "price_selector": ".price ins .amount bdi, .price .amount bdi",
        "price_type": "text",
        "stock_check_class": "outofstock" 
    },
    {
        "name": "LootQuest",
        "domain": "lootquest.pl",
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
        "item_selector": ".grid-product__wrap-inner",
        "title_selector": ".grid-product__title-inner",
        "link_selector": "a.grid-product__link", 
        "price_selector": ".details-product-price__value",
        "price_type": "text"
    },
    {
        "name": "PokeShop",
        "domain": "pokeshop.pl",
        "search_url": "https://pokeshop.pl/szukaj.html/szukaj={query}",
        "item_selector": ".Okno", 
        "title_selector": ".ProdCena h3 a",
        "link_selector": ".ProdCena h3 a",
        "price_selector": ".CenaAktualna",
        "price_type": "text"
    },
    {
        "name": "TCG Love",
        "domain": "tcglove.pl",
        "search_url": "https://www.tcglove.pl/pl/searchquery/{query}/1/full/5?url={query_commas}",
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

def clean_price(text):
    if not text: return 0.0
    clean = re.sub(r'[^\d,.]', '', str(text))
    clean = clean.replace(',', '.')
    try:
        val = float(clean.strip('.'))
        return val
    except ValueError:
        return 0.0

def make_search_url(url_template, query):
    query_plus = urllib.parse.quote_plus(query)
    query_commas = urllib.parse.quote(query.replace(" ", ","))
    url = url_template.replace("{query}", query_plus)
    url = url.replace("{query_commas}", query_commas)
    return url

def is_valid_match(title, query):
    title_lower = title.lower()
    query_lower = query.lower()
    
    query_words = query_lower.split()
    significant_words = [w for w in query_words if len(w) > 2]
    
    if significant_words:
        matches = 0
        for word in significant_words:
            if word in title_lower:
                matches += 1
        if matches < len(significant_words) * 0.5:
             return False, "Nie pasuje do nazwy"

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
        resp_search = requests.get(search_url, headers=HEADERS, timeout=15)
        
        if resp_search.status_code != 200:
            result['error'] = f"Błąd HTTP {resp_search.status_code}"
            return result

        soup = BeautifulSoup(resp_search.content.decode('utf-8', 'ignore'), 'html.parser')
        
        item_selector = shop.get('item_selector')
        items = []
        
        if item_selector:
            items = soup.select(item_selector)
        else:
            link_el = soup.select_one(shop['link_selector'])
            if link_el: items = [link_el.parent]

        if not items:
            return result 

        for item in items[:6]:
            title_selector = shop.get('title_selector', shop['link_selector'])
            title_el = item.select_one(title_selector)
            if not title_el: continue
            
            title_text = title_el.get_text(strip=True)
            
            is_valid, msg = is_valid_match(title_text, query)
            if not is_valid: continue
            
            link_el = item.select_one(shop['link_selector'])
            if not link_el and item.name == 'a': link_el = item
            if not link_el: link_el = item.find('a')
            if not link_el or not link_el.has_attr('href'): continue
            
            product_url = link_el['href']
            if not product_url.startswith("http"):
                base_domain = shop['domain']
                path = product_url.lstrip('/')
                product_url = f"https://{base_domain}/{path}"
            
            is_available = True
            stock_class = shop.get('stock_check_class')
            if stock_class:
                item_classes = item.get('class', [])
                if stock_class in item_classes:
                    is_available = False
                elif item.select_one(f".{stock_class}"):
                    is_available = False

            try:
                # Check product page details if necessary, or rely on list
                # For now, scraping product page for price accuracy as per original script
                # NOTE: This adds latency.
                resp_product = requests.get(product_url, headers=HEADERS, timeout=10)
                if resp_product.status_code == 200:
                    soup_product = BeautifulSoup(resp_product.content.decode('utf-8', 'ignore'), 'html.parser')
                    
                    if shop.get('stock_selector'):
                        oos_el = soup_product.select_one(shop['stock_selector'])
                        if oos_el: is_available = False
                    
                    if is_available:
                        text_content = soup_product.get_text().lower()
                        if "brak w magazynie" in text_content or "produkt niedostępny" in text_content:
                            pass # Warning: this check is heuristic

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

def search_polish_prices(query: str):
    """Search for products in Polish TCG shops."""
    shops = DEFAULT_SHOPS
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_shop, shop, query) for shop in shops]
        for future in futures:
            try:
                res = future.result()
                results.append(res)
            except Exception as e:
                logger.error(f"Error in search thread: {e}")
    return results
