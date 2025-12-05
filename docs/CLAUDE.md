# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Version Control & GitHub Integration (2025-11-14)

**Project is now on GitHub!** The repository has been set up with Git version control and connected to GitHub for remote backup and collaboration.

**GitHub Repository:**
- URL: https://github.com/boguckicollection/kartoteka-2.0
- Initial commit contains complete Kartoteka 2.0 codebase with all backend and frontend files

**Git Workflow:**
- All changes are now tracked locally with `git commit`
- Changes can be pushed to GitHub with `git push`
- Full history and ability to revert to previous versions using `git revert` or `git reset`
- Use Conventional Commits format: `feat(scope): description`, `fix(scope): description`, etc.

**Common Git Commands:**
```bash
# View recent commits
git log --oneline

# Stage and commit changes
git add .
git commit -m "feat(api): add new feature"

# Push to GitHub
git push

# Revert to previous version (safe - creates new commit)
git revert <commit-id>

# Check status
git status
```

---

## Recent Changes (2025-11-18)

**FIXES: Improved handling of related products in Shoper API**

1.  ✅ **Fixed `AttributeError` for `validate_product_ids`** (`backend/app/shoper.py`):
    *   **Problem**: The `validate_product_ids` function was incorrectly defined outside the `ShoperClient` class, even though it was called as its method, leading to an `AttributeError`.
    *   **Solution**: Moved the definition of `validate_product_ids` into the `ShoperClient` class, making it a proper method.
    *   **Result**: Correct validation of related products before their publication.

2.  ✅ **Fixed issue with related products not appearing in Shoper** (`backend/app/shoper.py`):
    *   **Problem**: Related products, sent in the `related` field during product creation (`POST` method), were not being saved by the Shoper API and did not appear on the store page.
    *   **Solution**: 
        1.  Updated the `ShoperClient.get_product` method to also fetch data about related products (`"related"`) in the `with` parameter, enabling diagnosis.
        2.  Modified the `ShoperClient.update_product` method to accept and process the `related` field in the payload.
        3.  In the `publish_scan_to_shoper` function, added an explicit call to `ShoperClient.update_product` with the `related` field after successful product creation. This forces the saving of associations in a separate `PUT` request.
    *   **Result**: Related products are now correctly saved and visible in the Shoper store.

---

## Recent Changes (2025-11-17)

**IMPROVEMENT: Attribute handling and duplicate publication feedback**

1.  ✅ **Default Attribute Handling for "Not Applicable" and "Normal"** (`attributes.py`, `ids_dump.json`):
    *   **Problem**: When a scanned card lacked a specific "Energy" or "Card Type" (e.g., a Trainer card), or had a standard "Finish", these attributes were being skipped during product publication, leading to incomplete product data in Shoper.
    *   **Solution**:
        1.  The backend logic in `map_detected_to_shoper_attributes` was updated to automatically select a default option if no specific value is detected.
        2.  It now defaults to **"Nie dotyczy"** (Not Applicable) for "Energia" (Energy) and "Typ karty" (Card Type).
        3.  It now defaults to **"Normal"** for "Wykończenie" (Finish).
    *   **Implementation**: The correct `option_id`s for these new defaults (`182`, `183`, `184`) were fetched from the Shoper API and saved in the local `ids_dump.json` cache.
    *   **Result**: Products published from the application will now always have these critical attributes set, ensuring data consistency.

2.  ✅ **Fixed Silent Failure on Duplicate Publication** (`frontend/src/views/Scan.tsx`):
    *   **Problem**: When publishing a scan that was detected as a duplicate of an existing product, the UI would show no confirmation or error, making it seem like the action failed.
    *   **Root Cause**: The frontend was only prepared to handle the API response for a *new* product creation and did not correctly interpret the response for a stock update on an *existing* product.
    *   **Solution**: The success handler in the frontend was modified to correctly parse both types of responses.
    *   **Result**: The UI now displays a clear success message, such as "Updated existing product - stock increased to X", when a duplicate is published.

---

## Recent Changes (2025-11-17)

**FINAL FIX: Attributes must be in POST /products payload AND filtered by category**

1. ✅ **Attributes included DIRECTLY in POST /products during creation** (`shoper.py:1183-1190, 1335-1342`):
   - **Problem**: Attributes sent via separate PUT `/products/{id}/attributes` or PUT `/products/{id}` after creation were ignored
   - **Root Cause**: Shoper API only accepts attributes DURING product creation in POST payload, not via separate update
   - **Solution**: Added attributes directly to `build_shoper_payload()` and removed separate `set_product_attributes()` call
   - **Format** (verified from actual Shoper product 1081):
     ```json
     {
       "category_id": 70,
       "translations": {...},
       "stock": {...},
       "attributes": {
         "11": {"38": "Common", "65": "Reverse Holo"},
         "14": {"64": "Angielski"},
         "15": {"66": "Near Mint"}
       }
     }
     ```
   - **IMPORTANT**: Values are OPTION TEXT (e.g., "Near Mint"), NOT option IDs (not "176")!
   - **Result**: Attributes are now set correctly when product is created

2. ✅ **Reverted to option TEXT values** (`attributes.py:97-120, 208-220`):
   - **Discovery**: Actual Shoper products store attributes with TEXT values, not numeric IDs
   - **Example from product 1081**: `{"11": {"38": "Double Rare"}}` (text, not ID)
   - **Solution**: Reverted `_best_option_id()` to return option text value instead of option_id
   - **Result**: Attributes match Shoper's expected format

3. ✅ **Added attribute_group_id fallback** (`shoper.py:959-979, 1023-1040`):
   - **Problem**: Shoper API doesn't always return `attribute_group_id` in `/attributes` response
   - **Solution**: Added `_get_attribute_group_from_fallback()` to load group IDs from `ids_dump.json`
   - **Fallback mapping**:
     - Rzadkość (38) → Group 11
     - Typ karty (39) → Group 12
     - Energia (63) → Group 13
     - Język (64) → Group 14
     - Wykończenie (65) → Group 11
     - Jakość (66) → Group 15

4. ⚠️ **Removed POST-creation attribute update** (`shoper.py:1411-1423`):
   - Removed `set_product_attributes()` call after product creation
   - Endpoint `/products/{id}/attributes` does NOT work (returns errors or creates duplicate products)
   - Endpoint `PUT /products/{id}` with attributes field does NOT work (attributes ignored)
   - **Only working method**: Include attributes in POST `/products` payload during creation

5. ✅ **Filter attributes by category assignment** (`shoper.py:959-989, 1213-1235`):
   - **Problem**: Shoper API rejects attributes from groups not assigned to product's category
   - **Error**: `"Attribute '14' does not exist"` or `"Attribute '15' does not exist"`
   - **Root Cause**: Category 70 (White Flare) has groups `[11, 12, 13, 14]` but NOT group 15
   - **Solution**: Added `_get_category_attribute_groups()` to load allowed groups from `ids_dump.json`
   - **Filtering**: Only include attributes from groups assigned to the product's category
   - **Example**: Category 70 allows groups 11-14, so group 15 (Jakość) is filtered out
   - **Result**: No more "Attribute 'X' does not exist" errors

**Previous attribute fixes (2025-11-14):**

**ATTRIBUTE FIX: Attributes POST/PUT endpoint now works correctly**

1. ✅ **Attribute payload fixed** (`shoper.py:383-405`):
   - **Problem**: Shoper API was returning `400: "Wartość pola 'name' jest niepoprawna: Pole wymagane"` when trying to add attributes
   - **Root Cause**: Payload sent to attribute endpoints was missing `name` field in `translations` object
   - **Solution**: Added `"name": "Product"` placeholder to `translations` in `set_product_attributes()` method
   - **Format now**: `{ "translations": { "pl_PL": { "name": "Product", "active": true } }, "category_id": ..., "stock": ..., "11": { "66": "176" } }`
   - **Result**: Attributes now successfully added to products via PUT/POST after creation

2. ✅ **Payload field ordering optimized** (`shoper.py:383-405`):
   - `translations` field now added FIRST (some APIs require specific order)
   - Followed by `category_id`, `stock`, and then attribute groups
   - This ordering ensures Shoper API accepts the request

3. ⚠️ **Attribute assignment workflow** (Current Implementation):
   - Attributes are still added AFTER product creation via separate PUT/POST request
   - This is less efficient than including them in POST but works reliably with Shoper API
   - Future improvement: Consider adding attributes directly in product creation POST payload once Shoper API supports it

---

## Recent Changes (2025-11-13)

**CRITICAL FIX: Attributes endpoint payload structure**

1. ✅ **Attributes included in POST request** (`shoper.py:1080-1086, 1176`):
   - **FIXED**: Attributes are now correctly added directly in POST `/products` during product creation
   - **REMOVED**: Incorrect PUT request after product creation (removed completely)
   - **Format**: Nested object `{"11": {"66": "176", "38": "117"}}` grouped by `attribute_group_id` with STRING values
   - Implementation follows official Shoper API documentation (TworzenieProduktowShoperAPI.pdf pages 5-6)
   - **Previous bugs fixed**:
     - Attributes parameter was passed to `build_shoper_payload()` but never added to payload
     - Wrong format: array instead of nested object (causing "Attribute '0' does not exist" error)
     - Used integer values instead of strings
   - **Fix applied**: Correct nested structure with group_id as outer key, attribute_id:option_id pairs as strings

2. ✅ **Image upload verified correct** (`shoper.py:163-244, 1068-1069`):
   - Images uploaded to `/webapi2/gfx` (or `/webapi/rest/gfx`) as Base64
   - `gfx_id` correctly added to `stock.gfx_id` as INTEGER in product creation payload
   - Multi-endpoint fallback working correctly

3. ⚠️ **Warehouse code** (pending implementation):
   - Currently must be set manually via `/confirm` payload or `PATCH /scans/{id}/warehouse`
   - Future: Automatic generation and incrementation per session (format: `K1K1P001`, `K1K1P002`, etc.)

## Previous Changes (2025-01-12)

**Fixed critical issues in Shoper product publishing:**

1. ✅ **Image upload endpoint fallback** (`shoper.py:163-244`):
   - System now tries multiple GFX endpoints in sequence: `/webapi2/gfx`, `/webapi/rest/gfx`, `/gfx`
   - Fixes `400 "Missing MODULE 'gfx'"` errors by automatically retrying with different endpoints
   - Detailed logging for each upload attempt with status codes and error messages

2. ✅ **Attribute format corrected** (`shoper.py:823-874`):
   - Changed from dict format `{"66": "176"}` to numeric array `[{"attribute_id": 66, "option_id": 176}]`
   - Fixed `400 "Attribute 'X' has invalid option value"` errors

**New debugging capabilities:**
- Comprehensive logging throughout publication flow (image selection, upload, attribute mapping)
- See "Debugging Product Publishing" section for log interpretation guide
- Red flag indicators help identify issues before checking Shoper admin panel

## Project Overview

Kartoteka 2.0 is a Pokemon card scanning and inventory management system with mobile-first design. The system supports live camera scanning (Android), desktop file upload, card pricing, and direct integration with Shoper e-commerce platform.

**Stack:**
- Backend: FastAPI (Python 3.11) with SQLite database
- Frontend: React 18.3 + Vite 5.4 + TypeScript
- Deployment: Docker Compose (services on ports 8000 and 5173)

## Common Commands

### Development
```bash
# Build and start all services
docker compose up -d --build

# Rebuild single service (use ; separator in PowerShell)
docker compose build api; docker compose up -d api
docker compose build frontend; docker compose up -d frontend

# View logs
docker compose logs -f api
docker compose logs -f frontend

# Restart services
docker compose restart api
docker compose restart frontend
```

### Testing
```bash
# Backend tests (from root)
pytest -q

# Frontend type checking
cd frontend && npx tsc --noEmit
```

### Database Management
```bash
# Reset database (dev only - loses all data)
rm storage/app.db
docker compose restart api  # Will recreate schema on startup
```

### Mobile Development (Android via ADB)
```bash
# Connect via wireless debugging (Android 11+)
adb pair <IP>:<PAIRING_PORT>
adb connect <IP>:<DEBUG_PORT>

# Setup port forwarding for localhost access
adb reverse tcp:5173 tcp:5173
adb reverse tcp:8000 tcp:8000

# Access from Android browser: http://localhost:5173
```

## Architecture

### Request Flow
1. **Mobile Scan**: Android camera → `/scan/probe` (quality check) → `/scan/commit` (save + TCG lookup) → UI candidate selection → `/confirm` (finalize)
2. **Desktop Upload**: File upload → `/scan` (Vision OCR + TCG lookup) → form editing → `/confirm` (finalize)
3. **Pricing**: Manual search or live scan → `/pricing/estimate` (Cardmarket pricing) → display with variant multipliers
4. **Publishing**: Session-based batch → `/sessions/{id}/publish` (bulk create in Shoper)

### Core Backend Modules

**`backend/app/main.py`** (107KB) - Central FastAPI application
- Scan endpoints: `/scan/probe`, `/scan/commit`, `/scan`, `/confirm`
- Pricing: `/pricing/estimate`, `/pricing/manual_search`
- Sessions: `/sessions/start`, `/sessions/{id}/summary`, `/sessions/{id}/publish`
- Shoper integration: `/shoper/attributes`, `/shoper/categories`, `/sync/shoper`
- Push notifications: `/notifications/subscribe`, background order checking

**`backend/app/settings.py`** - Pydantic v2 configuration
- All env vars with aliases (e.g., `SHOPER_BASE_URL`)
- Uses `extra="ignore"` to prevent validation errors on unknown keys
- Key settings: quality thresholds, pricing multipliers, Shoper defaults, duplicate detection

**`backend/app/shoper.py`** (38KB) - Shoper e-commerce client
- Product creation with taxonomy mapping (sets → categories)
- **Image upload with multi-endpoint fallback** (lines 163-244):
  - Tries `/webapi2/gfx`, `/webapi/rest/gfx`, or `/gfx` in sequence
  - Base64 encoding with detailed logging for each attempt
  - Returns `gfx_id` for product association
- **Attribute assignment during product creation** (lines 853-913, 1080-1086):
  - Builds nested object format: `{"group_id": {"attribute_id": "option_id"}}` with STRING values
  - Maps detected scan data (condition, variant, rarity, etc.) to Shoper option IDs
  - Groups attributes by `attribute_group_id` from Shoper API response
  - Added DIRECTLY to POST `/products` request payload (not via separate PUT)
  - Function `build_product_attributes_payload()` creates the nested structure from scan data
- Taxonomy caching (TTL-based) with `ids_dump.json` fallback
- Handles variant attributes (Holo, Reverse Holo) and pricing
- Warehouse code assignment in `stock.additional_codes.warehouse`

**`backend/app/providers.py`** - Card data provider (RapidAPI + PokemonTCG fallback)
- Primary: `pokemon-tcg-api.p.rapidapi.com` with `x-rapidapi-key` header
- Fallback: `api.pokemontcg.io/v2/cards` (free API)
- Returns candidates with images, pricing, set info

**`backend/app/pricing.py`** - Price calculation engine
- EUR → PLN conversion (`EUR_PLN_RATE`, default 4.3)
- Final multiplier (`PRICE_MULTIPLIER`, default 1.24)
- Variant estimation: Holo (3.0x), Reverse Holo (2.0x) when API data missing
- Graded card prices (PSA/BGS/CGC) if available

**`backend/app/vision.py`** - OpenAI Vision OCR (optional)
- Extracts card name + number from uploaded images
- Falls back to filename parsing when `OPENAI_API_KEY` not set

**`backend/app/analysis/`** - Image analysis utilities
- `fingerprint.py`: Perceptual hashing for duplicate detection
- `pipeline.py`: Quality scoring for live scan frames
- `set_symbol.py`: Set logo recognition (unused in current flow)

**`backend/app/db.py`** - SQLAlchemy models
- Tables: `scans`, `products`, `sessions`, `session_scans`, `push_subscriptions`
- Uses `init_db()` for schema creation with safe `ALTER TABLE` migrations

### Frontend Architecture

**`frontend/src/App.tsx`** - Main application shell
- Platform detection (`isAndroid` based on user agent)
- Mobile: TabBar navigation (Home, Scan, Pricing, Dashboard)
- Desktop: Sidebar navigation + larger form layouts
- Manages active view state and callback handlers

**Key Views:**
- `Scan.tsx` (38KB): Desktop file upload + form editing, mobile live camera
- `Pricing.tsx` (15KB): Manual search + live scan modes, displays variant prices with visual rarity overlays
- `Home.tsx`: Dashboard with recent scans and quick actions
- `Inventory.tsx`: Product listing from local DB
- `Orders.tsx`: Shoper order integration

**Hooks:**
- `useLiveScan.ts` (17KB): Mobile camera handling for scan-to-inventory flow
- `useLivePricingScan.ts` (8KB): Mobile camera for pricing-only flow
- Both use callback refs for video element initialization
- Implement frame quality checking before sending to backend

**Components:**
- `AttributeForm.tsx`: Dynamic Shoper attribute mapping UI
- `SlideOutPanel.tsx`: Mobile panel for attribute editing
- `Sidebar.tsx` / `TabBar.tsx`: Navigation for desktop/mobile
- `Toast.tsx`: Notification system

### Integration Points

**Shoper (E-commerce Platform):**
- Requires: `SHOPER_BASE_URL` (e.g., `https://shop.shoparena.pl/webapi/rest`)
- Auth: `SHOPER_ACCESS_TOKEN` (Bearer token)
- Sync: `POST /sync/shoper` pulls products into local DB
- Publish: `POST /sessions/{id}/publish` creates products in batch
- Taxonomy: Categories and attributes cached with 60min TTL
- Images: Optional `SHOPER_IMAGE_BASE` for static image URLs (template: `{name}-{number}.jpg`)

**Card Data (TCG Provider):**
- Primary: RapidAPI (`RAPIDAPI_KEY` + `RAPIDAPI_HOST`)
- Endpoints: `/cards`, `/cards/search` with `search=name:<X> number:<Y>`
- Pricing from `prices.cardmarket.7d_average` (EUR)

**OpenAI Vision (Optional):**
- Set `OPENAI_API_KEY` for OCR on uploaded images
- Without key: uses filename-based parsing

**Push Notifications (Mobile):**
- VAPID keys: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`
- Service worker in `frontend/public/sw.js`
- Background task checks Shoper orders every 30s, sends push on new orders

## Configuration Management

When adding new settings:
1. Add field to `backend/app/settings.py` with type hints and `Field()` (include `alias=` for env var)
2. Update `docker-compose.yml` environment section
3. Update `backend/.env.example` with description
4. Update relevant documentation section in `README-LOCAL.md` or `AGENTS.md`

Example:
```python
# settings.py
new_feature_enabled: bool = Field(default=False, alias="NEW_FEATURE_ENABLED")

# docker-compose.yml
environment:
  - NEW_FEATURE_ENABLED=${NEW_FEATURE_ENABLED:-false}

# .env.example
NEW_FEATURE_ENABLED=false  # Enable experimental feature X
```

## Code Conventions

### Backend (Python)
- **Async-first**: Use `async def` for all I/O endpoints, `httpx.AsyncClient` for external calls
- **Error handling**: Return `JSONResponse({"error": "..."}, status_code=4xx/5xx)`
- **Type hints**: Required for all new code (PEP 484)
- **Line length**: 100-120 characters
- **Database**: SQLAlchemy with `init_db()` migrations (safe `ALTER TABLE` only)
- **Config**: All settings via Pydantic with env aliases, no hardcoded values

### Frontend (TypeScript)
- **Strict typing**: Explicit types for component props and API responses
- **Platform branching**: Use `isAndroid` for conditional rendering
- **Hooks over HOCs**: Extract complex logic into custom hooks
- **No default exports**: Use named exports for better refactoring
- **Mobile-first**: Live camera features take priority over file uploads in dual-mode components

### Git Workflow
- **Commits**: Conventional Commits in English (`feat(api): add pricing variants`)
- **Branches**: `main` (trunk), `feat/<desc>`, `fix/<desc>`, `hotfix/<desc>`
- **Types**: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `chore`
- **Scopes**: `api`, `frontend`, `docs`, `infra`
- **PRs**: Small, focused changes; include screenshots for UI changes

## Quality & Duplicate Detection

**Image Quality Scoring** (`/scan/probe`):
- `MIN_QUALITY_PROBE_WARN`: 0.45 (warning threshold for live view)
- `MIN_QUALITY_COMMIT`: 0.55 (minimum to accept scan)
- Checks: brightness, contrast, blur, edge detection

**Duplicate Detection** (`analysis/fingerprint.py`):
- Uses perceptual hashing (imagehash) before Vision call
- `DUPLICATE_DISTANCE_THRESHOLD`: 80 (Hamming distance)
- `DUPLICATE_USE_TILES`: Tile-based comparison for robustness
- Returns existing scan data to avoid re-scanning same card

## Mobile vs Desktop Differences

| Feature | Mobile (Android) | Desktop |
|---------|------------------|---------|
| Scan Input | Live camera (`<video>`) | File upload |
| Navigation | TabBar (bottom) | Sidebar (left) |
| Form Layout | Single column, panels | Two columns |
| Camera Controls | Torch, zoom slider, overlay | N/A |
| PWA Features | Service worker, push notifications | Optional |

**Critical**: When modifying shared components (e.g., `Scan.tsx`), always test both platforms. Use `isAndroid` flag for conditional logic, never assume desktop-only usage.

## Visual Effects (Rarity Overlays)

Frontend applies CSS effects based on card rarity in `styles.css`:
- `rarity-holo`: Holographic gradient animation
- `rarity-reverse-holo`: Reverse foil effect
- `rarity-rainbow-rare`: Multi-color shimmer
- `rarity-gold`: Metallic gold sheen
- `rarity-amazing-rare`: Vibrant rainbow
- `rarity-shiny`: Sparkle effect
- `rarity-full-art`: Subtle gradient
- `rarity-double-rare`: Two-tone animation

Applied in `Pricing.tsx` and scan result displays.

## API Integration Details

### Shoper API - Product Publishing

**Critical workflow for product creation:**

1. **Upload Image First** (`POST /webapi2/gfx` or `/webapi/rest/gfx`):
   - Send Base64-encoded image in `gfx.content` field with `gfx.file` (filename)
   - API returns `gfx_id` - save this for product creation
   - Implemented in `shoper.py:upload_gfx()` (lines 163-244)
   - **Multiple endpoint attempts**: System tries endpoints in order until one succeeds:
     1. `/webapi2/gfx` (newer API, preferred)
     2. `/webapi/rest/gfx` (standard API)
     3. `/gfx` (if base_url already contains `/webapi/rest`)
   - **Error handling**: Each endpoint attempt is logged with status code and error message
   - **Common errors**:
     - `400 "Missing MODULE 'gfx'"` → Wrong endpoint, system will retry with next variant
     - `401 Unauthorized` → Check `SHOPER_ACCESS_TOKEN`
     - `413 Payload Too Large` → Image file too big, resize before upload

2. **Create Product with Attributes** (`POST /webapi/rest/products`):
   - **Required fields**: `stock.price`, `translations.pl_PL.name`, `translations.pl_PL.active`
   - **Image**: Include `gfx_id` as `stock.gfx_id` (NUMBER, not string)
   - **Active flag**: `translations.pl_PL.active` must be `"1"` (string) for product visibility
   - **Stock**: Nested object with `code`, `price`, `stock`, `availability_id`, `delivery_id`
   - **Warehouse code**: Set in `stock.additional_codes.warehouse` (string)
   - **Attributes**: INCLUDE in POST request during product creation (see format below)
   - **Attributes Format**: Nested object grouped by `attribute_group_id` with STRING values!
   ```json
   {
     "stock": { "gfx_id": 12345, "price": 25.99 },
     "attributes": {
       "11": {
         "38": "117",   // Rarity: Rare (STRING values!)
         "66": "176"    // Condition: Near Mint
       }
     }
   }
   ```
   - **Critical**: Outer keys are `attribute_group_id` (string), inner keys are `attribute_id` (string), values are `option_id` (string)
   - All IDs must be STRINGS, not integers (e.g., `"38"` not `38`)
   - Get available attributes with group IDs from `GET /webapi/rest/attributes`
   - Each attribute has `attribute_group_id` field used for grouping
   - Implemented in `shoper.py:build_product_attributes_payload()` (lines 853-913)
   - Attributes added to payload in `build_shoper_payload()` (lines 1080-1086)
   - **Mapping logic** in `attributes.py:map_detected_to_shoper_attributes()`
   - Returns nested dict `{"group_id": {"attribute_id": "option_id"}}` with string values

**Common mistakes:**
- Forgetting to upload image before product creation → product has no image
- Not setting `stock.gfx_id` → image not linked to product
- Using wrong endpoint for GFX upload → 400 error (fixed: system now tries multiple endpoints)
- **NOT including attributes in POST** → Attributes will be missing from product
- **Using array format instead of nested object** → `400 "Attribute '0' does not exist"` error
- **Using integer IDs for attributes** → `400` error (must be strings!)
- **Wrong nested structure** → Must be `{"group_id": {"attr_id": "opt_id"}}` not `{"attr_id": "opt_id"}`
- **Missing attribute_group_id grouping** → Shoper API requires attributes grouped by group_id
- Setting `active: false` → product invisible in store
- Not setting `warehouse_code` → Product published without warehouse location

### TCGGO API (RapidAPI)

**Base URL**: `https://pokemon-tcg-api.p.rapidapi.com`

**Authentication**: Header `x-rapidapi-key` with RapidAPI key

**Key Endpoints**:
- `GET /cards?search=name` - Search cards by name
- `GET /cards/{cardId}` - Get card details
- `GET /episodes` - List all Pokemon TCG sets
- `GET /episodes/{id}/cards` - All cards from specific set

**Response Structure**:
```json
{
  "id": 3852,
  "name": "Giratina VSTAR",
  "rarity": "Rare Secret",
  "image": "https://...",  // Use this for product image
  "prices": {
    "cardmarket": {
      "currency": "EUR",
      "lowest_near_mint": 157.21,  // Primary price source
      "30d_average": 192.79
    },
    "tcg_player": {
      "currency": "USD",
      "market_price": 146.69
    }
  },
  "episode": {"name": "Crown Zenith"}
}
```

**Price Conversion**:
- Use `prices.cardmarket.lowest_near_mint` (EUR) as base
- Convert: `price_pln = eur_price * EUR_PLN_RATE * PRICE_MULTIPLIER`
- Default rates: `EUR_PLN_RATE=4.3`, `PRICE_MULTIPLIER=1.24`

**Image Handling**:
- TCGGO provides high-quality card images in `image` field
- Download and upload to Shoper GFX before product creation
- Store original URL in scan record for reference

### Image Source Selection

Users can choose between TCGGO images or local scans for product publishing:

**Database fields** (`Scan` model):
- `use_tcggo_image` (boolean, default=True): If true, use TCGGO image; if false, use local scan
- `additional_images` (text/JSON): Array of file paths for additional product images (back, details)

**API Endpoints**:
- `PATCH /scans/{scan_id}/image-settings` - Update image source preference
  ```json
  {
    "use_tcggo_image": false,
    "additional_images": ["/path/to/back.jpg", "/path/to/detail.jpg"]
  }
  ```
- `POST /scans/{scan_id}/upload-additional-image` - Upload additional image (multipart/form-data)
  - Saves to `storage/uploads/scan_{id}_extra_{timestamp}.jpg`
  - Automatically appends to `additional_images` list

**Publishing flow**:
1. If `use_tcggo_image=true` → download from `candidate.image` (TCGGO URL)
2. If `use_tcggo_image=false` → use `scan.stored_path` (local file)
3. All images uploaded as Base64 to Shoper `/webapi/rest/gfx` endpoint
4. Additional images uploaded after product creation via `/products/{id}/images`

**Important**: Shoper API does **NOT** accept image URLs - only Base64-encoded files. All images (TCGGO or local) are converted to Base64 before upload.

## Troubleshooting

### Mobile Issues

**Camera not working on mobile:**
- Ensure using `http://localhost:5173` via `adb reverse` OR HTTPS with valid cert
- Check browser permissions (tap padlock icon → Camera → Allow)
- Close other camera apps (WhatsApp, etc.)

**"Kamera zajęta" / Camera busy:**
- Kill background apps holding camera
- Restart browser

### API & Database Issues

**Frontend can't reach API:**
- Check `docker compose logs -f api` for startup errors
- Verify healthcheck passes: `curl http://localhost:8000/health`
- Confirm `depends_on: api: condition: service_healthy` in docker-compose.yml

**Database schema mismatch:**
- In dev: delete `storage/app.db` and restart (loses data)
- In prod: add safe migration to `init_db()` (ALTER TABLE ADD COLUMN IF NOT EXISTS)

**SQLite "disk I/O error":**
- Caused by permission issues with WAL mode files (`app.db-wal`, `app.db-shm`)
- **Solution 1**: Remove database files: `docker compose run --rm --user root api rm -rf /app/storage/app.db*`
- **Solution 2**: Changed to DELETE mode (db.py:30) to avoid WAL permission issues
- DELETE mode is safer in Docker environments with volume mounts
- If you need WAL mode back, ensure storage directory has proper permissions (777)

**Duplicate false positives:**
- Increase `DUPLICATE_DISTANCE_THRESHOLD` (default 80)
- Disable: `DUPLICATE_CHECK_ENABLED=false`

### Shoper Publishing Issues

**Product published without image:**
- **Symptom**: Product appears in Shoper but has no image, logs show `gfx_id=None`
- **Diagnosis**: Check logs for GFX upload attempts:
  ```
  DEBUG: Will try these endpoints in order: ['/webapi2/gfx', '/webapi/rest/gfx']
  DEBUG: Trying endpoint: https://.../webapi2/gfx
  DEBUG: Response status: 400
  ERROR: All GFX upload endpoints failed
  ```
- **Common causes**:
  - **Wrong endpoint**: Error `400 "Missing MODULE 'gfx'"` → System should auto-retry other endpoints
  - **Invalid auth**: Error `401 Unauthorized` → Check `SHOPER_ACCESS_TOKEN` is valid
  - **File too large**: Error `413 Payload Too Large` → Reduce image size before upload
  - **Image not available**: `image_to_upload=None` → Check `candidate.image` or `scan.stored_path` exists
- **Solution**:
  - Verify logs show successful upload: `SUCCESS: Image uploaded via ..., gfx_id=123`
  - If all endpoints fail, contact Shoper support to verify which GFX endpoint is enabled
  - Ensure `SHOPER_BASE_URL` does not duplicate path segments (e.g., not `https://shop.../webapi/rest/webapi/rest`)

**Attributes not assigned to product:**
- **Symptom**: Product published but has no attributes (condition, rarity, language, etc.)
- **Diagnosis**: Check logs for attribute mapping and product creation:
  ```
  DEBUG: Detected attributes data: {'language': 'pl', 'variant': None, 'condition': 'NM', ...}
  DEBUG: Raw mapping from attributes.py: {'66': '176', '38': '117'}
  INFO: Final attributes payload (nested object with group_id): {'11': {'66': '176', '38': '117'}}
  DEBUG: Added 2 attributes in 1 group(s) to POST payload
  INFO: Product creation payload:
  {
    "attributes": {
      "11": {
        "66": "176",
        "38": "117"
      }
    },
    ...
  }
  ```
- **Common causes**:
  - **Wrong format (array instead of nested object)**: `[{"attribute_id": 66}]` → Must be `{"11": {"66": "176"}}`
  - **Integer IDs instead of strings**: `{"11": {66: 176}}` → Must be `{"11": {"66": "176"}}` (all strings!)
  - **Missing group_id nesting**: `{"66": "176"}` → Must be grouped: `{"11": {"66": "176"}}`
  - **Invalid option_id**: Error `"Attribute 'X' has invalid option value"` → Check `ids_dump.json` for valid option IDs
  - **Missing detected data**: `'variant': None, 'condition': None` → Scan doesn't have these fields set
  - **Attribute mapping failure**: Empty `Mapped attributes` → Check `attributes.py` mapping logic
  - **Attributes not included in POST**: Check that payload contains `"attributes"` field
- **Solution**:
  - Verify attributes are built in `shoper.py:build_product_attributes_payload()` (lines 853-913)
  - Verify attributes are added to payload in `build_shoper_payload()` (lines 1080-1086)
  - Check `scan.detected_condition`, `scan.detected_variant`, etc. are set before publishing
  - Ensure attribute names in `attributes.py:attribute_targets` match Shoper attribute names
  - Verify payload includes `"attributes"` object (nested by group_id) in POST request
  - Check logs for "DEBUG: Added N attributes in M group(s) to POST payload" confirmation message

**Product published without warehouse code:**
- **Symptom**: Product has `"warehouse": ""` in `stock.additional_codes`
- **Cause**: Field `scan.warehouse_code` is `None` or empty before publishing
- **Solution**: Set warehouse code before publishing:
  ```bash
  # Option 1: Set via /confirm endpoint with warehouse_code in payload
  # Option 2: Set via dedicated endpoint
  curl -X PATCH http://localhost:8000/scans/{scan_id}/warehouse \
    -H "Content-Type: application/json" \
    -d '{"warehouse_code": "K1K1P001"}'
  ```
- **Future improvement**: Implement automatic warehouse code generation and incrementation per session

**Shoper sync fails:**
- Verify `SHOPER_BASE_URL` and `SHOPER_ACCESS_TOKEN` are set
- Check token hasn't expired
- Review API response in logs for 401/403 errors
- Ensure `SHOPER_BASE_URL` format: `https://shop123.shoparena.pl/webapi/rest` (no trailing slash)

### Debugging Product Publishing

**Monitoring logs during publication:**
```bash
# View all API logs in real-time
docker compose logs -f api

# Filter for important messages only
docker compose logs -f api | grep -E "(DEBUG|INFO|SUCCESS|WARNING|ERROR)"
```

**Expected log sequence for successful publication:**

1. **Image source selection**:
   ```
   DEBUG: primary_image=https://images.tcggo.com/tcggo/storage/23136/fennel.png
   DEBUG: candidate.image=https://images.tcggo.com/tcggo/storage/23136/fennel.png
   DEBUG: scan.stored_path=/app/storage/uploads/1762954806926_img2315.jpg
   INFO: Final image_to_upload=https://images.tcggo.com/tcggo/storage/23136/fennel.png
   ```

2. **Image download (if URL)**:
   ```
   INFO: Downloading image from URL: https://images.tcggo.com/...
   SUCCESS: Downloaded image to temp file: /tmp/tmpum84m_zm.png (400005 bytes)
   ```

3. **GFX upload with fallback**:
   ```
   DEBUG: Will try these endpoints in order: ['https://.../webapi2/gfx', 'https://.../webapi/rest/gfx']
   DEBUG: Trying endpoint: https://.../webapi2/gfx, filename=tmpum84m_zm.png, base64_length=533340
   DEBUG: Response status: 200
   SUCCESS: Image uploaded via https://.../webapi2/gfx, gfx_id=456
   INFO: Final gfx_id for product creation: 456
   ```

4. **Attribute mapping** (BEFORE product creation):
   ```
   DEBUG: Detected attributes data: {'language': 'pl', 'variant': 'Holo', 'condition': 'NM', 'rarity': 'Uncommon', ...}
   DEBUG: Raw mapping from attributes.py: {'66': '176', '38': '116', '65': '122'}
   INFO: Final attributes payload (nested object with group_id): {'11': {'66': '176', '38': '116', '65': '122'}}
   DEBUG: Added 3 attributes in 1 group(s) to POST payload
   ```

5. **Product creation payload** (with attributes included):
   ```
   INFO: Product creation payload:
   {
     "code": "PKM-BB-082-NM-NORM",
     "stock": {
       "gfx_id": 456,  ← Image linked
       "additional_codes": {
         "warehouse": "K1K1P001"  ← Warehouse code set
       }
     },
     "attributes": {  ← Attributes included in POST! (nested by group_id)
       "11": {
         "66": "176",  ← Condition: Near Mint
         "38": "116",  ← Rarity: Uncommon
         "65": "122"   ← Finish: Holo
       }
     }
   }
   ```

6. **Product created** (with attributes already set):
   ```
   INFO: Extracted product_id=1733 from response type=int
   ```

7. **Final result**:
   ```
   SUCCESS: Product published to Shoper with ID: 1733
   ```

**Red flags in logs (indicates problems):**
- `WARNING: No valid image file to upload` → No image will be uploaded
- `ERROR: All GFX upload endpoints failed` → Image upload failed completely
- `INFO: Final gfx_id for product creation: None` → Product will be created without image
- `"attributes": []` or missing in payload → Attributes will not be set
- `"warehouse": ""` in payload → No warehouse code set
- `'variant': None, 'condition': None` in detected data → Missing scan metadata

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + all endpoints
│   │   ├── settings.py          # Pydantic config
│   │   ├── db.py                # SQLAlchemy models
│   │   ├── shoper.py            # E-commerce integration
│   │   ├── providers.py         # TCG card API
│   │   ├── pricing.py           # Price calculation
│   │   ├── vision.py            # OpenAI OCR
│   │   ├── attributes.py        # Shoper attribute mapping
│   │   ├── schemas.py           # Pydantic request/response models
│   │   └── analysis/
│   │       ├── fingerprint.py   # Duplicate detection
│   │       ├── pipeline.py      # Quality scoring
│   │       └── set_symbol.py    # Set logo detection
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main shell + routing
│   │   ├── main.tsx             # Entry point
│   │   ├── styles.css           # Global styles + rarity effects
│   │   ├── views/
│   │   │   ├── Scan.tsx         # Scan + form editing
│   │   │   ├── Pricing.tsx      # Pricing tool
│   │   │   ├── Home.tsx         # Dashboard
│   │   │   ├── Inventory.tsx    # Product list
│   │   │   └── Orders.tsx       # Shoper orders
│   │   ├── hooks/
│   │   │   ├── useLiveScan.ts   # Camera for scan-to-inventory
│   │   │   └── useLivePricingScan.ts  # Camera for pricing
│   │   └── components/
│   │       ├── Sidebar.tsx      # Desktop nav
│   │       ├── TabBar.tsx       # Mobile nav
│   │       ├── AttributeForm.tsx # Shoper attributes
│   │       ├── SlideOutPanel.tsx # Mobile panel
│   │       └── Toast.tsx        # Notifications
│   ├── public/
│   │   └── sw.js                # Service worker (push notifications)
│   ├── Dockerfile
│   ├── package.json
│   └── tsconfig.json
├── storage/
│   ├── app.db                   # SQLite database (gitignored)
│   └── uploads/                 # Uploaded card images
├── legacy/                      # Old scripts (not used in current app)
├── docker-compose.yml           # Service orchestration
├── ids_dump.json                # Shoper taxonomy fallback
└── README.md                    # Setup instructions
```

## Testing Strategy

- **Backend**: Add unit tests for new business logic modules (alongside existing code)
- **Frontend**: Use `tsc --noEmit` for type checking before commits
- **Integration**: Manual testing required for Shoper publish flow (use `PUBLISH_DRY_RUN=true` for safe testing)
- **Mobile**: Always test camera features on actual Android device via ADB

**Note:** Legacy tests in `tests/` are not maintained for current MVP. Do not modify unless specifically required.
