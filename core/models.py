import hashlib
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ProxyConfig(BaseModel):
    server: str
    port: int = Field(ge=1, le=65535)
    uuid: Optional[str] = None
    password: Optional[str] = None
    method: Optional[str] = None
    type: str = "tcp"
    security: str = "none"
    path: Optional[str] = None
    host: Optional[str] = None
    service_name: Optional[str] = None
    sni: Optional[str] = None
    fp: Optional[str] = None
    alpn: Optional[str] = None
    pbk: Optional[str] = None
    sid: Optional[str] = None
    flow: Optional[str] = None
    spx: Optional[str] = None
    obfs: Optional[str] = None
    obfs_password: Optional[str] = None
    alter_id: int = 0
    raw_meta: dict = Field(default_factory=dict)


class ProxyNode(BaseModel):
    protocol: Literal["vless", "vmess", "trojan", "ss", "hysteria2"]
    config: ProxyConfig
    raw_uri: str
    source_url: str = ""
    country: str = "UN"
    city: str = ""
    speed: float = 0.0
    latency: int = 0
    is_alive: bool = False
    is_bs: bool = False

    @property
    def strict_id(self) -> str:
        cred = self.config.uuid or self.config.password or ""
        path = self.config.path or ""
        sni = self.config.sni or self.config.host or ""
        service = self.config.service_name or ""
        return (
            f"{self.protocol}://{cred}@"
            f"{self.config.server}:{self.config.port}"
            f":{sni}:{path}:{service}"
        )

    @property
    def machine_id(self) -> str:
        path = self.config.path or ""
        sni = self.config.sni or self.config.host or ""
        service = self.config.service_name or ""
        return (
            f"{self.protocol}://"
            f"{self.config.server}:{self.config.port}"
            f":{sni}:{path}:{service}"
        )
