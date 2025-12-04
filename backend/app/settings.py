from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # Ignore unknown env keys to prevent ValidationError on extras
    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True, extra="ignore")
    app_name: str = Field(default="Card Scanner API")
    environment: str = Field(default="development")
    upload_dir: str = Field(default="/app/storage/uploads")
    allowed_origins: str = Field(default="*")  # comma separated
    database_url: str = Field(default="sqlite:////app/storage/app.db")
    eur_pln_rate: float = Field(default=4.3)
    price_multiplier: float = Field(default=1.23)

    # Placeholders for future integrations
    openai_api_key: str | None = None
    shoper_client_id: str | None = None
    shoper_client_secret: str | None = None
    shoper_base_url: str | None = Field(default=None, alias="SHOPER_BASE_URL")
    shoper_access_token: str | None = Field(default=None, alias="SHOPER_ACCESS_TOKEN")
    shoper_products_path: str = Field(default="/products", alias="SHOPER_PRODUCTS_PATH")
    shoper_orders_path: str = Field(default="/orders", alias="SHOPER_ORDERS_PATH")
    shoper_users_path: str = Field(default="/users", alias="SHOPER_USERS_PATH")
    # Optional taxonomy paths (fallbacks handled in client)
    shoper_attributes_path: str = Field(default="/attributes", alias="SHOPER_ATTRIBUTES_PATH")
    shoper_categories_path: str = Field(default="/categories", alias="SHOPER_CATEGORIES_PATH")
    shoper_languages_path: str = Field(default="/languages", alias="SHOPER_LANGUAGES_PATH")
    shoper_availability_path: str = Field(default="/availability", alias="SHOPER_AVAILABILITY_PATH")
    sales_metrics_ttl_minutes: int = Field(default=5, alias="SALES_METRICS_TTL_MINUTES")
    shoper_image_base: str | None = Field(default=None, alias="SHOPER_IMAGE_BASE")
    shoper_auto_sync_on_startup: bool = Field(default=True)
    shoper_sync_ttl_minutes: int = Field(default=15)
    shoper_taxonomy_ttl_minutes: int = Field(default=60)
    # Publish defaults
    price_multiplier: float = 1.2
    publish_dry_run: bool = False

    # VAPID keys for push notifications
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    
    # ntfy.sh configuration for rich mobile notifications
    ntfy_enabled: bool = Field(default=False, alias="NTFY_ENABLED")
    ntfy_url: str = Field(default="http://ntfy", alias="NTFY_URL")
    ntfy_topic: str = Field(default="kartoteka-orders", alias="NTFY_TOPIC")
    ntfy_priority: str = Field(default="urgent", alias="NTFY_PRIORITY")
    ntfy_auth_token: str | None = Field(default=None, alias="NTFY_AUTH_TOKEN")
    app_base_url: str = Field(default="http://localhost:5173", alias="APP_BASE_URL")
    
    default_tax_id: int = Field(default=1)
    default_producer_id: int = Field(default=23)
    default_lang_id: int = Field(default=1)
    default_language_code: str = Field(default="pl_PL")
    default_availability_id: int = Field(default=2)
    default_delivery_id: int = Field(default=3)
    default_unit_id: int = Field(default=1)
    code_prefix: str = Field(default="PKM")
    image_name_template: str = Field(default="{name}-{number}.jpg")
    # Map set name -> Shoper category_id (override via env as JSON)
    set_category_map_json: str | None = Field(default=None, alias="SET_CATEGORY_MAP")
    # Map set or category display name -> code used in product code (e.g., Destined Rivals -> DR)
    set_code_map_json: str | None = Field(default=None, alias="SET_CODE_MAP")
    tcggo_api_key: str | None = None
    # RapidAPI (TCGGO provider)
    rapidapi_key: str | None = Field(default=None, alias="RAPIDAPI_KEY")
    rapidapi_host: str = Field(default="pokemon-tcg-api.p.rapidapi.com", alias="RAPIDAPI_HOST")
    tcggo_base_url: str = Field(default="https://pokemon-tcg-api.p.rapidapi.com")
    tcggo_search_path: str = Field(default="/cards")
    tcggo_search_search_path: str = Field(default="/cards/search")
    tcggo_sort: str = Field(default="episode_newest")
    
    # Pokemon TCG API (pokemontcg.io)
    pokemontcg_io_api_key: str | None = Field(default=None, alias="POKEMONTCG_IO_API_KEY")

    # Duplicate detection (fingerprint) before Vision
    duplicate_check_enabled: bool = Field(default=True, alias="DUPLICATE_CHECK_ENABLED")
    duplicate_distance_threshold: int = Field(default=80, alias="DUPLICATE_DISTANCE_THRESHOLD")
    duplicate_use_tiles: bool = Field(default=True, alias="DUPLICATE_USE_TILES")
    shoper_force_image_upload: bool = Field(default=False, alias="SHOPER_FORCE_IMAGE_UPLOAD")
    # Optional path to a newline-separated list of Pokemon names for OCR correction
    pokemon_names_path: str | None = Field(default=None, alias="POKEMON_NAMES_PATH")

    # Quality gates
    min_quality_probe_warn: float = Field(default=0.45, alias="MIN_QUALITY_PROBE_WARN")
    min_quality_commit: float = Field(default=0.55, alias="MIN_QUALITY_COMMIT")

    # Price auto-update settings
    price_auto_update_enabled: bool = Field(default=False, alias="PRICE_AUTO_UPDATE_ENABLED")
    price_update_interval_hours: int = Field(default=24, alias="PRICE_UPDATE_INTERVAL_HOURS")
    min_price_pln: float = Field(default=0.10, alias="MIN_PRICE_PLN") # Deprecated default, used as fallback absolute minimum
    max_price_change_percent: float = Field(default=50.0, alias="MAX_PRICE_CHANGE_PERCENT")
    
    # Purchase Cost & Dynamic Minimum Pricing Logic
    min_price_common: float = Field(default=0.10, alias="MIN_PRICE_COMMON")
    min_price_uncommon: float = Field(default=0.10, alias="MIN_PRICE_UNCOMMON")
    min_price_rare: float = Field(default=0.10, alias="MIN_PRICE_RARE")
    min_price_premium_percent: float = Field(default=0.80, alias="MIN_PRICE_PREMIUM_PERCENT")
    
    premium_rarities: list[str] = Field(
        default=[
            "Double Rare", 
            "Illustration Rare", 
            "Special Illustration Rare", 
            "Hyper Rare", 
            "Ultra Rare", 
            "Secret Rare", 
            "SIR", 
            "HR", 
            "UR"
        ],
        alias="PREMIUM_RARITIES"
    )

    # Price estimation multipliers (when variant price is not available)
    holo_price_multiplier: float = Field(default=3.0, alias="HOLO_PRICE_MULTIPLIER")
    reverse_holo_price_multiplier: float = Field(default=2.0, alias="REVERSE_HOLO_PRICE_MULTIPLIER")

    # Furgonetka API Integration
    furgonetka_client_id: str | None = Field(default=None, alias="FURGONETKA_CLIENT_ID")
    furgonetka_client_secret: str | None = Field(default=None, alias="FURGONETKA_CLIENT_SECRET")
    furgonetka_base_url: str = Field(default="https://sandbox.furgonetka.pl", alias="FURGONETKA_BASE_URL")
    furgonetka_sandbox_mode: bool = Field(default=True, alias="FURGONETKA_SANDBOX_MODE")
    furgonetka_redirect_uri: str = Field(default="http://localhost:8000/furgonetka/oauth/callback", alias="FURGONETKA_REDIRECT_URI")
    
    # Carrier service mapping (Shoper delivery_method_id -> Furgonetka service code)
    # Example: {"15": "inpost", "16": "dpd_pickup", "17": "orlen", "18": "dhl"}
    furgonetka_service_map: str | None = Field(default=None, alias="FURGONETKA_SERVICE_MAP")
    
    # Default sender address (your warehouse)
    furgonetka_sender_name: str = Field(default="", alias="FURGONETKA_SENDER_NAME")
    furgonetka_sender_street: str = Field(default="", alias="FURGONETKA_SENDER_STREET")
    furgonetka_sender_city: str = Field(default="", alias="FURGONETKA_SENDER_CITY")
    furgonetka_sender_postcode: str = Field(default="", alias="FURGONETKA_SENDER_POSTCODE")
    furgonetka_sender_phone: str = Field(default="", alias="FURGONETKA_SENDER_PHONE")
    furgonetka_sender_email: str = Field(default="", alias="FURGONETKA_SENDER_EMAIL")

    # Note: Do NOT define a nested Config when using model_config (pydantic v2)


settings = Settings()
