from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "ResultKraft API"
    environment: str = "development"
    debug: bool = True

    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""

    # Gemini AI (only for custom NLP commands)
    gemini_api_key: str = ""

    # Razorpay
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # Cloudflare R2
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_uploads: str = "resultkraft-uploads"
    r2_bucket_reports: str = "resultkraft-reports"

    # Email (Brevo)
    brevo_api_key: str = ""

    # App
    frontend_url: str = "http://localhost:3000"
    secret_key: str = "change-me-in-production"
    max_file_size_mb: int = 50
    max_files_per_request: int = 5

    # Rate limits
    upload_rate_limit: str = "10/minute"
    ai_command_rate_limit: str = "20/minute"
    payment_rate_limit: str = "5/minute"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
