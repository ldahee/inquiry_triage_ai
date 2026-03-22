import json
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_base_url: Optional[str] = None

    # Model per agent
    router_model: str = "gpt-4o-mini"
    billing_model: str = "gpt-4o-mini"
    account_model: str = "gpt-4o-mini"
    technical_support_model: str = "gpt-4o-mini"
    shipping_model: str = "gpt-4o-mini"
    fallback_model: str = "gpt-4o-mini"
    safety_model: str = "gpt-4o-mini"

    # Routing policy
    routing_confidence_low_threshold: float = 0.50
    max_llm_calls: int = 5
    max_retry_count: int = 2

    # Database
    database_url: Optional[str] = None

    # Environment
    environment: str = "development"  # "development" | "production"

    # Security
    # ALLOWED_ORIGINS: JSON 배열 또는 쉼표 구분 문자열 e.g. '["https://app.example.com"]' 또는 'https://app.example.com'
    allowed_origins: List[str] = ["http://localhost:3000"]
    # API 키가 설정된 경우 모든 요청에 X-API-Key 헤더 필요
    api_key: Optional[str] = None
    # 운영자 모드(mode=operator) 접근에 필요한 별도 키
    operator_api_key: Optional[str] = None
    # Rate limiting: slowapi 형식 e.g. "20/minute"
    rate_limit: str = "20/minute"

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if not v or (isinstance(v, str) and not v.strip()):
            return ["http://localhost:3000"]
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return v

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
