from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional, Tuple, Union

from pydantic_settings import BaseSettings, SettingsConfigDict

# Satış kredisi = `polygon_gas_cost_cents_estimate` × bu sabit (ürün politikası; env yok).
SALE_CREDIT_MULTIPLIER = 10


def _env_files() -> Union[Tuple[str, ...], Tuple[()]]:
    # unittest: TURKDAMGA_TESTING=1 iken .env okunmaz (CI / yerel çakışma önlenir)
    if os.getenv("TURKDAMGA_TESTING") == "1":
        return ()
    return (".env",)


class Settings(BaseSettings):
    """Ortam değişkenleri; tam alan listesi için TurkDamga-Backend.md."""

    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "TurkDamga"
    app_version: str = "0.1.0"
    debug: bool = False

    # JWT (auth); üretimde güçlü SECRET_KEY kullanın
    secret_key: str = "dev-secret-change-in-production-min-32-characters!!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    # KVKK: damga ↔ kişi eşlemesi için HMAC anahtarı (ham TC saklanmaz)
    subject_tc_hmac_secret: str = "dev-tc-hmac-secret-min-32-chars-change-me!!"

    database_url: Optional[str] = None

    # Polygon GAS (cent) → satış kredisi: **sabit kural maliyet × 10** (ürün politikası).
    # Örn. tahmini maliyet 1¢ → müşteri 10 kredi öder (kredi soyut birim).
    polygon_gas_cost_cents_estimate: int = 1
    signup_bonus_credits: int = 10_000

    def stamp_credit_cost(self) -> int:
        base = max(1, int(self.polygon_gas_cost_cents_estimate))
        return max(1, base * SALE_CREDIT_MULTIPLIER)


@lru_cache
def get_settings() -> Settings:
    return Settings()
