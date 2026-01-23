"""Configuration loading for Review Fraud Workshop."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and config files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Application settings
    app_name: str = "Review Fraud Workshop"
    app_version: str = "1.0.0"
    debug: bool = False

    # Elasticsearch settings
    elasticsearch_url: Optional[str] = Field(default=None, alias="ELASTICSEARCH_URL")
    es_host: str = Field(default="localhost", alias="ELASTICSEARCH_HOST")
    es_port: int = Field(default=9200, alias="ELASTICSEARCH_PORT")
    es_scheme: str = Field(default="http", alias="ELASTICSEARCH_SCHEME")
    es_username: Optional[str] = Field(default=None, alias="ELASTICSEARCH_USERNAME")
    es_password: Optional[str] = Field(default=None, alias="ELASTICSEARCH_PASSWORD")
    es_api_key: Optional[str] = Field(default=None, alias="ELASTICSEARCH_API_KEY")
    es_cloud_id: Optional[str] = Field(default=None, alias="ELASTICSEARCH_CLOUD_ID")
    es_verify_certs: bool = Field(default=True, alias="ELASTICSEARCH_VERIFY_CERTS")

    # Index names
    reviews_index: str = "reviews"
    businesses_index: str = "businesses"
    users_index: str = "users"
    incidents_index: str = "incidents"
    notifications_index: str = "notifications"

    # Streaming settings
    review_generation_interval: float = 1.0  # seconds between generated reviews
    batch_size: int = 10  # reviews per batch

    @property
    def es_url(self) -> str:
        """Get the full Elasticsearch URL."""
        return f"{self.es_scheme}://{self.es_host}:{self.es_port}"

    @classmethod
    def load_from_yaml(cls, yaml_path: str = "config/config.yaml") -> "Settings":
        """Load settings from YAML config file, with env overrides."""
        config_data = {}

        yaml_file = Path(yaml_path)
        if yaml_file.exists():
            with open(yaml_file, "r") as f:
                yaml_config = yaml.safe_load(f) or {}

            # Flatten nested YAML structure
            if "elasticsearch" in yaml_config:
                es_config = yaml_config["elasticsearch"]
                config_data["es_host"] = es_config.get("host", "localhost")
                config_data["es_port"] = es_config.get("port", 9200)
                config_data["es_scheme"] = es_config.get("scheme", "http")
                config_data["es_username"] = es_config.get("username")
                config_data["es_password"] = es_config.get("password")
                config_data["es_api_key"] = es_config.get("api_key")
                config_data["es_cloud_id"] = es_config.get("cloud_id")
                config_data["es_verify_certs"] = es_config.get("verify_certs", True)

            if "indices" in yaml_config:
                indices = yaml_config["indices"]
                config_data["reviews_index"] = indices.get("reviews", "yelp_reviews")
                config_data["businesses_index"] = indices.get("businesses", "yelp_businesses")
                config_data["users_index"] = indices.get("users", "yelp_users")
                config_data["incidents_index"] = indices.get("incidents", "review_fraud_incidents")
                config_data["notifications_index"] = indices.get("notifications", "review_fraud_notifications")

            if "app" in yaml_config:
                app_config = yaml_config["app"]
                config_data["app_name"] = app_config.get("name", "Review Fraud Workshop")
                config_data["debug"] = app_config.get("debug", False)

            if "streaming" in yaml_config:
                streaming = yaml_config["streaming"]
                config_data["review_generation_interval"] = streaming.get("interval", 1.0)
                config_data["batch_size"] = streaming.get("batch_size", 10)

        # Filter out None values
        config_data = {k: v for k, v in config_data.items() if v is not None}

        return cls(**config_data)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings.load_from_yaml()
