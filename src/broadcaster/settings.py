"""
Application settings using Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Required:
        TELEGRAM_BOT_TOKEN: Your Telegram bot token from @BotFather
        ADMIN_TELEGRAM_ID: Admin Telegram user ID(s) - comma-separated for multiple
    
    Optional:
        DATABASE_PATH: Path to SQLite database file (defaults to broadcaster.db)
        WEBHOOK_URL: Public URL for Telegram webhook (Railway provides this)
        PORT: Server port (Railway sets this dynamically)
    """
    
    # Required
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    admin_telegram_id: str = Field(..., env="ADMIN_TELEGRAM_ID")  # Comma-separated
    
    # Optional
    database_path: str = Field("broadcaster.db", env="DATABASE_PATH")
    webhook_url: Optional[str] = Field(None, env="WEBHOOK_URL")
    webhook_path: str = Field("/webhook", env="WEBHOOK_PATH")
    
    # Server
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    
    # Feature flags
    enable_websocket: bool = Field(True, env="ENABLE_WEBSOCKET")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def admin_ids(self) -> List[int]:
        """Parse admin_telegram_id into a list of integers."""
        ids = []
        for id_str in self.admin_telegram_id.split(","):
            id_str = id_str.strip()
            if id_str:
                try:
                    ids.append(int(id_str))
                except ValueError:
                    pass
        return ids
    
    @property
    def full_webhook_url(self) -> str:
        """Get the full webhook URL including path."""
        if not self.webhook_url:
            return ""
        base = self.webhook_url.rstrip("/")
        path = self.webhook_path.lstrip("/")
        return f"{base}/{path}"


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get application settings (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
