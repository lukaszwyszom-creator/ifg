from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_KEY_PATTERNS = ("change-me", "secret", "test", "dev", "local", "example")

DEFAULT_SELLER_NIP = "9670402857"
DEFAULT_SELLER_NAME = "Ikona Małgorzata Katarzyna Krzyżanowska-Witkowska"
DEFAULT_SELLER_STREET = "Kossaka"
DEFAULT_SELLER_BUILDING_NO = "72"
DEFAULT_SELLER_APARTMENT_NO = ""
DEFAULT_SELLER_POSTAL_CODE = "85-307"
DEFAULT_SELLER_CITY = "Bydgoszcz"
DEFAULT_SELLER_COUNTRY = "PL"


class Settings(BaseSettings):
    # Produkcja (DS723+): docker-compose.prod.yml montuje .env.production jako /app/.env.
    # env_ignore_empty: pusty REGON_API_KEY="" z Docker Compose nie blokuje wartości z pliku .env.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    app_name: str = Field(default="KSeF Backend", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(alias="DATABASE_URL")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=20, alias="DATABASE_MAX_OVERFLOW")
    contractor_cache_ttl_days: int = Field(default=7, alias="CONTRACTOR_CACHE_TTL_DAYS")

    jwt_secret_key: str | None = Field(default=None, alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    initial_admin_username: str | None = Field(default=None, alias="INITIAL_ADMIN_USERNAME")
    initial_admin_password: str | None = Field(default=None, alias="INITIAL_ADMIN_PASSWORD")

    ksef_environment: str = Field(default="test", alias="KSEF_ENVIRONMENT")
    ksef_auth_token: str | None = Field(default=None, alias="KSEF_AUTH_TOKEN")
    ksef_timeout_seconds: int = Field(default=30, alias="KSEF_TIMEOUT_SECONDS")
    ksef_auth_redeem_timeout_seconds: int = Field(default=120, alias="KSEF_AUTH_REDEEM_TIMEOUT_SECONDS")
    regon_environment: str = Field(default="production", alias="REGON_ENVIRONMENT")
    regon_api_key: str | None = Field(default=None, alias="REGON_API_KEY")

    @field_validator("regon_api_key", mode="before")
    @classmethod
    def _empty_regon_api_key_as_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value
    regon_wsdl_test: str = Field(
        default="https://wyszukiwarkaregontest.stat.gov.pl/wsBIR/wsdl/UslugaBIRzewnPubl-ver11-test.wsdl",
        alias="REGON_WSDL_TEST",
    )
    regon_wsdl_production: str = Field(
        default="https://wyszukiwarkaregon.stat.gov.pl/wsBIR/wsdl/UslugaBIRzewnPubl-ver11-prod.wsdl",
        alias="REGON_WSDL_PRODUCTION",
    )
    request_timeout_seconds: int = Field(default=15, alias="REQUEST_TIMEOUT_SECONDS")

    seller_nip: str | None = Field(default=DEFAULT_SELLER_NIP, alias="SELLER_NIP")
    seller_name: str | None = Field(default=DEFAULT_SELLER_NAME, alias="SELLER_NAME")
    seller_street: str | None = Field(default=DEFAULT_SELLER_STREET, alias="SELLER_STREET")
    seller_building_no: str | None = Field(default=DEFAULT_SELLER_BUILDING_NO, alias="SELLER_BUILDING_NO")
    seller_apartment_no: str | None = Field(default=DEFAULT_SELLER_APARTMENT_NO, alias="SELLER_APARTMENT_NO")
    seller_postal_code: str | None = Field(default=DEFAULT_SELLER_POSTAL_CODE, alias="SELLER_POSTAL_CODE")
    seller_city: str | None = Field(default=DEFAULT_SELLER_CITY, alias="SELLER_CITY")
    seller_country: str = Field(default=DEFAULT_SELLER_COUNTRY, alias="SELLER_COUNTRY")

    # Monitoring
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    alert_webhook_url: str | None = Field(default=None, alias="ALERT_WEBHOOK_URL")

    # Feature flags
    enable_ksef: bool = Field(default=True, alias="ENABLE_KSEF")
    enable_warehouse: bool = Field(default=True, alias="ENABLE_WAREHOUSE")
    enable_payments: bool = Field(default=True, alias="ENABLE_PAYMENTS")

    # KSeF — synchronizacja faktur zakupowych
    ksef_purchase_sync_days_back: int = Field(default=90, alias="KSEF_PURCHASE_SYNC_DAYS_BACK")
    ksef_purchase_sync_full_days: int = Field(default=365, alias="KSEF_PURCHASE_SYNC_FULL_DAYS")
    ksef_purchase_sync_overlap_days: int = Field(default=2, alias="KSEF_PURCHASE_SYNC_OVERLAP_DAYS")
    ksef_auto_sync_enabled: bool = Field(default=False, alias="KSEF_AUTO_SYNC_ENABLED")
    ksef_auto_sync_cron: str = Field(default="0 8,14,20 * * *", alias="KSEF_AUTO_SYNC_CRON")

    # Powiadomienia e-mail po synchronizacji zakupów KSeF (GWO-IFG-NOTIFY-0001/0002)
    purchase_sync_notify_enabled: bool = Field(default=False, alias="PURCHASE_SYNC_NOTIFY_ENABLED")
    purchase_sync_notify_recipients: str | None = Field(
        default=None, alias="PURCHASE_SYNC_NOTIFY_RECIPIENTS"
    )
    purchase_sync_notify_email: str | None = Field(
        default=None,
        alias="PURCHASE_SYNC_NOTIFY_EMAIL",
        description="Deprecated — użyj PURCHASE_SYNC_NOTIFY_RECIPIENTS",
    )
    purchase_sync_notify_max_attempts: int = Field(
        default=5, alias="PURCHASE_SYNC_NOTIFY_MAX_ATTEMPTS"
    )
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from: str | None = Field(default=None, alias="SMTP_FROM")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")

    @field_validator(
        "seller_nip",
        "seller_name",
        "seller_street",
        "seller_building_no",
        "seller_apartment_no",
        "seller_postal_code",
        "seller_city",
        "seller_country",
        mode="before",
    )
    @classmethod
    def _strip_seller_value(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def _validate_production_security(self) -> "Settings":
        if self.app_env != "production":
            return self

        errors: list[str] = []

        # JWT_SECRET_KEY — musi istnieć, mieć ≥32 znaków i nie być domyślną wartością
        key = self.jwt_secret_key or ""
        if not key:
            errors.append("JWT_SECRET_KEY jest wymagany w trybie production.")
        elif len(key) < 32:
            errors.append(
                f"JWT_SECRET_KEY jest za krótki ({len(key)} znaków); wymagane minimum 32."
            )
        elif any(pat in key.lower() for pat in _INSECURE_KEY_PATTERNS):
            errors.append(
                "JWT_SECRET_KEY zawiera wartość domyślną/testową — zmień na losowy klucz."
            )

        # DEBUG musi być wyłączony na produkcji
        if self.debug:
            errors.append("DEBUG=true jest niedopuszczalne w trybie production.")

        if errors:
            raise ValueError(
                "BLOKADA STARTU — konfiguracja produkcyjna jest niezabezpieczona:\n"
                + "\n".join(f"  \u2022 {e}" for e in errors)
            )

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
