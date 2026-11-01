from pathlib import Path
from typing import Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPOSITORY_ROOT / "backend" / ".env", extra="ignore")

    app_name: str = "DataTrace"
    environment: str = "development"
    database_url: str = f"sqlite:///{(REPOSITORY_ROOT / 'datasets' / 'datatrace.db').as_posix()}"
    storage_dir: Path = REPOSITORY_ROOT / "datasets" / "generated" / "uploads"
    output_dir: Path = REPOSITORY_ROOT / "datasets" / "output"
    quarantine_dir: Path = REPOSITORY_ROOT / "datasets" / "quarantine"
    customer_master_path: Path = REPOSITORY_ROOT / "datasets" / "sample" / "customer_master.csv"
    merchant_master_path: Path = REPOSITORY_ROOT / "datasets" / "sample" / "merchant_master.csv"
    max_upload_bytes: int = 10 * 1024 * 1024
    ai_provider: str = "auto"
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = "z-ai/glm-5.3-flash"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    ai_timeout_seconds: float = 12.0
    ai_budget_usd: float = 1.0
    ai_input_cost_per_million_usd: float = 0.075
    ai_output_cost_per_million_usd: float = 0.25
    ai_max_input_tokens: int = 1800
    ai_max_output_tokens: int = 1200
    ai_max_retries: int = 0
    ai_cache_enabled: bool = True
    profile_sample_size: int = 5000
    max_processing_rows: int = 500_000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    log_level: str = "INFO"

    @field_validator(
        "storage_dir",
        "output_dir",
        "quarantine_dir",
        "customer_master_path",
        "merchant_master_path",
        mode="before",
    )
    @classmethod
    def resolve_relative_paths(cls, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else REPOSITORY_ROOT / path

    @model_validator(mode="after")
    def reject_wildcard_cors_in_production(self) -> Self:
        if self.environment.lower() in {"prod", "production"} and "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS must not contain '*' in production.")
        if self.ai_timeout_seconds <= 0 or self.ai_timeout_seconds > 60:
            raise ValueError("AI_TIMEOUT_SECONDS must be greater than 0 and at most 60.")
        if not 0 < self.ai_budget_usd <= 1000:
            raise ValueError("AI_BUDGET_USD must be greater than 0 and at most 1000.")
        if min(self.ai_input_cost_per_million_usd, self.ai_output_cost_per_million_usd) < 0:
            raise ValueError("AI token prices cannot be negative.")
        if not 1 <= self.ai_max_input_tokens <= 20_000:
            raise ValueError("AI_MAX_INPUT_TOKENS must be between 1 and 20,000.")
        if not 1 <= self.ai_max_output_tokens <= 4_000:
            raise ValueError("AI_MAX_OUTPUT_TOKENS must be between 1 and 4,000.")
        if not 0 <= self.ai_max_retries <= 2:
            raise ValueError("AI_MAX_RETRIES must be between 0 and 2.")
        if not 100 <= self.profile_sample_size <= 100_000:
            raise ValueError("PROFILE_SAMPLE_SIZE must be between 100 and 100,000.")
        if not 1 <= self.max_processing_rows <= 5_000_000:
            raise ValueError("MAX_PROCESSING_ROWS must be between 1 and 5,000,000.")
        if self.ai_provider.casefold() not in {"auto", "openrouter", "gemini", "none"}:
            raise ValueError("AI_PROVIDER must be auto, openrouter, gemini, or none.")
        if not self.openrouter_model.strip() or len(self.openrouter_model) > 180:
            raise ValueError("OPENROUTER_MODEL must contain a model ID up to 180 characters.")
        return self
