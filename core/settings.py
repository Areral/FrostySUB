import os
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional
from loguru import logger


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TG_BOT_TOKEN: Optional[str] = None
    TG_CHAT_ID: Optional[str] = None
    TG_TOPIC_ID: str = "7"
    SUBSCRIPTION_SOURCES: Optional[str] = None

    parser: dict = Field(default_factory=lambda: {
        "max_accounts_per_server": 5,
    })
    
    system: dict = Field(default_factory=lambda: {
        "threads": 25,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    })
    
    checking: dict = Field(default_factory=lambda: {
        "min_speed": 1.0,
        "max_latency": 5000,
        "speedtest_url": "https://speed.cloudflare.com/__down?bytes=5000000",
        "champion_test_url": "https://speed.cloudflare.com/__down?bytes=20000000",
        "connectivity_urls":[
            "http://www.gstatic.com/generate_204",
            "http://cp.cloudflare.com/generate_204",
            "http://captive.apple.com/hotspot-detect.html",
            "http://edge-http.microsoft.com/captiveportal/generate_204",
            "http://detectportal.firefox.com/success.txt",
            "http://wifi.vivo.com.cn/generate_204",
            "http://connectivitycheck.gstatic.com/generate_204"
        ],
    })
    
    app: dict = Field(default_factory=lambda: {
        "public_url": "",
        "template_path": "config/web/template.html",
        "channel_tag": "@ScDevNetwork",
    })
    
    whitelist: dict = Field(default_factory=lambda: {
        "domains_url": "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/source/config/whitelist-all.txt",
        "ips_url": "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/source/config/cidrwhitelist.txt",
    })

    BATCH_SIZE: int = 200

    @classmethod
    def load(cls):
        config_path = "config/settings.yaml"
        if not os.path.exists(config_path):
            logger.warning(f"Файл {config_path} не найден, загрузка дефолтов")
            return cls()
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
        return cls(**(yaml_config or {}))


CONFIG = AppSettings.load()
