import urllib.parse
import os
import json
import hashlib
import ipaddress
import base64
from loguru import logger
from typing import List, Dict, Any, Optional

from core.models import ProxyNode
from core.settings import CONFIG

class Exporter:
    @staticmethod
    def _flag(code: str) -> str:
        if not code or code == "UN": return "❓"
        try: return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)
        except Exception: return "❓"

    @staticmethod
    def _safe_b64encode(b: bytes) -> str:
        try:
            return base64.b64encode(b).decode("utf-8").rstrip("=")
        except Exception:
            return ""

    @staticmethod
    def _is_ip(address: str) -> bool:
        if not address: return False
        try:
            ipaddress.ip_address(address.strip("[]"))
            return True
        except ValueError:
            return False

    @staticmethod
    def _format_host(address: str) -> str:
        if not address: return address
        clean = address.strip().strip("[]")
        try:
            ip = ipaddress.ip_address(clean)
            return f"[{clean}]" if ip.version == 6 else clean
        except ValueError:
            return clean

    @staticmethod
    def _xray_encode_value(key: str, value: str) -> str:
        k = key.lower()
        if k in ("pbk", "sid", "flow", "fp", "type", "security", "encryption", "net", "tls", "protocol"):
            return value
        if k == "alpn": return urllib.parse.quote(value, safe=",/")
        if k == "path": return urllib.parse.quote(value, safe="")
        if k in ("host", "sni", "peer", "add", "server"): return urllib.parse.quote(value, safe=".-_[]:")
        if k == "servicename": return urllib.parse.quote(value, safe=".-_/")
        return urllib.parse.quote(value, safe="")

    @staticmethod
    def _urlencode(query_dict: Dict[str, Any]) -> str:
        if not query_dict: return ""
        parts =[]
        for k, raw_v in query_dict.items():
            if raw_v is None: continue
            
            if str(raw_v).lower() in ("none", "null", "") and k.lower() not in ("sid", "pbk", "path", "spx"): 
                continue
                
            v = "1" if isinstance(raw_v, bool) and raw_v else ("0" if isinstance(raw_v, bool) else str(raw_v))
            parts.append(f"{k}={Exporter._xray_encode_value(k, v)}")
        return "&".join(parts)

    @staticmethod
    def _build_url(node: ProxyNode, name: str) -> str:
        c = node.config
        encoded_name = urllib.parse.quote(name, safe="")
        host_for_uri = Exporter._format_host(c.server or "")
        port = c.port

        try:
            if node.protocol == "vless":
                q = dict(c.raw_meta or {})
                q["type"] = c.type
                q["security"] = c.security
                q["encryption"] = "none"

                if c.path is not None: q["path"] = c.path
                if c.host: q["host"] = c.host
                if c.sni: q["sni"] = c.sni
                if c.fp: q["fp"] = c.fp
                if c.alpn: q["alpn"] = c.alpn
                if c.pbk is not None: q["pbk"] = c.pbk
                if c.sid is not None: q["sid"] = c.sid
                if c.spx is not None: q["spx"] = c.spx
                if c.flow: q["flow"] = c.flow
                if c.service_name: q["serviceName"] = c.service_name

                allow_insecure = False
                for k, v in c.raw_meta.items():
                    if k.lower() in ("allowinsecure", "insecure") and str(v).lower() in ("1", "true", "yes"):
                        allow_insecure = True
                        break
                        
                if c.security == "tls" and allow_insecure:
                    q["allowInsecure"] = "1"
                    q["insecure"] = "1"

                return f"vless://{c.uuid}@{host_for_uri}:{port}?{Exporter._urlencode(q)}#{encoded_name}"

            elif node.protocol == "vmess":
                data = {
                    "v": "2", "ps": name, "add": c.server, "port": str(c.port),
                    "id": str(c.uuid), "aid": str(c.alter_id), "net": c.type,
                    "type": "none", "tls": "tls" if c.security in ("tls", "reality") else "",
                }
                
                if c.host: data["host"] = c.host
                if c.path: data["path"] = c.path
                if c.type == "grpc" and c.service_name: data["path"] = c.service_name

                if data["tls"]:
                    if c.sni: data["sni"] = c.sni
                    if c.fp: data["fp"] = c.fp
                    if c.alpn: data["alpn"] = c.alpn
                    
                for k, v in c.raw_meta.items():
                    if k not in data:
                        data[k] = v

                j_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                return f"vmess://{Exporter._safe_b64encode(j_str.encode('utf-8'))}"

            elif node.protocol == "trojan":
                q = dict(c.raw_meta or {})
                q["type"] = c.type
                q["security"] = c.security

                if c.path is not None: q["path"] = c.path
                if c.host: q["host"] = c.host
                if c.sni: q["sni"] = c.sni
                if c.fp: q["fp"] = c.fp
                if c.alpn: q["alpn"] = c.alpn
                if c.service_name: q["serviceName"] = c.service_name
                if c.flow: q["flow"] = c.flow

                allow_insecure = False
                for k, v in c.raw_meta.items():
                    if k.lower() in ("allowinsecure", "insecure") and str(v).lower() in ("1", "true", "yes"):
                        allow_insecure = True
                        break
                        
                if c.security == "tls" and allow_insecure:
                    q["allowInsecure"] = "1"
                    q["insecure"] = "1"

                return f"trojan://{c.password}@{host_for_uri}:{port}?{Exporter._urlencode(q)}#{encoded_name}"

            elif node.protocol == "ss":
                b64_up = Exporter._safe_b64encode(f"{c.method}:{c.password}".encode("utf-8"))
                q = dict(c.raw_meta or {})
                q_str = Exporter._urlencode(q)
                suffix = f"/?{q_str}" if q_str else ""
                return f"ss://{b64_up}@{host_for_uri}:{port}{suffix}#{encoded_name}"

            elif node.protocol == "hysteria2":
                q = dict(c.raw_meta or {})
                if c.sni: q["sni"] = c.sni
                if c.obfs: q["obfs"] = c.obfs
                if c.obfs_password: q["obfs-password"] = c.obfs_password

                return f"hysteria2://{c.password}@{host_for_uri}:{port}?{Exporter._urlencode(q)}#{encoded_name}"

        except Exception as e:
            logger.debug(f"Exporter: Ошибка сборки URL для {node.strict_id}: {e}")
            pass

        try:
            parsed = urllib.parse.urlparse(node.raw_uri)
            return parsed._replace(fragment=encoded_name).geturl()
        except Exception:
            return node.raw_uri or ""

    @staticmethod
    def generate_subscription(nodes: List[ProxyNode], title: str) -> str:
        logger.debug(f"Exporter: Генерация тела подписки '{title}' для {len(nodes)} узлов")
        channel_tag = CONFIG.app.get("channel_tag", "@ScDevNetwork")
        lines =[f"#profile-title: {title}", "#profile-update-interval: 6"]
        for node in sorted(nodes, key=lambda x: x.speed, reverse=True):
            flag = Exporter._flag(node.country)
            sni = node.config.sni or node.config.host or node.config.server
            proto = node.protocol.upper()
            short_hash = hashlib.md5(node.strict_id.encode("utf-8")).hexdigest()[:4].upper()
            
            name = f"{flag} {node.country} | {sni} | {proto} [{short_hash}] | {channel_tag}"
            
            lines.append(Exporter._build_url(node, name))
        return "\n".join(lines)

    @staticmethod
    def save_files(nodes: List[ProxyNode], shard_index: int = -1, parsed_count: int = 0, dead_sources: List[str] = None, duration: float = 0.0, l4_dropped: int = 0):
        logger.info(f"Exporter: Старт сохранения {len(nodes)} узлов в физические файлы (Shard {shard_index})")
        if not nodes:
            nodes_bs = []
            nodes_chs =[]
        else:
            nodes_bs = [n for n in nodes if n.is_bs]
            nodes_chs = [n for n in nodes if not n.is_bs]
            
        suffix = f"_{shard_index}" if shard_index >= 0 else ""

        os.makedirs("data", exist_ok=True)
        
        for filename, node_list, title in[
            (f"sub_all{suffix}.txt", nodes, "Scarlet Devil | Gungnir (MIX)"),
            (f"sub_bs{suffix}.txt", nodes_bs, "Scarlet Devil | Nightbird (БС)"),
            (f"sub_chs{suffix}.txt", nodes_chs, "Scarlet Devil | Vampire Dash (ЧС)"),
        ]:
            try:
                with open(f"data/{filename}", "w", encoding="utf-8") as f:
                    f.write(Exporter.generate_subscription(node_list, title))
                logger.debug(f"Exporter: Файл {filename} успешно сохранён ({len(node_list)} узлов)")
            except Exception as e:
                logger.error(f"Exporter: Ошибка записи {filename}: {e}")
                pass
                
        top_speed = max((n.speed for n in nodes), default=0.0) if nodes else 0.0
        stats = {
            "parsed": parsed_count,
            "alive": len(nodes),
            "top_speed": top_speed,
            "duration": duration,
            "l4_dropped": l4_dropped,
            "dead_sources": list(dead_sources) if dead_sources else[]
        }
        
        try:
            with open(f"data/stats{suffix}.json", "w", encoding="utf-8") as f:
                json.dump(stats, f)
            logger.info(f"Exporter: Экспорт телеметрии завершен (stats{suffix}.json)")
        except Exception as e:
            logger.error(f"Exporter: Ошибка записи статистики: {e}")
            pass
