# Praktyczny przewodnik po tworzeniu produktów w API Shoper

API Shoper REST umożliwia automatyczne tworzenie i zarządzanie produktami w sklepie, ale wymaga precyzyjnego zrozumienia struktury danych i prawidłowej kolejności operacji. **Stock musi być obiektem, nie tablicą** - to najczęstszy błąd powodujący niepowodzenia. Token dostępu jest ważny przez 90 dni, więc jedna autoryzacja wystarcza na trzy miesiące pracy, a system wspiera wielojęzyczność poprzez obiekt translations.

## Kompletny proces tworzenia produktu krok po kroku

Proces tworzenia produktu w API Shoper składa się z czterech podstawowych kroków wykonywanych w określonej kolejności. Najpierw musisz uzyskać token autoryzacyjny, następnie stworzyć podstawowy produkt z wymaganymi polami, a dopiero potem możesz dodawać do niego obrazy i atrybuty.

**Krok 1: Autoryzacja i uzyskanie tokena**

Zanim wykonasz jakiekolwiek operacje, musisz utworzyć użytkownika WebAPI w panelu administracyjnym Shoper. Przejdź do Konfiguracja → Administracja, system i stwórz nową grupę z typem "Dostęp do WebAPI". Ustaw odpowiednie uprawnienia (odczyt, zapis dla produktów), a następnie dodaj konto administratora w tej grupie.

```python
import requests

# Inicjalizacja sesji
session = requests.Session()

# Pobranie tokena dostępu
response = session.post(
    'https://twoj-sklep.shoparena.pl/webapi/rest/auth',
    auth=('twoj_login', 'twoje_haslo')
)

result = response.json()
token = result['access_token']  # Ważny przez 2592000 sekund (90 dni)

# Dodanie tokena do nagłówków sesji
session.headers.update({'Authorization': f'Bearer {token}'})
```

Token dostępu (`access_token`) jest ważny przez 90 dni, a token odświeżający (`refresh_token`) przez 180 dni. Nie musisz autoryzować się przy każdym żądaniu - przechowuj token bezpiecznie i używaj go przez cały okres ważności.

**Krok 2: Przygotowanie struktury danych produktu**

Kluczowe jest zrozumienie, że `stock` jest obiektem (nie tablicą), `options` jest tablicą wariantów produktu, a `translations` to słownik z tłumaczeniami dla różnych języków. Oto kompletna struktura z wszystkimi wymaganymi polami:

```json
{
  "category_id": 18,
  "unit_id": 1,
  "currency_id": 1,
  "code": "PROD-001",
  "pkwiu": "123456",
  "translations": {
    "pl_PL": {
      "name": "Przykładowy produkt",
      "description": "Szczegółowy opis produktu",
      "active": true
    }
  },
  "stock": {
    "price": 99.99,
    "stock": 100,
    "availability_id": 8,
    "delivery_id": 1
  },
  "options": [{
    "price": 99.99,
    "active": true,
    "stock": 100
  }]
}
```

**Krok 3: Utworzenie produktu przez API**

Wyślij żądanie POST do endpointu `/webapi/rest/products` z przygotowanymi danymi. API zwróci ID nowo utworzonego produktu, którego będziesz potrzebować do dodania obrazów i atrybutów.

```python
# Utworzenie produktu
product_data = {
    "category_id": 18,
    "unit_id": 1,
    "currency_id": 1,
    "code": "PROD-001",
    "translations": {
        "pl_PL": {
            "name": "Mój produkt",
            "description": "Opis produktu",
            "active": True
        }
    },
    "stock": {
        "price": 99.99,
        "stock": 100.0,
        "availability_id": 8,
        "delivery_id": 1
    },
    "options": [{
        "price": 99.99,
        "active": True,
        "stock": 100.0
    }]
}

response = session.post(
    'https://twoj-sklep.shoparena.pl/webapi/rest/products',
    json=product_data
)

# Zapisz ID produktu do dalszych operacji
product_id = response.json()['product_id']
```

**Krok 4: Dodanie obrazów do produktu**

Po utworzeniu produktu możesz dodać do niego obrazy używając endpointu `/webapi/rest/product-images`. Każdy obraz wymaga referencji do ID produktu i może być oznaczony jako główny.

```python
# Dodanie obrazu produktu
image_data = {
    "product_id": product_id,
    "url": "https://example.com/images/product.jpg",
    "main": True,
    "order": 1
}

response = session.post(
    'https://twoj-sklep.shoparena.pl/webapi/rest/product-images',
    json=image_data
)
```

**Krok 5: Dodanie atrybutów do produktu**

Atrybuty dodaje się osobno po utworzeniu produktu, używając dedykowanego endpointu lub metody `product.attributes.save`. Atrybuty są zorganizowane jako słownik, gdzie klucze to ID grup atrybutów, a wartości to kolejne słowniki z ID atrybutów i ich wartościami.

## Dodawanie atrybutów: POST vs PUT - różnice i zastosowanie

Różnica między POST a PUT w kontekście atrybutów produktu dotyczy tego, czy tworzysz nowe przypisanie atrybutu, czy aktualizujesz istniejące. **POST służy do pierwszego przypisania atrybutów** do produktu, podczas gdy **PUT aktualizuje już istniejące wartości** atrybutów.

W praktyce, API Shoper używa dedykowanej metody `product.attributes.save`, która automatycznie wykrywa, czy atrybuty istnieją i należy je zaktualizować, czy też trzeba je utworzyć od zera. Kluczowy jest parametr `force: true`, który wymusza nadpisanie istniejących wartości.

```javascript
// Przykład Node.js z biblioteką shoper-pl
var options = {
  "id": 184,              // ID produktu
  "data": {
    "1": {                // ID grupy atrybutów (np. "Kolor")
      "5": "Czerwony",    // ID atrybutu: wartość
      "6": "Duży"
    },
    "2": {                // Kolejna grupa atrybutów (np. "Material")
      "10": "Bawełna"
    }
  },
  "force": true           // Wymuś nadpisanie istniejących wartości
};

api.product.attributes.save(options)
  .then(function(result) {
    console.log('Atrybuty zapisane:', result);
  });
```

Struktura danych atrybutów może wydawać się skomplikowana, ale jest logiczna: najpierw grupujesz atrybuty według kategorii (kolor, rozmiar, materiał), a następnie w każdej grupie określasz konkretne wartości. Parametr `force: true` jest kluczowy, jeśli chcesz mieć pewność, że twoje zmiany zostaną zastosowane nawet jeśli produkt już ma jakieś atrybuty.

**Kompletny przykład w Python:**

```python
# Najpierw pobierz listę dostępnych atrybutów i ich ID
attributes_response = session.get(
    'https://twoj-sklep.shoparena.pl/webapi/rest/attributes'
)
available_attributes = attributes_response.json()

# Następnie przypisz atrybuty do produktu
attributes_data = {
    "product_id": product_id,
    "attributes": {
        "1": {  # Grupa: Kolor
            "5": "Niebieski",
            "6": "XL"
        }
    }
}

# Aktualizacja produktu z atrybutami (PUT)
response = session.put(
    f'https://twoj-sklep.shoparena.pl/webapi/rest/products/{product_id}',
    json=attributes_data
)
```

## Dodawanie obrazów: metody i zalecane podejście

API Shoper obsługuje dwie główne metody dodawania obrazów do produktów: **przez URL zewnętrzny** (zalecana dla większości przypadków) oraz **przez upload pliku zakodowanego w Base64** (dla mniejszych operacji). Metoda URL jest preferowana przy importach masowych, ponieważ API samo pobiera i przetwarza obrazy.

**Metoda 1: Dodawanie obrazu przez URL (zalecana)**

To najprostszy i najbardziej wydajny sposób. API Shoper pobiera obraz z podanego URL, przetwarza go i zapisuje w systemie. Możesz dodać wiele obrazów do jednego produktu, oznaczając jeden jako główny (`main: true`).

```python
# Dodanie głównego obrazu produktu
main_image = {
    "product_id": product_id,
    "url": "https://example.com/products/prod001-main.jpg",
    "main": True,
    "order": 1
}

response = session.post(
    'https://twoj-sklep.shoparena.pl/webapi/rest/product-images',
    json=main_image
)

# Dodanie dodatkowych obrazów
additional_images = [
    {
        "product_id": product_id,
        "url": "https://example.com/products/prod001-side.jpg",
        "main": False,
        "order": 2
    },
    {
        "product_id": product_id,
        "url": "https://example.com/products/prod001-back.jpg",
        "main": False,
        "order": 3
    }
]

for image in additional_images:
    session.post(
        'https://twoj-sklep.shoparena.pl/webapi/rest/product-images',
        json=image
    )
```

**Metoda 2: Upload przez Base64 (dla małych operacji)**

Jeśli nie masz możliwości udostępnienia obrazów przez URL, możesz wysłać je bezpośrednio jako dane zakodowane w Base64. Ta metoda jest mniej wydajna przy masowych operacjach.

```python
import base64

# Wczytanie i zakodowanie obrazu
with open('product_image.jpg', 'rb') as image_file:
    encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

# Wysłanie obrazu
image_data = {
    "product_id": product_id,
    "data": encoded_image,
    "main": True,
    "order": 1
}

response = session.post(
    'https://twoj-sklep.shoparena.pl/webapi/rest/product-images',
    json=image_data
)
```

**Pobieranie obrazów z API**

Możesz też pobrać listę obrazów produktu, włączając parametr `gfx: true` podczas pobierania danych produktu:

```javascript
var options = {
  "extended": true,
  "translations": true,
  "gfx": true,          // Dołącz obrazy w odpowiedzi
  "attributes": true,
  "products": [30995]
};

api.product_list(options)
  .then(function(productList) {
    console.log(productList);
  });
```

Zalecane praktyki przy dodawaniu obrazów to: optymalizuj rozmiar plików przed uploadem (nie większe niż 2MB), używaj formatów JPG lub PNG, nazywaj pliki w sposób opisowy, a przy masowych importach korzystaj z metody URL i umieszczaj obrazy na szybkim serwerze lub CDN.

## Wymagane pola przy tworzeniu produktu

API Shoper wymaga określonego zestawu pól, aby utworzyć prawidłowy produkt. **Pięć absolutnie wymaganych pól to**: `category_id` (kategoria produktu), `translations` (przynajmniej dla jednego języka), `stock.price` (cena), `unit_id` (jednostka miary), oraz `currency_id` (waluta). Bez tych pól otrzymasz błąd walidacji.

**Pola obowiązkowe (nie mogą być null):**

- **category_id** (integer) - ID kategorii, do której należy produkt. Kategoria musi istnieć w systemie i być aktywna.
- **unit_id** (integer) - ID jednostki miary (np. sztuka, kilogram, metr).
- **currency_id** (integer) - ID waluty cenowej (zwykle 1 dla PLN).
- **translations** (object) - Obiekt zawierający tłumaczenia dla przynajmniej jednego języka (np. "pl_PL").
  - **translations.pl_PL.name** (string) - Nazwa produktu (wymagana w każdym języku).
  - **translations.pl_PL.active** (boolean) - Czy produkt jest aktywny.
- **stock** (object, NIE tablica!) - Obiekt z informacjami o magazynie i cenie.
  - **stock.price** (float) - Cena produktu (musi być liczbą zmiennoprzecinkową, np. 10.0).
  - **stock.stock** (float) - Stan magazynowy.
- **options** (array) - Tablica wariantów produktu (nawet jeśli produkt nie ma wariantów, tablica musi istnieć).
  - **options[].price** (float) - Cena wariantu.

**Pola opcjonalne ale zalecane:**

- **code** (string) - Kod produktu/SKU, ułatwia identyfikację i zarządzanie.
- **ean** (string) - Kod kreskowy EAN.
- **producer_id** (integer) - ID producenta.
- **producer_code** (string) - Kod producenta.
- **pkwiu** (string) - Kod klasyfikacji PKWiU.
- **weight** (float) - Waga produktu w kilogramach.
- **tax_id** (integer) - ID stawki VAT.
- **delivery_id** (integer) - ID metody dostawy.
- **availability_id** (integer) - ID statusu dostępności.

**Kompletny przykład z wszystkimi wymaganymi polami:**

```csharp
// Przykład C# z RestSharp
Product product = new Product();

// Wymagane podstawowe pola
product.category_id = 18;
product.unit_id = 1;
product.currency_id = 1;
product.code = "PROD-12345";

// Opcje/warianty (TABLICA)
product.options = new List<ProductOptions>();
product.options.Add(new ProductOptions {
    price = 10.0f,      // Float, nie integer!
    active = true,
    stock = 10.0f
});

// Stock (OBIEKT, nie tablica!)
product.stock = new ProductStock();
product.stock.price = 10.0f;
product.stock.stock = 10.0f;
product.stock.availability_id = 8;
product.stock.delivery_id = 1;

// Tłumaczenia (SŁOWNIK)
product.translations = new Dictionary<string, ProductTranslation>();
product.translations.Add("pl_PL", new ProductTranslation {
    name = "Testowy Produkt",
    description = "Opis produktu",
    active = true
});

// Dodanie do żądania
request.AddJsonBody(product);
```

Kluczowe jest zrozumienie typów danych: **stock to obiekt `{}`, nie tablica `[]`**. To najczęściej popełniany błąd. Cena musi być typem float (10.0), nie integer (10). Translations używa kodów języka w formacie język_REGION (np. "pl_PL", "en_US").

## Przykłady kodu pokazujące prawidłowe tworzenie produktu

Poniżej znajdziesz kompletne, działające przykłady w najpopularniejszych językach programowania, pokazujące cały proces od autoryzacji po utworzenie produktu z obrazami i atrybutami.

**Przykład 1: Python z biblioteką requests (kompletny workflow)**

```python
import requests

# Inicjalizacja i autoryzacja
session = requests.Session()
auth_response = session.post(
    'https://sklep12345.shoparena.pl/webapi/rest/auth',
    auth=('api_user', 'api_password')
)
token = auth_response.json()['access_token']
session.headers.update({
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
})

# Przygotowanie danych produktu
product = {
    "category_id": 18,
    "unit_id": 1,
    "currency_id": 1,
    "code": "LAPTOP-001",
    "ean": "5901234567890",
    "producer_id": 5,
    "weight": 2.5,
    "translations": {
        "pl_PL": {
            "name": "Laptop Dell XPS 15",
            "description": "<p>Wydajny laptop do pracy i rozrywki</p>",
            "active": True
        },
        "en_US": {
            "name": "Dell XPS 15 Laptop",
            "description": "<p>Powerful laptop for work and entertainment</p>",
            "active": True
        }
    },
    "stock": {
        "price": 4999.99,
        "stock": 25.0,
        "availability_id": 8,
        "delivery_id": 1
    },
    "options": [{
        "price": 4999.99,
        "active": True,
        "stock": 25.0
    }]
}

# Utworzenie produktu
create_response = session.post(
    'https://sklep12345.shoparena.pl/webapi/rest/products',
    json=product
)

if create_response.status_code == 200 or create_response.status_code == 201:
    product_id = create_response.json()['product_id']
    print(f"Produkt utworzony, ID: {product_id}")
    
    # Dodanie obrazów
    images = [
        {
            "product_id": product_id,
            "url": "https://cdn.example.com/laptop-front.jpg",
            "main": True,
            "order": 1
        },
        {
            "product_id": product_id,
            "url": "https://cdn.example.com/laptop-side.jpg",
            "main": False,
            "order": 2
        }
    ]
    
    for image in images:
        img_response = session.post(
            'https://sklep12345.shoparena.pl/webapi/rest/product-images',
            json=image
        )
        print(f"Obraz dodany: {img_response.status_code}")
    
    print("Produkt utworzony kompletnie z obrazami!")
else:
    print(f"Błąd: {create_response.status_code}")
    print(create_response.json())
```

**Przykład 2: TypeScript z biblioteką shoper-ts (nowoczesne API)**

```typescript
import { Client, AuthMethod } from "shoper-ts";

const client = new Client({
  shop_url: "https://sklep12345.shoparena.pl",
  auth: {
    method: AuthMethod.UserPassword,
    username: "api-user",
    password: "api-password",
  },
});

// Utworzenie produktu z pełną strukturą
async function createProduct() {
  try {
    const newProduct = await client.insert("products", {
      category_id: 18,
      unit_id: 1,
      currency_id: 1,
      code: "PHONE-001",
      ean: "5901234567891",
      translations: {
        "pl_PL": {
          name: "iPhone 15 Pro",
          description: "Najnowszy model iPhone",
          active: true
        }
      },
      stock: {
        price: 5999.0,
        stock: 50.0,
        availability_id: 8,
        delivery_id: 1
      },
      options: [{
        price: 5999.0,
        active: true,
        stock: 50.0
      }]
    });
    
    console.log(`Produkt utworzony: ${newProduct.product_id}`);
    
    // Dodanie obrazu
    await client.insert("product-images", {
      product_id: newProduct.product_id,
      url: "https://cdn.example.com/iphone.jpg",
      main: true,
      order: 1
    });
    
    // Aktualizacja z dodatkowymi danymi
    await client.update("products", newProduct.product_id, {
      producer_id: 10,
      weight: 0.2
    });
    
    console.log("Produkt kompletny!");
    
  } catch (error) {
    console.error("Błąd:", error);
  }
}

createProduct();
```

**Przykład 3: PHP z biblioteką shoper-json-api-php**

```php
<?php
require_once('/path/to/shoper-json-api-php/autoload.php');

try {
    $client = new \Monetivo\ShoperJsonApi('https://sklep12345.shoparena.pl/');
    $client->login('api_user', 'api_password');
    
    // Dane produktu
    $productData = [
        'category_id' => 18,
        'unit_id' => 1,
        'currency_id' => 1,
        'code' => 'WATCH-001',
        'translations' => [
            'pl_PL' => [
                'name' => 'Smartwatch Samsung Galaxy Watch 6',
                'description' => 'Inteligentny zegarek z wieloma funkcjami',
                'active' => true
            ]
        ],
        'stock' => [
            'price' => 1299.99,
            'stock' => 100.0,
            'availability_id' => 8,
            'delivery_id' => 1
        ],
        'options' => [[
            'price' => 1299.99,
            'active' => true,
            'stock' => 100.0
        ]]
    ];
    
    // Utworzenie produktu
    $result = $client->createProduct($productData);
    $productId = $result['product_id'];
    
    echo "Produkt utworzony: " . $productId . "\n";
    
    // Dodanie obrazu
    $imageData = [
        'product_id' => $productId,
        'url' => 'https://cdn.example.com/watch.jpg',
        'main' => true,
        'order' => 1
    ];
    
    $client->addProductImage($imageData);
    
    $client->logout();
    
} catch (\Monetivo\Exceptions\MonetivoException $e) {
    echo "Błąd: " . $e->getMessage();
}
?>
```

**Przykład 4: C# z RestSharp (szczegółowa obsługa błędów)**

```csharp
using RestSharp;
using System;
using System.Collections.Generic;

class ShoperApiExample
{
    static void Main()
    {
        // Autoryzacja
        var client = new RestClient("https://sklep12345.shoparena.pl");
        var authRequest = new RestRequest("/webapi/rest/auth", Method.POST);
        authRequest.AddParameter("client_id", "api_user");
        authRequest.AddParameter("client_secret", "api_password");
        
        var authResponse = client.Execute<Dictionary<string, object>>(authRequest);
        
        if (!authResponse.IsSuccessful)
        {
            Console.WriteLine($"Błąd autoryzacji: {authResponse.ErrorMessage}");
            return;
        }
        
        string token = authResponse.Data["access_token"].ToString();
        Console.WriteLine($"Token: {token}");
        
        // Utworzenie produktu
        var productRequest = new RestRequest("/webapi/rest/products", Method.POST);
        productRequest.AddHeader("Authorization", "Bearer " + token);
        
        var product = new
        {
            category_id = 18,
            unit_id = 1,
            currency_id = 1,
            code = "TABLET-001",
            translations = new Dictionary<string, object>
            {
                {
                    "pl_PL", new
                    {
                        name = "iPad Pro 12.9",
                        description = "Profesjonalny tablet Apple",
                        active = true
                    }
                }
            },
            stock = new
            {
                price = 6999.0,
                stock = 30.0,
                availability_id = 8,
                delivery_id = 1
            },
            options = new[]
            {
                new
                {
                    price = 6999.0,
                    active = true,
                    stock = 30.0
                }
            }
        };
        
        productRequest.AddJsonBody(product);
        var productResponse = client.Execute(productRequest);
        
        if (productResponse.IsSuccessful)
        {
            Console.WriteLine("Produkt utworzony pomyślnie!");
            Console.WriteLine(productResponse.Content);
        }
        else
        {
            Console.WriteLine($"Błąd tworzenia: {productResponse.StatusCode}");
            Console.WriteLine(productResponse.Content);
        }
    }
}
```

Te przykłady pokazują kompletny workflow i można je bezpośrednio adaptować do własnych potrzeb, zmieniając jedynie URL sklepu i dane autoryzacyjne.

## Najczęstsze błędy i jak ich unikać

Podczas pracy z API Shoper deweloperzy napotykają kilka powtarzających się problemów. Zrozumienie ich przyczyn i rozwiązań oszczędza godziny debugowania.

**Błąd #1: "Wartość pola 'price' jest niepoprawna: Pole wymagane"**

To najczęstszy błąd przy tworzeniu produktów. Pojawia się, gdy **stock jest traktowany jako tablica zamiast obiektu** lub gdy pole price jest w niewłaściwym formacie.

```csharp
// ❌ BŁĄD - Stock jako lista/tablica
product.stock = new List<ProductStock>();
product.stock.Add(new ProductStock { price = 20, stock = 20 });

// ✅ PRAWIDŁOWO - Stock jako obiekt
product.stock = new ProductStock();  // Obiekt, nie lista!
product.stock.price = 10.0;          // Float, nie integer!
product.stock.stock = 10.0;
product.stock.availability_id = 8;
product.stock.delivery_id = 1;
```

Musisz odróżnić `{}` (obiekt) od `[]` (tablica/lista). W JSON: `"stock": {...}` jest prawidłowe, a `"stock": [{...}]` spowoduje błąd. Dodatkowo cena musi być liczbą zmiennoprzecinkową (10.0), nie całkowitą (10).

**Błąd #2: "unauthorized_client" lub "Access denied"**

Ten błąd oznacza problemy z autoryzacją - nieprawidłowe przekazanie tokena lub brak uprawnień dla użytkownika WebAPI.

```csharp
// ❌ BŁĄD - Token jako parametr
request.AddParameter("access_token", token);

// ✅ PRAWIDŁOWO - Token w nagłówku Authorization
request.AddHeader("Authorization", "Bearer " + token);
```

Upewnij się, że użytkownik WebAPI ma odpowiednie uprawnienia w panelu administracyjnym Shoper. Przejdź do Konfiguracja → Administracja i sprawdź, czy grupa użytkownika ma zaznaczone uprawnienia do odczytu i zapisu dla produktów.

**Błąd #3: Brakujące wymagane pola**

API zwraca błędy walidacji, gdy brakuje wymaganych pól. Pola oznaczone w dokumentacji jako non-nullable muszą być wypełnione.

```json
{
  "error": "validation_error",
  "message": "Pole wymagane",
  "field": "translations.pl_PL.name"
}
```

Aby zobaczyć szczegółowe błędy walidacji, możesz wywołać endpoint `internals.validation.errors` zaraz po nieudanym żądaniu:

```php
<?php
// Po nieudanym żądaniu pobierz szczegóły błędów
$errors = $client->call('internals.validation.errors', null);
print_r($errors);
?>
```

**Błąd #4: Nieprawidłowa struktura translations**

Tłumaczenia muszą używać właściwego formatu kodu języka: `język_REGION` (np. "pl_PL", "en_US"), nie "pl" czy "en".

```javascript
// ❌ BŁĄD - Nieprawidłowy kod języka
translations: {
  "pl": { name: "Produkt" }  // Nieprawidłowy format
}

// ✅ PRAWIDŁOWO - Pełny kod język_REGION
translations: {
  "pl_PL": { 
    name: "Produkt",
    active: true 
  }
}
```

**Błąd #5: Wygasły token nie jest odświeżany**

Token jest ważny przez 90 dni, ale wiele implementacji próbuje autoryzować się przy każdym żądaniu, co jest niepotrzebne i nieefektywne.

```python
# ✅ PRAWIDŁOWE podejście - przechowywanie i odświeżanie tokena
class ShoperClient:
    def __init__(self, shop_url, login, password):
        self.shop_url = shop_url
        self.login = login
        self.password = password
        self.token = None
        self.token_expires = None
    
    def get_token(self):
        # Sprawdź czy token jest ważny
        if self.token and self.token_expires > time.time():
            return self.token
        
        # Jeśli nie, pobierz nowy
        response = requests.post(
            f'{self.shop_url}/webapi/rest/auth',
            auth=(self.login, self.password)
        )
        result = response.json()
        self.token = result['access_token']
        self.token_expires = time.time() + result['expires_in']
        
        return self.token
```

**Błąd #6: Niewłaściwy ID kategorii lub referencje**

Wszystkie ID (category_id, unit_id, producer_id, etc.) muszą odnosić się do istniejących zasobów w systemie Shoper.

```python
# ✅ Sprawdź dostępne kategorie przed utworzeniem produktu
categories_response = session.get(
    'https://sklep.pl/webapi/rest/categories'
)
categories = categories_response.json()
print("Dostępne kategorie:", categories)

# Użyj prawidłowego ID z listy
product['category_id'] = categories['list'][0]['category_id']
```

**Lista kontrolna przed wysłaniem żądania:**

1. ✓ Stock jest obiektem `{}`, nie tablicą `[]`
2. ✓ Pole price jest float (10.0), nie int (10)
3. ✓ Translations używa formatu "pl_PL", nie "pl"
4. ✓ Token w nagłówku: `Authorization: Bearer <token>`
5. ✓ Wszystkie wymagane pola są wypełnione
6. ✓ ID kategorii, jednostki, waluty istnieją w systemie
7. ✓ Options jest tablicą, nawet jeśli zawiera jeden element

**Debugowanie błędów - praktyczne podejście:**

```python
def create_product_with_error_handling(session, product_data):
    try:
        response = session.post(
            'https://sklep.pl/webapi/rest/products',
            json=product_data
        )
        
        # Loguj pełny request i response
        print("Request:", product_data)
        print("Status:", response.status_code)
        print("Response:", response.json())
        
        if response.status_code >= 400:
            # Pobierz szczegółowe błędy walidacji
            errors_response = session.get(
                'https://sklep.pl/webapi/rest/internals/validation/errors'
            )
            print("Błędy walidacji:", errors_response.json())
            return None
        
        return response.json()['product_id']
        
    except Exception as e:
        print(f"Wyjątek: {str(e)}")
        return None
```

Kluczem do uniknięcia problemów jest **dokładna walidacja danych przed wysłaniem**, **przechowywanie i logowanie pełnych request/response** podczas testowania, oraz **zrozumienie różnicy między obiektami a tablicami** w strukturze JSON. Token powinien być przechowywany bezpiecznie i odświeżany dopiero po wygaśnięciu, a wszystkie ID muszą odnosić się do rzeczywiście istniejących zasobów w sklepie.

## Podsumowanie i najlepsze praktyki

API Shoper REST wymaga precyzyjnego podejścia do struktury danych, ale po zrozumieniu podstawowych zasad staje się potężnym narzędziem do automatyzacji. Kluczowe zasady to: stock jako obiekt (nie tablica), ceny jako float, wielojęzyczność przez translations z kodami "język_REGION", oraz właściwe zarządzanie tokenem ważnym przez 90 dni. Proces tworzenia produktu składa się z czterech kroków: autoryzacja, utworzenie produktu z wymaganymi polami, dodanie obrazów przez URL lub Base64, oraz przypisanie atrybutów z parametrem force:true. Najczęstsze błędy wynikają z niewłaściwej struktury obiektu stock, błędnego przekazywania tokena, lub brakujących wymaganych pól - wszystkie łatwo uniknąć przez walidację przed wysłaniem i dokładne logowanie response. Społeczność deweloperów stworzyła dojrzałe biblioteki klienckie w Pythonie, Node.js, TypeScript, PHP i C#, które upraszczają integrację i zawierają gotowe przykłady implementacji.