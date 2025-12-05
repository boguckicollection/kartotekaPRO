# **Raport Techniczny: Kompleksowa Integracja Systemu Kartoteka 2.0 z API REST Furgonetka.pl**

## **Streszczenie Wykonawcze**

Niniejszy dokument stanowi wyczerpujące studium techniczne i architektoniczne, mające na celu przeprowadzenie zespołu deweloperskiego aplikacji "Kartoteka 2.0" przez proces integracji z systemem logistycznym Furgonetka.pl. Raport został przygotowany w odpowiedzi na zapotrzebowanie klienta biznesowego, posiadającego aktywny sklep na platformie Shoper połączony z kontem Furgonetka, który dąży do automatyzacji procesu generowania i drukowania listów przewozowych bezpośrednio z poziomu własnej aplikacji zarządzającej.

Analiza obejmuje pełne spektrum zagadnień: od protokołów uwierzytelniania OAuth 2.0, przez konstrukcję skomplikowanych struktur danych JSON reprezentujących przesyłki kurierskie, aż po fizyczną realizację wydruku etykiet w formacie PDF i ZPL. Szczególny nacisk położono na specyfikę polskiego rynku e-commerce, w tym obsługę Paczkomatów InPost, punktów odbioru (PUDO) oraz integrację danych pochodzących z platformy Shoper. Opracowanie to wykracza poza standardową dokumentację, oferując analizę przypadków brzegowych, strategii obsługi błędów oraz optymalizacji procesów magazynowych, co czyni je kompletnym przewodnikiem wdrożeniowym dla środowiska produkcyjnego Kartoteka 2.0.

## ---

**1\. Wstęp i Kontekst Strategiczny Integracji**

Współczesna logistyka e-commerce nie opiera się już wyłącznie na transporcie towarów z punktu A do punktu B, lecz na błyskawicznej wymianie danych pomiędzy systemami sprzedaży (ERP/WMS), brokerami kurierskimi a fizyczną infrastrukturą przewoźników. Dla aplikacji takiej jak Kartoteka 2.0, która pełni rolę nadrzędnego systemu zarządzania dla sklepu internetowego opartego o silnik Shoper, bezpośrednia integracja z API Furgonetka.pl jest krokiem milowym w stronę automatyzacji operacyjnej.

### **1.1 Rola Middleware w Ekosystemie Logistycznym**

Furgonetka.pl w tym układzie pełni rolę brokera usług oraz agregatora technologicznego. Zamiast budować oddzielne integracje z API DPD, DHL, InPost czy Poczta Polska, Kartoteka 2.0 komunikuje się z jednym, ustandaryzowanym interfejsem REST API Furgonetki. To podejście drastycznie redukuje dług technologiczny i koszty utrzymania. Kluczowym wyzwaniem, które ten raport adresuje, jest przełożenie logiki biznesowej Kartoteki 2.0 na uniwersalny język API Furgonetki, przy jednoczesnym zachowaniu spójności z danymi znajdującymi się w platformie Shoper.

### **1.2 Cel Biznesowy i Techniczny**

Nadrzędnym celem jest umożliwienie operatorowi Kartoteki 2.0 kliknięcia przycisku "Drukuj etykietę" przy zamówieniu, co w tle uruchomi kaskadę procesów: walidację adresu, utworzenie przesyłki w systemie przewoźnika, pobranie pliku z etykietą i przesłanie go na urządzenie drukujące. Eliminacja konieczności logowania się do panelu Furgonetki czy Shopera w celu ręcznego generowania listów przewozowych przełoży się na znaczną oszczędność czasu i redukcję błędów ludzkich.1

## ---

**2\. Architektura Ekosystemu: Kartoteka 2.0, Shoper i Furgonetka**

Zrozumienie przepływu danych w trójstronnym układzie (Kartoteka 2.0 \- Shoper \- Furgonetka) jest kluczowe dla uniknięcia duplikacji danych i błędów synchronizacji.

### **2.1 Istniejące Połączenie Shoper-Furgonetka**

Użytkownik wskazał, że konto Furgonetka jest już połączone ze sklepem Shoper. Oznacza to, że Furgonetka posiada mechanizmy (prawdopodobnie cykliczne zadania typu cron lub webhooki), które importują zamówienia ze Shopera do panelu Furgonetki jako "zamówienia do realizacji".1

**Implikacje dla Kartoteki 2.0:**

1. **Ryzyko Duplikacji:** Jeśli Kartoteka 2.0 utworzy nową przesyłkę na podstawie danych lokalnych, a Furgonetka zaimportuje to samo zamówienie ze Shopera, w panelu mogą pojawić się dwa byty dotyczące tej samej transakcji.  
2. **Strategia Mapowania:** Kartoteka 2.0 powinna wykorzystywać pole user\_reference\_number (numer referencyjny użytkownika) w API Furgonetki, wpisując tam numer zamówienia ze Shopera (np. \#12345). Systemy Furgonetki często potrafią sparować ręcznie utworzoną przesyłkę z zaimportowanym zamówieniem, jeśli numery referencyjne są zgodne, co automatycznie zmieni status zamówienia w Shoperze na "Wysłane".2

### **2.2 Topologia Połączenia API**

Integracja będzie opierać się na architekturze REST (Representational State Transfer). Kartoteka 2.0 będzie pełnić rolę klienta HTTP, inicjując żądania do serwerów Furgonetki.

| Komponent | Rola | Odpowiedzialność |
| :---- | :---- | :---- |
| **Kartoteka 2.0** | Klient API | Inicjacja procesu, przechowywanie tokenów, interfejs użytkownika, drukowanie. |
| **Furgonetka API** | Gateway | Autoryzacja, walidacja danych, routing do przewoźników, generowanie PDF/ZPL. |
| **Shoper** | Źródło Danych | Oryginalne źródło zamówień, adresów i produktów. |
| **Przewoźnik (np. InPost)** | Wykonawca | Fizyczny transport, generowanie statusów śledzenia. |

## ---

**3\. Protokoły Bezpieczeństwa i Autoryzacja OAuth 2.0**

Bezpieczeństwo dostępu do API jest fundamentem stabilnej integracji. Furgonetka wykorzystuje standard OAuth 2.0, który jest obecnie przemysłowym standardem delegowania uprawnień.3 Dla aplikacji "Kartoteka 2.0" posiadającej Client ID, proces ten musi zostać zaimplementowany z najwyższą starannością.

### **3.1 Mechanizm OAuth 2.0 i Wybór Grant Type**

W dokumentacji Furgonetki wymieniane są trzy główne typy autoryzacji (Grant Types) 3:

1. **Authorization Code:** Wymaga interakcji użytkownika (przekierowania do przeglądarki). Jest to najbezpieczniejsza metoda, zalecana, gdy aplikacja ma wielu użytkowników logujących się na własne konta Furgonetki.  
2. **Client Credentials:** Używany do komunikacji maszyna-maszyna, gdzie aplikacja działa we własnym imieniu.  
3. **Password (Resource Owner Password Credentials):** Wymaga przesłania loginu i hasła użytkownika bezpośrednio przez aplikację. Choć prosty, jest odradzany ze względów bezpieczeństwa, chyba że aplikacja jest wysoce zaufana.

Biorąc pod uwagę, że "Kartoteka 2.0" jest aplikacją zarządzającą sklepem (Backend/Backoffice) i posiada już Client ID dla środowiska produkcyjnego, najbardziej prawdopodobnym i rekomendowanym scenariuszem dla trwałej integracji jest **Authorization Code Flow** z trwałym przechowywaniem tokenów odświeżających (Refresh Tokens).

### **3.2 Implementacja Procesu "Handshake" (Uścisk Dłoni)**

Proces nawiązywania połączenia składa się z kilku kroków, które muszą zostać obsłużone przez kod aplikacji Kartoteka 2.0.

#### **Krok 1: Uzyskanie Kodu Autoryzacyjnego (Code)**

Aplikacja musi wygenerować link i otworzyć go operatorowi (lub przekierować go), aby ten zalogował się w Furgonetce i potwierdził uprawnienia aplikacji.

**URL Żądania:**

HTTP

GET https://api.furgonetka.pl/oauth/authorize?response\_type=code\&client\_id=\&redirect\_uri=\&scope=api

* client\_id: Identyfikator dostarczony w danych autoryzacyjnych aplikacji.  
* redirect\_uri: Adres zwrotny w Twojej aplikacji (musi być identyczny z tym podanym przy rejestracji aplikacji w Furgonetce).  
* scope: Zakres uprawnień, standardowo api.

Po zatwierdzeniu przez użytkownika, Furgonetka przekieruje przeglądarkę na redirect\_uri z parametrem code, np.: https://twoja-aplikacja.pl/callback?code=SplxlOBeZQQYbYS6WxSbIA. Kod ten jest ważny bardzo krótko (zazwyczaj 30 sekund).3

#### **Krok 2: Wymiana Kodu na Token Dostępu (Access Token)**

Backend Kartoteki 2.0 musi natychmiast wymienić otrzymany kod na tokeny.

**Żądanie POST:**

HTTP

POST https://api.furgonetka.pl/oauth/token  
Authorization: Basic  
Content-Type: application/x-www-form-urlencoded

grant\_type=authorization\_code  
\&code=  
\&redirect\_uri=

**Nagłówek Authorization:** Jest to kluczowy element. Należy połączyć ciąg znaków Client ID, dwukropek : oraz Client Secret, a następnie zakodować całość algorytmem Base64. Wynik wstawiamy po słowie Basic .3

**Odpowiedź Serwera (Sukces 200 OK):**

JSON

{  
  "access\_token": "eyJ0eXAiOiJKV1QiLCJhbG...",  
  "token\_type": "Bearer",  
  "expires\_in": 2592000,  
  "refresh\_token": "def50200..."  
}

### **3.3 Strategia Zarządzania Cyklem Życia Tokena**

Analiza odpowiedzi serwera ujawnia krytyczne parametry operacyjne:

* access\_token: Klucz do API, ważny zazwyczaj 30 dni (expires\_in: 2592000 sekund).3  
* refresh\_token: Klucz odnawiania, ważny znacznie dłużej (do 3 miesięcy).

**Błąd Krytyczny w Implementacjach:** Częstym błędem jest zakładanie, że token jest wieczny. Kartoteka 2.0 **musi** zaimplementować mechanizm "Token Refresh".

#### **Algorytm Odświeżania Tokena:**

1. Aplikacja przechowuje w bazie danych: access\_token, refresh\_token oraz expiration\_date (wyliczone jako teraz \+ expires\_in).  
2. Przed każdym zapytaniem do API, aplikacja sprawdza, czy expiration\_date nie minęła (lub minie w ciągu najbliższej godziny).  
3. Alternatywnie, aplikacja nasłuchuje na kod błędu HTTP **401 Unauthorized**.4  
4. W przypadku wygaśnięcia, wysyłane jest żądanie odświeżenia:

HTTP

POST https://api.furgonetka.pl/oauth/token  
Authorization: Basic  
Content-Type: application/x-www-form-urlencoded

grant\_type=refresh\_token  
\&refresh\_token=

Wynikiem jest nowa para tokenów, którą należy nadpisać w bazie danych. Stary refresh\_token staje się nieważny (jest jednorazowy).3 Utrata tokena odświeżającego wymusza ponowne przejście procesu logowania przez użytkownika.

## ---

**4\. Modelowanie Danych Logistycznych**

Przed wysłaniem pierwszego żądania utworzenia przesyłki, Kartoteka 2.0 musi dokonać transformacji danych ze swojego modelu wewnętrznego (lub modelu Shopera) na model wymagany przez API Furgonetki. Logistyka w Polsce charakteryzuje się specyficznymi wymaganiami walidacyjnymi.

### **4.1 Standaryzacja Adresów**

Interfejs API Furgonetki jest rygorystyczny w kwestii formatowania danych adresowych. Błędy w tym obszarze są najczęstszą przyczyną odrzuceń żądań (kod 422 Unprocessable Entity).

* **Kod Pocztowy:** Musi być w formacie XX-XXX (np. 00-950). API odrzuci format 00950\. Kartoteka 2.0 powinna posiadać walidator Regex: /^\\d{2}-\\d{3}$/.  
* **Numer Telefonu:** Należy oczyścić numer z prefiksów międzynarodowych (+48), spacji i myślników. API zazwyczaj oczekuje 9 cyfr dla numerów polskich.  
* **Adres Email:** Jest kluczowy dla powiadomień statusowych od przewoźników (np. InPost wysyła kod odbioru na maila i do aplikacji).

### **4.2 Mapowanie Usług Przewoźników (Service Mapping)**

W bazie danych Kartoteki 2.0 metody dostawy (np. "Kurier DPD", "Paczkomaty InPost") muszą zostać zmapowane na techniczne identyfikatory usług Furgonetki. Na podstawie analizy dokumentacji i snippetów 6, oto kluczowe wartości dla pola service:

| Nazwa w Sklepie | Kod Usługi API (service) | Uwagi |
| :---- | :---- | :---- |
| DPD Kurier | dpd | Standardowa usługa kurierska. |
| InPost Paczkomaty | inpost | Wymaga podania pola point (np. WAW01). |
| InPost Kurier | inpostkurier | Doręczenie do drzwi. |
| Poczta Polska Kurier 48 | poczta | Często wymaga doprecyzowania wariantu w usługach dodatkowych. |
| Orlen Paczka | orlen | Wymaga ID punktu PSD. |
| UPS | ups |  |
| GLS | gls |  |
| FedEx | fedex |  |

**Insight:** Wartości te są łańcuchami znaków (string) i muszą być przekazywane dokładnie w takiej formie (małe litery).

### **4.3 Logika "Paczki" (Parcel) vs "Przesyłki" (Package)**

W nomenklaturze API Furgonetki istnieje rozróżnienie:

* **Package (Przesyłka):** Całe zamówienie logistyczne, jeden list przewozowy "główny", jeden odbiorca.  
* **Parcel (Paczka):** Fizyczne pudło. Jedna przesyłka może składać się z wielu paczek (tzw. wielopaczka/multipack).7

Kartoteka 2.0 musi obsługiwać sytuację, w której jedno zamówienie ze Shopera jest pakowane w dwa kartony. W takim przypadku w JSON-ie w tablicy parcels znajdą się dwa obiekty, a system wygeneruje (zazwyczaj) dwie etykiety lub jedną etykietę wieloczęściową.

## ---

**5\. Proces Tworzenia Przesyłki: Inżynieria Payloadu**

Serce integracji stanowi endpoint POST /packages. To tutaj następuje "magia" zamiany danych cyfrowych w zlecenie transportowe. Poniżej przedstawiono szczegółową analizę struktury żądania, uwzględniając najnowsze zmiany w API (np. wersjonowanie v2).8

### **5.1 Struktura Żądania JSON**

Żądanie należy wysłać na adres https://api.furgonetka.pl/packages (lub /packages/v2 jeśli dokumentacja w panelu tak wskazuje \- zalecana weryfikacja dynamiczna).

Poniższy JSON prezentuje pełną strukturę dla typowej przesyłki kurierskiej (InPost Kurier) z pobraniem (COD).

JSON

{  
  "package": {  
    "type": "package",           // Typ obiektu  
    "service": "inpostkurier",   // Kod przewoźnika  
    "user\_reference\_number": "Zamówienie \#10293", // Numer ze Shopera  
    "ref": "Zamówienie \#10293",  // Alternatywne pole referencyjne  
    "send\_date": "2025-05-20",   // Data nadania (planowana)  
      
    "receiver": {  
      "type": "private",         // 'company' lub 'private'  
      "name": "Jan Kowalski",  
      "company": "",             // Opcjonalne dla osób prywatnych  
      "street": "Długa 15/4",  
      "city": "Warszawa",  
      "postcode": "00-123",  
      "phone": "501502503",  
      "email": "jan.kowalski@email.com"  
    },  
      
    "sender": {  
      // Opcjonalne, jeśli zdefiniowane domyślnie na koncie Furgonetki,  
      // ale zalecane dla pewności.  
      "name": "Mój Sklep Internetowy",  
      "street": "Magazynowa 7",  
      "city": "Poznań",  
      "postcode": "60-100",  
      "phone": "618100200",  
      "email": "sklep@mojafirma.pl"  
    },  
      
    "parcels":,  
      
    "services": {  
      "cod": {                   // Usługa pobrania (Cash on Delivery)  
        "amount": 165.50,        // Kwota do pobrania od klienta  
        "currency": "PLN",  
        "account": "12345678901234567890123456" // Nr konta do zwrotu (opcjonalny, jeśli zdefiniowany w panelu)  
      },  
      "insurance": {             // Ubezpieczenie  
        "amount": 150.00         // Kwota ubezpieczenia (często równa wartości towaru)  
      }  
    },  
      
    "pickup": {  
      "type": "courier"          // 'courier' (zamówienie podjazdu) lub 'dropoff' (nadanie w punkcie)  
    }  
  }  
}

### **5.2 Kluczowe Pola i Ich Znaczenie**

1. **user\_reference\_number / ref:** To pole jest "mostem" między Kartoteką 2.0 a Furgonetką. Wpisanie tu numeru zamówienia pozwala na łatwe wyszukiwanie przesyłek w panelu Furgonetki oraz potencjalną automatyczną synchronizację statusów w Shoperze.  
2. **send\_date:** API nie pozwala zazwyczaj na tworzenie przesyłek z datą wsteczną. Jeśli tworzymy etykietę w piątek wieczorem, warto ustawić datę nadania na poniedziałek, aby uniknąć problemów z ważnością etykiety u niektórych przewoźników.  
3. **parcels (Wymiary i Waga):** Furgonetka stosuje walidację tych parametrów. Próba nadania paczki o wadze 50kg do Paczkomatu (limit 25kg) zakończy się błędem API. Kartoteka 2.0 powinna znać limity przewoźników i blokować takie próby po stronie interfejsu użytkownika (UI).  
4. **contents:** Pole często ignorowane, ale krytyczne dla przesyłek międzynarodowych oraz w procesach reklamacyjnych.

### **5.3 Usługi Dodatkowe (Additional Services)**

W sekcji services definiujemy dodatkowe parametry, które wpływają na cenę i proces doręczenia. Oprócz standardowego pobrania (cod) i ubezpieczenia (insurance), API obsługuje flagi takie jak sms\_notification (powiadomienie SMS) czy delivery\_on\_saturday (doręczenie w sobotę \- dostępne tylko dla wybranych usług).

**Walidacja Usług:** Ważne jest, aby nie żądać usług wzajemnie wykluczających się lub niedostępnych dla danego przewoźnika (np. doręczenie na godzinę dla Orlen Paczki). W tym celu rekomendowane jest użycie endpointu walidacyjnego.

### **5.4 Endpoint Walidacji (POST /packages/validate)**

Dobrą praktyką programistyczną jest wstępna weryfikacja danych przed właściwym utworzeniem przesyłki (które może skutkować blokadą środków w portmonetce). Endpoint /packages/validate przyjmuje identyczny payload jak endpoint tworzący, ale zamiast tworzyć przesyłkę, zwraca listę potencjalnych błędów lub potwierdzenie poprawności oraz wycenę.8

## ---

**6\. Specyfika Przewoźników i Obsługa Punktów PUDO**

Polski rynek e-commerce jest zdominowany przez dostawy do punktów (Out-of-Home), co wprowadza dodatkową warstwę komplikacji w integracji.

### **6.1 Paczkomaty InPost i Punkty Odbioru**

Dla usług typu inpost (Paczkomaty), orlen (Orlen Paczka), poczta (Odbiór w Punkcie) czy dpd\_pickup, kluczowym elementem nie jest ulica i numer domu odbiorcy, lecz **identyfikator punktu**.

W JSON-ie, w obiekcie receiver, pole point staje się obowiązkowe.

JSON

"receiver": {  
  "email": "klient@example.com",  
  "phone": "500500500",  
  "point": "WAW22A" // ID Paczkomatu  
}

Skąd wziąć ID punktu?  
Kartoteka 2.0 pobiera dane ze Shopera. W bazie Shopera, dla zamówień z metodą dostawy "Paczkomaty", identyfikator wybranego przez klienta punktu jest zazwyczaj przechowywany w atrybutach zamówienia lub w komentarzu. Aplikacja musi wyekstrahować ten kod (np. KRA01N, PL12345) i przekazać go do API Furgonetki.  
Formaty ID Punktów 6:

* **InPost:** Zawsze ciąg znaków, np. WAW22A.  
* **Poczta Polska:** Często ID numeryczne (PNI), np. 116744\.  
* **DPD:** Często z prefiksem kraju, np. PL11033.  
* **Orlen:** Numer PSD (6 znaków), np. 106088\.

### **6.2 Przesyłki Paletowe i Niestandardowe**

Jeśli sklep oferuje towar gabarytowy, Kartoteka 2.0 musi obsługiwać inny zestaw usług (np. pall-ex lub usługi paletowe DPD/DHL). Wymaga to zmiany struktury parcels – zamiast standardowej paczki, definiuje się typ opakowania jako paletę (np. EURO).9

## ---

**7\. Zarządzanie Etykietami i Infrastruktura Druku**

Celem nadrzędnym użytkownika jest "drukowanie listów przewozowych". W kontekście API oznacza to pobranie pliku z etykietą i przesłanie go na urządzenie drukujące.

### **7.1 Pobieranie Etykiety (Endpoint GET)**

Po pomyślnym utworzeniu przesyłki (HTTP 200 OK), w odpowiedzi API otrzymamy package\_id. Kolejnym krokiem jest pobranie etykiety.

Endpoint: GET /packages/{package\_id}/label  
Alternatywnie, odpowiedź tworzenia przesyłki może zawierać bezpośredni link label\_url lub documents\_url.8  
Formaty Plików:  
Furgonetka umożliwia pobranie etykiet w różnych formatach 11:

* **PDF:** Uniwersalny format. Idealny dla drukarek laserowych (format A4, np. 4 etykiety na stronę) lub termicznych, jeśli sterownik drukarki obsługuje konwersję.  
* **ZPL / EPL:** Języki programowania drukarek termicznych (Zebra/Eltron). Jest to format preferowany w profesjonalnych magazynach. Plik nie jest obrazkiem, lecz kodem tekstowym, który jest interpretowany przez drukarkę, co zapewnia idealną ostrość kodów kreskowych i błyskawiczny wydruk.

Aby wybrać format, należy użyć odpowiedniego parametru w zapytaniu lub nagłówka, np.:  
GET /packages/{package\_id}/label?format=zpl (Szczegóły zależą od konkretnej wersji API, zalecana weryfikacja w dokumentacji Swagger w panelu).

### **7.2 Strategie Druku w Aplikacji Kartoteka 2.0**

Aplikacja webowa (jako backend) nie ma bezpośredniego dostępu do drukarki podłączonej do komputera użytkownika (przeglądarki). Istnieją dwa główne podejścia do rozwiązania tego problemu:

#### **Podejście A: Druk Przeglądarkowy (PDF)**

1. Kartoteka 2.0 pobiera PDF z API Furgonetki.  
2. Wyświetla PDF w nowym oknie lub iframe z automatycznym wywołaniem window.print().  
3. Użytkownik wybiera drukarkę w oknie dialogowym systemu i zatwierdza.  
   Zaleta: Prostota implementacji.  
   Wada: Wymaga interakcji użytkownika przy każdej etykiecie (kilka kliknięć).

#### **Podejście B: Integracja z "Print Server" lub Assistantem (ZPL/PDF)**

Furgonetka oferuje aplikację "Asystent Druku" (Printing Assistant) 11, która instalowana jest na komputerze magazyniera. Aplikacja ta łączy się z chmurą Furgonetki.

1. Kartoteka 2.0 tworzy przesyłkę przez API.  
2. Przesyłka pojawia się na koncie Furgonetki.  
3. Asystent Druku (skonfigurowany do nasłuchiwania nowych przesyłek) automatycznie pobiera etykietę i wysyła ją na domyślną drukarkę termiczną.  
   Zaleta: Pełna automatyzacja (klikasz w aplikacji, etykieta wychodzi z drukarki).  
   Wada: Konieczność instalacji i konfiguracji zewnętrznego oprogramowania na stacjach roboczych.

**Rekomendacja dla Kartoteki 2.0:** Rozpoczęcie od podejścia A (wyświetlanie PDF) jako MVP (Minimum Viable Product), a docelowo rozważenie integracji z API Asystenta Druku lub budowa własnego mikserwisu drukującego, jeśli wolumen zamówień jest duży.

## ---

**8\. Obsługa Błędów i Odporność Systemu**

Integracja produkcyjna musi być odporna na awarie. API Furgonetki komunikuje stany błędów za pomocą kodów HTTP.4

### **8.1 Mapa Kodów Odpowiedzi**

| Kod HTTP | Znaczenie | Akcja Systemu Kartoteka 2.0 |
| :---- | :---- | :---- |
| **200 OK / 201 Created** | Sukces. | Zapisz package\_id w bazie, pobierz etykietę. |
| **400 Bad Request** | Błąd składni JSON. | Loguj błąd deweloperski. Sprawdź strukturę payloadu. |
| **401 Unauthorized** | Token wygasł lub jest błędny. | **Krytyczne:** Wywołaj procedurę refresh\_token i ponów żądanie. |
| **402 Payment Required** | Brak środków (Prepaid). | Wyświetl komunikat użytkownikowi: "Doładuj konto Furgonetka". |
| **403 Forbidden** | Brak uprawnień. | Sprawdź, czy dana usługa (np. DPD) jest aktywna na koncie. |
| **422 Unprocessable Entity** | Błąd walidacji danych. | **Najczęstszy błąd.** Wyświetl użytkownikowi komunikat z API (np. "Błędny kod pocztowy"). |
| **500/502/503** | Błąd serwera Furgonetki. | Zastosuj "Exponential Backoff" (odczekaj 1s, 2s, 4s...) i ponów próbę. Nie bombarduj API. |

### **8.2 Obsługa Błędów Biznesowych (Validation Errors)**

W przypadku kodu 422, ciało odpowiedz (body) zawiera szczegóły błędów w formacie JSON.13  
Przykład:

JSON

{  
  "errors": {  
    "receiver.postcode": \["Kod pocztowy jest nieprawidłowy dla wybranego kraju."\],  
    "parcels.weight":  
  }  
}

Kartoteka 2.0 musi sparsować tę odpowiedź i podświetlić odpowiednie pola w formularzu edycji przesyłki, umożliwiając operatorowi korektę danych bez wychodzenia z aplikacji.

## ---

**9\. Strategia Testów i Środowisko Sandbox**

Wdrażanie integracji na "żywym organizmie" (produkcji) jest ryzykowne, gdyż generowanie etykiet często wiąże się z obciążeniem finansowym konta.

### **9.1 Środowisko Testowe**

Furgonetka udostępnia środowisko Sandbox: https://sandbox.furgonetka.pl.8  
Ważne: Dane logowania (Client ID/Secret) dla Sandboxa są inne niż dla Produkcji. Użytkownik dostarczył dane produkcyjne. Aby bezpiecznie testować, należy zarejestrować osobne konto na platformie Sandbox i tam wygenerować testowe aplikacje.

### **9.2 Scenariusze Testowe**

Przed wdrożeniem produkcyjnym należy przeprowadzić testy dla następujących scenariuszy:

1. **Happy Path:** Utworzenie poprawnej przesyłki kurierskiej i pobranie PDF.  
2. **Paczkomat:** Utworzenie przesyłki do Paczkomatu (walidacja pola point).  
3. **Token Refresh:** Symulacja wygaśnięcia tokena (np. poprzez ręczne usunięcie go z bazy lub odczekanie czasu ważności) i sprawdzenie, czy aplikacja sama go odnowi.  
4. **Błąd Adresowy:** Próba wysyłki na błędny kod pocztowy – weryfikacja czy aplikacja wyświetla zrozumiały komunikat błędu.  
5. **Brak Środków:** (Trudne do symulacji na Sandboxie, ale warto przygotować obsługę błędu 402).

## ---

**10\. Podsumowanie i Rekomendacje Wdrożeniowe**

Integracja Kartoteki 2.0 z API Furgonetka.pl jest procesem wieloetapowym, wymagającym precyzji w obszarze autoryzacji i strukturyzacji danych. Dzięki wykorzystaniu Authorization Code Flow, aplikacja zyska bezpieczny i trwały dostęp do zasobów logistycznych. Kluczem do sukcesu jest:

1. **Solidna obsługa Tokenów:** Implementacja mechanizmu automatycznego odświeżania (refresh\_token) to absolutna konieczność, aby system był bezobsługowy ("set and forget").  
2. **Walidacja po stronie Klienta:** Odsiewanie błędnych kodów pocztowych i numerów telefonów jeszcze przed wysłaniem zapytania do API.  
3. **Inteligentne Mapowanie:** Wykorzystanie powiązania ze Shoperem do automatycznego pobierania ID Paczkomatów, zamiast zmuszania użytkownika do ręcznego ich kopiowania.  
4. **Ergonomia Druku:** Zapewnienie szybkiego dostępu do etykiet PDF, z wizją przyszłej automatyzacji druku termicznego.

Wykonanie powyższych zaleceń przekształci Kartotekę 2.0 w potężne narzędzie logistyczne, skracając czas obsługi pojedynczego zamówienia z kilku minut do kilku sekund.

### **Lista Kontrolna dla Programisty (Checklist)**

* \[ \] Zaimplementowano endpoint odbierający code z OAuth (Callback URL).  
* \[ \] Skonfigurowano tabelę w bazie danych do bezpiecznego przechowywania tokenów (szyfrowanie at rest).  
* \[ \] Stworzono serwis (Cron/Middleware) do odświeżania tokenów.  
* \[ \] Zmapowano metody dostawy ze Shopera na kody usług Furgonetki (service).  
* \[ \] Zaimplementowano obsługę błędów 422 i wyświetlanie komunikatów walidacyjnych w UI.  
* \[ \] Przetestowano wydruk etykiety PDF na środowisku Sandbox.

Niniejszy raport stanowi kompletną bazę wiedzy niezbędną do rozpoczęcia prac programistycznych. Powodzenia we wdrożeniu\!

#### **Cytowane prace**

1. Shoper integration with Furgonetka – connect your store, otwierano: grudnia 2, 2025, [https://furgonetka.pl/en/e-commerce-integrations/shoper](https://furgonetka.pl/en/e-commerce-integrations/shoper)  
2. Furgonetka.pl: Integracja z WooCommerce – WordPress plugin, otwierano: grudnia 2, 2025, [https://wordpress.org/plugins/furgonetka/](https://wordpress.org/plugins/furgonetka/)  
3. Dokumentacja OAuth2 \- Furgonetka.pl, otwierano: grudnia 2, 2025, [https://furgonetka.pl/api/oauth](https://furgonetka.pl/api/oauth)  
4. HTTP Status Codes \- REST API Tutorial, otwierano: grudnia 2, 2025, [https://www.restapitutorial.com/httpstatuscodes](https://www.restapitutorial.com/httpstatuscodes)  
5. What are HTTP status codes? Complete Guide for API Developers \- Postman Blog, otwierano: grudnia 2, 2025, [https://blog.postman.com/what-are-http-status-codes/](https://blog.postman.com/what-are-http-status-codes/)  
6. Dokumentacja wzoru API dla integracji e-commerce \- Furgonetka.pl, otwierano: grudnia 2, 2025, [https://furgonetka.pl/api/universal-integration-example](https://furgonetka.pl/api/universal-integration-example)  
7. Shipping improvements – ship faster and more efficiently with Furgonetka, otwierano: grudnia 2, 2025, [https://furgonetka.pl/en/shipping-improvements](https://furgonetka.pl/en/shipping-improvements)  
8. Changelog REST API \- Furgonetka.pl, otwierano: grudnia 2, 2025, [https://furgonetka.pl/api/rest/changelog?lang=en\_GB](https://furgonetka.pl/api/rest/changelog?lang=en_GB)  
9. Express delivery in several dozen minutes \- Furgonetka.pl, otwierano: grudnia 2, 2025, [https://furgonetka.pl/en/express-delivery](https://furgonetka.pl/en/express-delivery)  
10. Domestic shipments – affordable domestic courier \- Furgonetka.pl, otwierano: grudnia 2, 2025, [https://furgonetka.pl/en/domestic-shipping](https://furgonetka.pl/en/domestic-shipping)  
11. Furgonetka Printing Assistant – print more easily, otwierano: grudnia 2, 2025, [https://furgonetka.pl/en/furgonetka-printing-assistant](https://furgonetka.pl/en/furgonetka-printing-assistant)  
12. REST API Response Codes \- MailerSend, otwierano: grudnia 2, 2025, [https://www.mailersend.com/help/rest-api-response-codes](https://www.mailersend.com/help/rest-api-response-codes)  
13. Validation responses in REST API \- Stack Overflow, otwierano: grudnia 2, 2025, [https://stackoverflow.com/questions/39759906/validation-responses-in-rest-api](https://stackoverflow.com/questions/39759906/validation-responses-in-rest-api)  
14. Structuring validation errors in REST APIs | by Łukasz Lalik \- Medium, otwierano: grudnia 2, 2025, [https://medium.com/@k3nn7/structuring-validation-errors-in-rest-apis-40c15fbb7bc3](https://medium.com/@k3nn7/structuring-validation-errors-in-rest-apis-40c15fbb7bc3)