from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Класс настроек для проекта"""
    api_key: str = Field(min_length=1, description="API ключ")
    database_url: str = Field(min_length=1, description="Ссылка на подключение к базе")
    rabbitmq_url: str = Field(min_length=1, description="Ссылка на подключение к rabbitmq")
    rabbitmq_management_url: str = Field("http://127.0.0.1:15672", description="Адрес для Management API")


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
