

# **Raport Techniczny: Kompleksowa Analiza Architektury i Implementacji Integracji Usług Logistycznych Furgonetka.pl w Środowisku Docker**

## **Streszczenie Zarządcze**

Niniejszy dokument stanowi wyczerpującą, ekspercką analizę techniczną oraz studium wykonalności integracji autorskiego systemu e-commerce, funkcjonującego w oparciu o architekturę mikroserwisową Docker, z ekosystemem logistycznym platformy Furgonetka.pl. Raport został przygotowany w odpowiedzi na zapytanie dotyczące możliwości programistycznej implementacji kluczowych procesów biznesowych: automatycznego tworzenia zamówień i przesyłek, generowania etykiet przewozowych, obsługi płatności ze szczególnym uwzględnieniem systemu BLIK oraz automatyzacji fizycznego wydruku dokumentów przewozowych.

Analiza opiera się na szczegółowej weryfikacji dokumentacji technicznej REST API Furgonetka.pl, dostępnych bibliotek klienckich, specyfikacji protokołów uwierzytelniania OAuth2 oraz dokumentacji urządzeń drukujących. Głównym celem opracowania jest nie tylko potwierdzenie wykonalności technicznej poszczególnych funkcjonalności, ale przede wszystkim przedstawienie optymalnych ścieżek implementacji, uwzględniających specyfikę środowiska konteneryzowanego, bezpieczeństwo transakcji oraz stabilność operacyjną.

Wnioski płynące z przeprowadzonej ewaluacji wskazują, że pełna integracja jest technicznie możliwa i uzasadniona biznesowo, aczkolwiek stopień złożoności implementacji różni się znacząco w zależności od obszaru funkcjonalnego. O ile tworzenie przesyłek i pobieranie etykiet opiera się na standardowych wzorcach architektonicznych REST 1, o tyle obsługa płatności BLIK w modelu automatycznym oraz zdalny wydruk etykiet z poziomu kontenera Docker wymagają zastosowania zaawansowanych rozwiązań pośrednich oraz precyzyjnego zaprojektowania przepływu danych. W szczególności, raport identyfikuje konieczność rozróżnienia płatności konsumenckich od rozliczeń B2B z operatorem logistycznym oraz proponuje hybrydowe podejście do druku, wykorzystujące formaty wektorowe ZPL.2

---

## **1\. Kontekst Architektoniczny: Integracja REST API w Środowisku Konteneryzowanym**

Współczesne systemy e-commerce coraz częściej odchodzą od monolitycznych architektur na rzecz rozwiązań opartych na mikroserwisach i konteneryzacji, co znajduje odzwierciedlenie w infrastrukturze użytkownika opartej na Dockerze. Integracja z zewnętrznym dostawcą usług logistycznych (3PL), takim jak Furgonetka.pl, w takim środowisku wymaga specyficznego podejścia do zarządzania stanem, siecią oraz bezpieczeństwem danych uwierzytelniających.

### **1.1. Charakterystyka Środowiska Docker w Kontekście Komunikacji API**

Aplikacja użytkownika, działająca jako serwer Docker z frontendem, stanowi idealny grunt do implementacji klienta API Furgonetki, pod warunkiem zachowania odpowiednich rygorów konfiguracyjnych. W ekosystemie Docker, aplikacja backendowa (zazwyczaj napisana w PHP, Pythonie lub Node.js) funkcjonuje w izolowanym środowisku, co ma kluczowe znaczenie dla stabilności integracji.4 Komunikacja z API Furgonetki odbywa się poprzez protokół HTTPS, co wymusza na kontenerze posiadanie dostępu do sieci zewnętrznej oraz poprawnie skonfigurowanej warstwy certyfikatów CA (Certificate Authority), aby móc bezpiecznie zestawiać połączenia szyfrowane TLS z endpointami https://api.furgonetka.pl/.1

Istotnym wyzwaniem w środowisku efemerycznym, jakim są kontenery, jest zarządzanie plikami tymczasowymi. Generowanie etykiet przewozowych (PDF lub ZPL) wiąże się z koniecznością ich chwilowego składowania przed wysłaniem do użytkownika lub drukarki. W architekturze Docker nie można polegać na lokalnym systemie plików kontenera w sposób trwały, gdyż restart usługi powoduje utratę danych. Dlatego implementacja musi uwzględniać albo bezpośrednie strumieniowanie danych (streaming) z odpowiedzi API do przeglądarki klienta, albo wykorzystanie dedykowanych wolumenów (volumes) współdzielonych między kontenerami, co jest zgodne z najlepszymi praktykami "Twelve-Factor App".

### **1.2. Zarządzanie Konfiguracją i Bezpieczeństwo Poświadczeń**

Integracja z Furgonetka.pl wymaga zarządzania wrażliwymi danymi uwierzytelniającymi, takimi jak client\_id oraz client\_secret.1 W środowisku Docker absolutnie niedopuszczalne jest "twarde kodowanie" (hardcoding) tych wartości w kodzie źródłowym aplikacji. Zgodnie z analizą repozytoriów i praktyk DevOps 4, optymalnym rozwiązaniem jest wstrzykiwanie tych danych jako zmiennych środowiskowych (ENV) w momencie uruchamiania kontenera.

Proces ten realizowany jest zazwyczaj poprzez pliki .env niepodlegające wersjonowaniu w systemie git, które są odczytywane przez orkiestratora (np. Docker Compose) i przekazywane do procesu PHP lub Python. Dzięki temu, nawet w przypadku wycieku kodu źródłowego, klucze API pozostają bezpieczne. Dodatkowo, w kontekście API Furgonetki, które opiera się na tokenach JWT (JSON Web Token) 1, aplikacja musi posiadać mechanizm bezpiecznego przechowywania aktywnego tokena dostępowego (access\_token). Przechowywanie go w bazie danych (np. Redis lub MySQL działającym w osobnym kontenerze) jest preferowane względem przechowywania w pamięci RAM procesu, co zapewnia persystencję sesji nawet po restarcie kontenera aplikacyjnego.

### **1.3. Biblioteki Klienckie i Wsparcie Językowe**

Analiza dostępnych zasobów deweloperskich wskazuje na silne wsparcie dla języka PHP w ekosystemie Furgonetki. Istnieją gotowe, społecznościowe oraz oficjalne biblioteki, takie jak kwarcek/furgonetka-rest-api-php czy lari/furgonetka.4 Wykorzystanie Dockera ułatwia zarządzanie zależnościami poprzez menedżera pakietów Composer. W pliku Dockerfile należy uwzględnić instalację niezbędnych rozszerzeń systemowych, takich jak libcurl oraz rozszerzeń PHP curl, json i openssl, które są fundamentalne dla obsługi zapytań REST.

Warto zauważyć, że chociaż PHP jest dominującym językiem w dostępnych przykładach, architektura REST API jest agnostyczna technologicznie. Oznacza to, że integracja jest w pełni możliwa również w Pythonie, Java czy Node.js, pod warunkiem implementacji odpowiedniej obsługi zapytań HTTP oraz standardu OAuth2 opisanego w dokumentacji.1

---

## **2\. Protokoły Uwierzytelniania i Zarządzanie Tożsamością w API**

Fundamentem bezpieczeństwa każdej integracji z zewnętrznym API jest mechanizm autoryzacji. Furgonetka.pl wykorzystuje standard OAuth2, który jest obecnie przemysłowym standardem zabezpieczania interfejsów REST.1 Zrozumienie niuansów tego protokołu jest kluczowe dla zapewnienia ciągłości działania automatyzacji sklepu.

### **2.1. Analiza Typów Grantów (Grant Types) w Kontekście Automatyzacji**

Dokumentacja Furgonetka.pl wymienia kilka metod autoryzacji, z których każda służy innym celom.1 Wybór odpowiedniego typu grantu (Grant Type) determinuje architekturę modułu autoryzacyjnego w aplikacji użytkownika.

1. **Authorization Code Grant:** Jest to metoda wymagająca interakcji użytkownika (przekierowania do strony logowania Furgonetki). Choć jest najbezpieczniejsza dla aplikacji klienckich działających w imieniu wielu użytkowników, w przypadku własnego sklepu działającego w tle (server-to-server), może być uciążliwa w implementacji pełnej automatyzacji, gdyż wymagałaby okresowego ręcznego logowania operatora w celu odświeżenia zgód, jeśli tokeny odświeżające wygasną.1  
2. **Resource Owner Password Credentials Grant:** Metoda ta polega na bezpośrednim przesłaniu loginu i hasła użytkownika do API w celu uzyskania tokena. Dokumentacja wspomina o autoryzacji typu "password".1 Jest to metoda prostsza w implementacji dla systemów backendowych, gdzie aplikacja "zna" poświadczenia właściciela konta. Jednakże, w przypadku włączonego uwierzytelniania dwuskładnikowego (2FA), proces ten staje się złożony, wymagając dodatkowego kroku weryfikacji kodu UUID i twoFactorCode.1  
3. **Client Credentials Grant:** To najczęściej stosowany typ autoryzacji dla komunikacji maszyna-maszyna (M2M). Aplikacja uwierzytelnia się swoim client\_id i client\_secret bez kontekstu konkretnego użytkownika. Dokumentacja Furgonetki wskazuje, że ten typ grantu jest przeznaczony dla integracji systemowych, ale tokeny uzyskane tą drogą mają zazwyczaj krótszy czas życia (60 minut) i nie podlegają odświeżaniu (brak refresh\_token), co wymusza częste ponawianie autoryzacji.1

Dla opisywanego przypadku (własny sklep), najczęściej rekomendowaną ścieżką jest wykorzystanie Authorization Code z długoterminowym refresh\_token lub Password Grant (jeśli 2FA jest wyłączone lub obsłużone). Kluczowe jest, aby system automatycznie zarządzał cyklem życia tokena.

### **2.2. Cykl Życia Tokena i Strategia Odświeżania**

Tokeny dostępowe (access\_token) w systemie Furgonetka.pl są zgodne ze standardem JWT i mają określony czas ważności – dokumentacja wspomina o 30 dniach dla tokenów uzyskanych metodą Authorization Code oraz Code Grant, oraz zaledwie 60 minutach dla Client Credentials.1 Implementacja w Dockerze musi zawierać logikę "Strażnika Tokena" (Token Guard).

Algorytm działania powinien wyglądać następująco:

1. Przed wykonaniem jakiejkolwiek operacji (np. utworzenie przesyłki), aplikacja sprawdza w lokalnym magazynie (Redis/Baza danych), czy posiada aktywny token i czy jego czas wygasnięcia (expires\_in) nie nastąpi w ciągu najbliższych np. 5 minut.  
2. Jeśli token jest ważny, jest dołączany do nagłówka Authorization: Bearer \<token\>.  
3. Jeśli token wygasa lub wygasł, aplikacja musi użyć posiadanego refresh\_token (ważnego zazwyczaj znacznie dłużej, np. 3 miesiące) do pobrania nowej pary tokenów poprzez żądanie POST na endpoint /oauth/token z parametrem grant\_type=refresh\_token.1  
4. W przypadku autoryzacji client\_credentials, gdzie nie ma refresh tokena, aplikacja musi po prostu ponownie poprosić o nowy token używając client\_id i secret.

### **2.3. Ograniczenia Sesyjne i Zarządzanie Limitami**

Niezwykle istotnym, a często pomijanym aspektem, jest limit sesji narzucony przez API Furgonetki. Dokumentacja precyzuje, że dla każdej aplikacji OAuth użytkownik może mieć otwartych **maksymalnie 20 sesji naraz**.1 Przekroczenie tego limitu (np. poprzez błędną implementację, która prosi o nowy token przy każdym żądaniu zamiast go cache'ować) spowoduje automatyczne unieważnienie najstarszego tokena.

W środowisku Docker, gdzie aplikacja może być skalowana horyzontalnie (wiele kontenerów obsługujących ruch), ryzyko wygenerowania wielu tokenów jest wysokie. Dlatego krytyczne jest zastosowanie centralnego magazynu tokenów (np. wspomniany Redis), do którego dostęp mają wszystkie instancje aplikacji. Brak takiej synchronizacji doprowadzi do sytuacji "wyścigu" (race condition), gdzie kontenery będą wzajemnie unieważniać swoje tokeny, paraliżując działanie sklepu.

---

## **3\. Implementacja Procesów Logistycznych: Od Zamówienia do Przesyłki**

Rdzeniem zapytania użytkownika jest możliwość tworzenia zamówień i generowania etykiet. Analiza dokumentacji pozwala na precyzyjne rozróżnienie dwóch bytów w systemie Furgonetka: "Zamówienia" (Order) oraz "Przesyłki" (Package/Shipment). Rozróżnienie to jest kluczowe dla architektury integracji.

### **3.1. Dychotomia: API Integracji E-commerce vs. API Logistyczne**

System Furgonetka.pl oferuje dwa uzupełniające się interfejsy programistyczne, które mogą być używane równolegle lub rozłącznie:

1. **API Integracji E-commerce (Orders API):** Służy do synchronizacji koszyka zakupowego ze sklepu do panelu Furgonetki. Pozwala to na przesłanie danych o zamówieniu (produkty, waga, adres), które następnie widoczne są w panelu "Do wysłania". Jest to rozwiązanie pół-automatyczne – dane trafiają do systemu, ale decyzję o wysyłce podejmuje często operator ręcznie w panelu. Endpointy takie jak POST /orders obsługują strukturę zawierającą cartId, products, shippingAddress.1  
2. **API Logistyczne (Logistics/Packages API):** Służy do natychmiastowego, w pełni automatycznego tworzenia listów przewozowych. To jest funkcjonalność, o którą pyta użytkownik w kontekście "generowania etykiety". Operacja ta pomija etap "oczekującego zamówienia" i od razu finalizuje proces logistyczny u przewoźnika.1

Dla pełnej automatyzacji w modelu Docker, rekomendowane jest bezpośrednie korzystanie z **API Logistycznego (/packages)**, chyba że proces biznesowy wymaga ręcznej weryfikacji każdego zamówienia przez pracownika w panelu Furgonetki.

### **3.2. Szczegółowa Struktura Żądania Tworzenia Przesyłki**

Aby zaimplementować funkcję tworzenia przesyłki, aplikacja musi skonstruować złożony obiekt JSON i wysłać go metodą POST na odpowiedni endpoint (zazwyczaj /packages lub /orders z flagą automatyzacji). Analiza bibliotek PHP 6 oraz dokumentacji parametrów 7 pozwala na zrekonstruowanie wymaganej struktury danych.

#### **Tabela 1: Kluczowe Segmenty Danych w Żądaniu Utworzenia Przesyłki**

| Segment Danych | Opis Funkcjonalny | Kluczowe Pola i Wymagania Walidacyjne |
| :---- | :---- | :---- |
| **sender** (Nadawca) | Określa punkt nadania paczki. | Może być zdefiniowany statycznie w panelu (ID punktu nadania) lub przesyłany dynamicznie (adres, miasto, kod pocztowy, kontakt). Walidacja kodu pocztowego jest krytyczna dla poprawności wyceny. 7 |
| **receiver** (Odbiorca) | Dane klienta docelowego. | Wymagane: imię, nazwisko, ulica, numer domu, miasto, kod pocztowy, telefon (często wymagany format \+48...), email (do powiadomień statusowych). 6 |
| **parcels** (Paczki) | Fizyczna charakterystyka przesyłki. | Wymagane: waga (kg), wymiary (dł. x szer. x wys. w cm), typ opakowania (box, envelope, pallet). Błędne wymiary mogą skutkować odrzuceniem przez API przewoźnika (np. InPost). 6 |
| **service** (Usługa) | Wybór przewoźnika i serwisu. | Kod usługi: inpost, dpd, ups, poczta, orlen. Dla usług punktowych (Paczkomaty, Żabka, Orlen Paczka) wymagany jest dodatkowy parametr identyfikujący punkt odbioru (np. point lub receiver\_paczkomat). 1 |
| **additional\_services** | Usługi dodatkowe (COD, ubezpieczenie). | cod (pobranie) \- wymaga podania kwoty i numeru konta (często zdefiniowanego globalnie). insurance (ubezpieczenie) \- wartość deklarowana. 7 |

### **3.3. Logika Mapowania i Walidacji Danych**

Kluczowym wyzwaniem implementacyjnym jest mapowanie danych ze sklepu na format akceptowany przez API. Różni przewoźnicy stosują różne formaty identyfikatorów punktów odbioru (PUDO). Dokumentacja API integracji E-commerce dostarcza cennych informacji na ten temat 1:

* **InPost (Paczkomaty):** Identyfikator to nazwa własna, np. KRA007.  
* **DPD Pickup:** Identyfikator punktu SAP, np. PL11033.  
* **Poczta Polska:** PNI (Placówka Pocztowa), np. 116744\.  
* **Orlen Paczka:** Numer PSD, np. 106088\.  
* **UPS Access Point:** ID punktu, np. U00032786.

Aplikacja użytkownika musi posiadać logikę, która na podstawie wybranej w frontendzie metody dostawy, odpowiednio sformatuje pole point w żądaniu JSON. Błędne przypisanie (np. wysłanie kodu Poczty Polskiej do serwisu InPost) skutkuje błędem walidacji (HTTP 400 Bad Request lub 422 Unprocessable Entity).

### **3.4. Obsługa Odpowiedzi i Błędów**

Poprawne przetworzenie żądania przez API skutkuje zwróceniem obiektu zawierającego package\_id (wewnętrzny identyfikator Furgonetki) oraz, w zależności od konfiguracji konta, numeru listu przewozowego (tracking number). W przypadku błędów, API zwraca szczegółowe komunikaty walidacyjne. W środowisku Docker, aplikacja powinna logować te błędy (do stdout/stderr obsługiwanego przez logi Dockera) oraz prezentować użytkownikowi czytelny komunikat (np. "Błędny format kodu pocztowego dla wybranego przewoźnika").

---

## **4\. Systemy Płatności w Ekosystemie API: Analiza Obsługi BLIK**

Pytanie użytkownika o możliwość "opłacania BLIK za pomocą API" dotyka jednego z najbardziej złożonych aspektów integracji, gdzie technologia spotyka się z modelem biznesowym i przepływami finansowymi. Należy tu dokonać fundamentalnego rozróżnienia między płatnością konsumenta (C2B) a rozliczeniem partnera z operatorem logistycznym (B2B).

### **4.1. Modele Rozliczeń z Furgonetka.pl**

W relacji Sklep (Właściciel aplikacji) – Furgonetka, dostępne są dwa główne modele rozliczeń, które determinują sposób korzystania z API:

1. **Model Prepaid (Portmonetka/Saldo):** Jest to model domyślny dla mniejszych podmiotów. Użytkownik doładowuje saldo swojego konta w Furgonetce (przelewem, kartą lub BLIKiem poprzez panel WWW). W momencie generowania etykiety przez API (POST /packages), system sprawdza saldo. Jeśli jest wystarczające, środki są automatycznie pobierane, a etykieta generowana. Jeśli brak środków – API zwraca błąd.  
2. **Model Postpaid (Faktura):** Dla klientów biznesowych z podpisaną umową. Etykiety są generowane bez natychmiastowego obciążenia, a rozliczenie następuje zbiorczo na podstawie faktury VAT wystawianej np. raz w miesiącu.9

### **4.2. Wykonalność Płatności BLIK "per API"**

Czy jest możliwe technicznie, aby API Furgonetki przyjęło żądanie "Utwórz paczkę i pobierz opłatę BLIKiem teraz"?  
Analiza dokumentacji płatności (Stripe, Adyen, BLIK standard) 11 oraz dokumentacji Furgonetki 13 wskazuje, że bezpośrednia inicjacja transakcji BLIK (wpisanie kodu 6-cyfrowego, oczekiwanie na push w aplikacji bankowej) jest procesem interaktywnym, przeznaczonym dla interfejsów frontendowych (Checkout), a nie dla asynchronicznych procesów backendowych generowania etykiet.  
API Furgonetki **nie udostępnia** endpointu, który przyjmowałby kod BLIK jako parametr przy tworzeniu przesyłki logistycznej w celu jej opłacenia. Płatność BLIK jest dostępna w "Furgonetka Koszyk" 13 jako metoda płatności dla *klienta końcowego* za towar, a nie jako metoda opłacenia kosztu etykiety przez sklep w momencie wywołania API.

### **4.3. Rekomendowana Architektura Płatności**

W celu zrealizowania postulatu użytkownika w sposób profesjonalny i niezawodny, rekomenduje się następujące podejście architektoniczne:

1. **Rozdzielenie Płatności:**  
   * **Klient \-\> Sklep:** Klient płaci za zamówienie (towar \+ wysyłka) w sklepie użytkownika, używając BLIK (obsłużonego przez bramkę płatniczą sklepu, np. Tpay, PayU, Stripe). Aplikacja użytkownika otrzymuje potwierdzenie wpłaty.  
   * **Sklep \-\> Furgonetka:** Aplikacja automatycznie zleca wygenerowanie etykiety przez API. Koszt tej etykiety jest pokrywany z **salda prepaid** (wcześniej doładowanego) lub dopisywany do **faktury postpaid**.  
2. Integracja Statusów Płatności (Furgonetka Koszyk):  
   Jeśli użytkownik korzysta z rozwiązania "Furgonetka Koszyk" (gotowy checkout), API udostępnia endpointy do aktualizacji statusu płatności (post/orders/{sourceOrderId}/payments).1 Pozwala to na przesłanie informacji do panelu Furgonetki, że dane zamówienie zostało opłacone (np. BLIKiem), co może być sygnałem dla magazynu do rozpoczęcia pakowania.

Wnioskując: Bezpośrednie "płacenie BLIKiem za etykietę" w locie przy każdym zapytaniu API jest anty-wzorcem architektonicznym w automatyzacji B2B. Należy dążyć do modelu automatycznego obciążania salda/kredytu kupieckiego.

---

## **5\. Generowanie i Automatyzacja Wydruku: PDF vs. ZPL**

Ostatnim, ale niezwykle istotnym elementem zapytania jest "wydruk za pomocą API". W środowisku logistycznym wydruk to nie tylko wygenerowanie pliku, ale fizyczne dostarczenie go na urządzenie termiczne. Tutaj architektura Docker napotyka na specyficzne wyzwania związane z izolacją sprzętową.

### **5.1. Formaty Etykiet: Analiza Porównawcza**

API Furgonetki umożliwia pobranie etykiet w różnych formatach. Wybór formatu ma fundamentalne znaczenie dla sposobu dalszego przetwarzania.2

#### **Tabela 2: Porównanie Formatów Etykiet w Kontekście Integracji Docker**

| Cecha | Format PDF (Portable Document Format) | Format ZPL (Zebra Programming Language) / EPL |
| :---- | :---- | :---- |
| **Natura Danych** | Grafika rastrowa/wektorowa sformatowana dla dokumentu strony (A4, A6). | Surowy kod sterujący drukarką (polecenia tekstowe, np. ^XA...^XZ). |
| **Zastosowanie** | Drukarki laserowe, atramentowe, uniwersalne. Ręczny wydruk przez przeglądarkę. | Drukarki termiczne i termotransferowe (Zebra, Citizen, Honeywell). Przemysłowa logistyka. |
| **Przetwarzanie w Docker** | Wymaga bibliotek do obsługi PDF (np. Ghostscript) jeśli chcemy manipulować. Duży rozmiar plików. | Bardzo lekkie ciągi tekstowe. Łatwe do manipulacji (np. doklejanie własnych kodów). 2 |
| **Metoda Druku** | Wymaga sterownika drukarki w systemie operacyjnym (CUPS) i renderowania grafiki. | Możliwy bezpośredni zrzut na port sieciowy drukarki (Raw Socket 9100\) bez sterowników. 17 |
| **Jakość Kodów Kreskowych** | Zależna od renderowania (skalowanie może zepsuć czytelność skanera). | Perfekcyjna (kody generowane sprzętowo przez drukarkę). |

### **5.2. Strategie Automatyzacji Wydruku w Dockerze**

Skoro API zwraca plik (lub kod ZPL), jak doprowadzić do fizycznego wydruku z kontenera?

Strategia A: Natywna Integracja (Furgonetka Printing Assistant)  
Furgonetka oferuje narzędzie "Printing Assistant" 15, które instaluje się na komputerze fizycznym podłączonym do drukarki. Aplikacja ta nasłuchuje poleceń z serwera Furgonetki.

* *Implementacja:* W API nie musimy przesyłać pliku do drukarki. Wystarczy skonfigurować w panelu Furgonetki automatyczny wydruk dla danego użytkownika lub wywołać odpowiednią akcję API (jeśli dostępna w niepublicznych metodach, co sugerują opcje automatyzacji w panelu). Jest to najprostsza metoda, przenosząca ciężar obsługi sprzętu na gotową aplikację producenta.

Strategia B: Wydruk Bezpośredni (Raw Socket) – Podejście "Cloud Native"  
Dla zaawansowanych użytkowników Docker, preferujących pełną kontrolę i używających drukarek sieciowych (z interfejsem Ethernet/Wi-Fi), możliwe jest zaimplementowanie własnego sterownika druku.

1. **Pobranie ZPL:** Aplikacja wysyła żądanie do API Furgonetki o etykietę w formacie ZPL (często wymaga to ustawienia odpowiednich nagłówków lub parametrów format=zpl).16  
2. **Transmisja TCP:** Kontener PHP/Python otwiera połączenie TCP (socket) na adres IP drukarki (np. 192.168.1.50, port 9100).  
3. **Wysłanie Danych:** Ciąg znaków ZPL odebrany z API jest wysyłany bezpośrednio do socketa. Drukarka interpretuje komendy i drukuje etykietę natychmiastowo.  
   * *Zaleta:* Brak pośredników, brak konieczności instalowania sterowników w kontenerze. Szybkość działania.  
   * *Wymaganie:* Drukarka musi być widoczna w sieci dla kontenera Docker (odpowiedni routing).

Strategia C: Serwer Wydruku CUPS w Kontenerze  
Jeśli drukarka jest podłączona przez USB do serwera hosta, konieczne jest udostępnienie jej kontenerom. Można to zrobić, montując urządzenie /dev/usb/lp0 do kontenera z zainstalowanym systemem CUPS (Common Unix Printing System). Aplikacja PHP komunikuje się z lokalnym CUPS-em, zlecając wydruk pliku PDF. Jest to rozwiązanie trudniejsze w konfiguracji i utrzymaniu w środowisku Docker.

---

## **6\. Obsługa Zwrotów i Logistyka Zwrotna**

Choć zapytanie użytkownika skupiało się na nadawaniu, kompletna integracja e-commerce nie może ignorować procesu odwrotnego. Furgonetka.pl kładzie duży nacisk na darmowy i prosty system zwrotów, co jest silnym atutem marketingowym.9

### **6.1. Implementacja Zwrotów przez API**

Dokumentacja wskazuje, że Furgonetka oferuje dedykowane narzędzia do obsługi zwrotów ("Szybkie zwroty"). Z perspektywy API, proces ten może być realizowany na dwa sposoby:

1. **Link "Nadaj do mnie":** API pozwala wygenerować link, który sklep wysyła klientowi. Klient sam wypełnia dane i generuje etykietę zwrotną. Jest to najmniej obciążające dla programisty rozwiązanie.  
2. **Przesyłka Zwrotna:** Aplikacja może utworzyć nową przesyłkę (analogicznie jak przy wysyłce), ale z zamienionymi rolami nadawcy i odbiorcy (Nadawca \= Klient, Odbiorca \= Magazyn Sklepu). Należy pamiętać, że etykietę taką trzeba dostarczyć klientowi (np. e-mailem jako PDF), co wymaga dodatkowej logiki w aplikacji.

System zwrotów Furgonetki integruje się również z platformami takimi jak WooCommerce czy PrestaShop poprzez wtyczki 19, co sugeruje, że API posiada odpowiednie endpointy do zarządzania statusem i przebiegiem zwrotu, które można zaimplementować we własnym rozwiązaniu Dockerowym.

---

## **7\. Podsumowanie i Rekomendacje Wdrożeniowe**

Przeprowadzona analiza potwierdza, że integracja REST API Furgonetka.pl z autorską aplikacją e-commerce opartą na Dockerze jest w pełni wykonalna i pozwala na osiągnięcie wysokiego stopnia automatyzacji. Poniżej przedstawiono syntetyczne podsumowanie odpowiedzi na postawione pytania oraz rekomendacje eksperckie.

1. **Tworzenie Zamówienia/Przesyłki:** Jest w pełni obsługiwane przez API. Rekomenduje się korzystanie z endpointów logistycznych (/packages) dla pełnej automatyzacji, z precyzyjną walidacją danych adresowych i mapowaniem usług kurierskich po stronie aplikacji.  
2. **Generowanie Etykiety:** API umożliwia pobieranie etykiet w czasie rzeczywistym. Zaleca się obsługę formatu ZPL dla profesjonalnych drukarek termicznych oraz PDF jako fallback dla użytkowników biurowych.  
3. **Płatność BLIK:** Bezpośrednia płatność BLIK za etykietę poprzez API w modelu "per request" nie jest zalecana ani standardowo wspierana. Należy wdrożyć model rozliczeń **Prepaid** (doładowanie salda) lub **Postpaid** (faktura), co zapewni płynność działania automatu wysyłkowego. Płatności BLIK od klientów sklepu powinny być procesowane niezależnie przez bramkę płatniczą sklepu.  
4. **Wydruk Automatyczny:** Wymaga rozwiązania hybrydowego. Dla środowiska Docker najwydajniejszą metodą jest bezpośrednia komunikacja TCP z drukarkami sieciowymi przy użyciu formatu ZPL (Raw Printing), co eliminuje konieczność instalowania sterowników w kontenerach. Alternatywą jest wykorzystanie aplikacji Furgonetka Printing Assistant na stacji roboczej.

**Rekomendacja Końcowa:** Sukces wdrożenia zależy od przyjęcia solidnej strategii zarządzania stanem tokenów OAuth2 (np. z wykorzystaniem Redis) oraz odseparowania logiki biznesowej płatności konsumenckich od technicznych rozliczeń kosztów logistycznych. Taka architektura zapewni skalowalność, bezpieczeństwo i niezawodność operacyjną sklepu.

#### **Cytowane prace**

1. Dokumentacja REST API \- Furgonetka.pl, otwierano: listopada 24, 2025, [https://furgonetka.pl/api/rest](https://furgonetka.pl/api/rest)  
2. PDF to ZPL Tutorial \- RapidAPI, otwierano: listopada 24, 2025, [https://rapidapi.com/adityawagh114/api/pdf-to-zpl/tutorials/pdf-to-zpl-tutorial-1](https://rapidapi.com/adityawagh114/api/pdf-to-zpl/tutorials/pdf-to-zpl-tutorial-1)  
3. Using ZPL Stored Formats \- Zebra Support Community, otwierano: listopada 24, 2025, [https://supportcommunity.zebra.com/s/article/Using-ZPL-Stored-Formats?language=en\_US](https://supportcommunity.zebra.com/s/article/Using-ZPL-Stored-Formats?language=en_US)  
4. Kwarcek/furgonetka-rest-api-php \- GitHub, otwierano: listopada 24, 2025, [https://github.com/Kwarcek/furgonetka-rest-api-php](https://github.com/Kwarcek/furgonetka-rest-api-php)  
5. .NET 8 . : Integrating Docker with a .NET Web API \- A Step-by-Step Guide \- YouTube, otwierano: listopada 24, 2025, [https://www.youtube.com/watch?v=\_wp2zJHs9l0](https://www.youtube.com/watch?v=_wp2zJHs9l0)  
6. ablypl/furgonetka \- GitHub, otwierano: listopada 24, 2025, [https://github.com/ablypl/furgonetka](https://github.com/ablypl/furgonetka)  
7. Changelog REST API \- Furgonetka.pl, otwierano: listopada 24, 2025, [https://furgonetka.pl/api/rest/changelog?lang=en\_GB](https://furgonetka.pl/api/rest/changelog?lang=en_GB)  
8. Shipping improvements – ship faster and more efficiently with Furgonetka, otwierano: listopada 24, 2025, [https://furgonetka.pl/en/shipping-improvements](https://furgonetka.pl/en/shipping-improvements)  
9. Returns to labelart.pl \- Cheap shipping for returned goods \- Furgonetka.pl, otwierano: listopada 24, 2025, [https://furgonetka.pl/sklep/zwroty/labelart.pl?lang=en\_GB](https://furgonetka.pl/sklep/zwroty/labelart.pl?lang=en_GB)  
10. Business offer for e-commerce \- Furgonetka, otwierano: listopada 24, 2025, [https://furgonetka.pl/en/offer-for-companies/ecommerce](https://furgonetka.pl/en/offer-for-companies/ecommerce)  
11. Blik payment method for mobile banking \- Adyen, otwierano: listopada 24, 2025, [https://www.adyen.com/payment-methods/blik](https://www.adyen.com/payment-methods/blik)  
12. BLIK payments \- Stripe Documentation, otwierano: listopada 24, 2025, [https://docs.stripe.com/payments/blik](https://docs.stripe.com/payments/blik)  
13. Dokumentacja Furgonetka Koszyk, otwierano: listopada 24, 2025, [https://furgonetka.pl/api/koszyk?lang=en\_GB](https://furgonetka.pl/api/koszyk?lang=en_GB)  
14. Furgonetka Checkout \- shopping on famous marketplaces, otwierano: listopada 24, 2025, [https://furgonetka.pl/en/checkout](https://furgonetka.pl/en/checkout)  
15. Furgonetka Printing Assistant – print more easily, otwierano: listopada 24, 2025, [https://furgonetka.pl/en/furgonetka-printing-assistant](https://furgonetka.pl/en/furgonetka-printing-assistant)  
16. Labelary ZPL Label API, otwierano: listopada 24, 2025, [https://labelary.com/service.html](https://labelary.com/service.html)  
17. Printing ZPL Label Files Easily? : r/Netsuite \- Reddit, otwierano: listopada 24, 2025, [https://www.reddit.com/r/Netsuite/comments/wjicwt/printing\_zpl\_label\_files\_easily/](https://www.reddit.com/r/Netsuite/comments/wjicwt/printing_zpl_label_files_easily/)  
18. Configure the Furgonetka Returns system, otwierano: listopada 24, 2025, [https://furgonetka.pl/en/wizard/shipment-returns/configuration](https://furgonetka.pl/en/wizard/shipment-returns/configuration)  
19. Configure Furgonetka Returns \- WooCommerce, otwierano: listopada 24, 2025, [https://furgonetka.pl/en/wizard/shipment-returns/woocommerce-configuration](https://furgonetka.pl/en/wizard/shipment-returns/woocommerce-configuration)