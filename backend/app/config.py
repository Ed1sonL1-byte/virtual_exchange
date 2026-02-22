from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_metaverse"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    binance_base_url: str = "https://api.binance.com"
    price_update_interval: int = 120  # seconds
    initial_balance: float = 10000.0  # USDT for new users
    spot_fee_rate: float = 0.001  # 0.1%
    amm_fee_rate: float = 0.003  # 0.3%
    maintenance_margin_rate: float = 0.005  # 0.5%
    funding_rate: float = 0.0001  # 0.01%

    class Config:
        env_file = ".env"


settings = Settings()
