from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration from environment variables."""
    
    # Groq AI Configuration
    groq_api_key: str
    groq_model: str = "mixtral-8x7b-32768"
    
    # Backend API
    api_auth_token: str
    backend_port: int = 8000
    
    # Security
    allowed_domains: str = "example.com,test.local,localhost"
    browser_session_timeout: int = 300  # seconds
    task_timeout: int = 120  # seconds
    max_request_size: int = 10485760  # 10MB
    
    # Browser Configuration
    headless: bool = True
    browser_binary_path: Optional[str] = None
    
    # Development
    debug: bool = False
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def allowed_domains_list(self) -> list[str]:
        """Parse allowed domains into a list."""
        return [d.strip() for d in self.allowed_domains.split(",")]


settings = Settings()
