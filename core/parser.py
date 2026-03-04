import base64
import json
import urllib.parse
import ipaddress
import re
import html
import asyncio
import hashlib
from typing import List, Optional
import aiohttp

from core.models import ProxyNode, ProxyConfig
from core.logger import logger
from core.settings import CONFIG
from core.validator import RKNValidator

SS_VALID_METHODS = {
    "aes-128-gcm", "aes-192-gcm", "aes-256-gcm", 
    "chacha20-ietf-poly1305", "xchacha20-ietf-poly1305", 
    "2022-blake3-aes-128-gcm", "2022-blake3-aes-256-gcm", "2022-blake3-chacha20-poly1305"
}

CONTROLLED_KEYS_COMMON = {
    "type", "security", "encryption", "path", "host",
    "sni", "peer", "fp", "alpn", "pbk", "sid", "flow",
    "servicename", "serviceName", "spx"
}


class LinkParser:
    GARBAGE_WORDS =[
        "01010101", "9292929", "11111111-1111", "test1",
        "@pwn1337-telegram", "rootface",
    ]

    HOST_RE = re.compile(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')

    def __init__(self):
        self.semaphore = asyncio.Semaphore(15)
        self.metrics = {}
        self._seen_content_hashes: set = set()

    @staticmethod
    def decode_base64(s: str) -> str:
        try:
            s = s.strip().replace('-', '+').replace('_', '/')
            s = re.sub(r'\s+', '', s)
            missing = len(s) % 4
            if missing: s += "=" * (4 - missing)
            return base64.b64decode(s.encode('ascii', 'ignore')).decode('utf-8', 'ignore')
        except Exception:
            return s

    @staticmethod
    def is_valid_host(host: str) -> bool:
        if not host: 
            return False
        h = host.strip("[]").lower()
        if h in ("localhost", "127.0.0.1", "0.0.0.0", "::1"): 
            return False
        if h.endswith(".localhost") or h.endswith(".local"): 
            return False
        try:
            ip = ipaddress.ip_address(h)
            is_global = ip.is_global
            return is_global
        except ValueError:
            is_valid_domain = bool(LinkParser.HOST_RE.match(h)) and len(h) >= 4
            return is_valid_domain

    @classmethod
    def _is_garbage(cls, line: str) -> bool:
        ll = line.lower()
        for w in cls.GARBAGE_WORDS:
            if w in ll:
                return True
        return False

    @staticmethod
    def _extract_clean_meta(q_simple: dict) -> dict:
        return {k: v for k, v in q_simple.items() if k.lower() not in CONTROLLED_KEYS_COMMON}

    @staticmethod
    def parse_vless(line: str) -> Optional[ProxyNode]:
        if LinkParser._is_garbage(line): return None
        try:
            line = html.unescape(line).replace("/?", "?")
            u = urllib.parse.urlparse(line)
            q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
            q_simple = {k: urllib.parse.unquote(v[0]) for k, v in q.items() if v}

            host = u.hostname
            if not host or not LinkParser.is_valid_host(host): return None
            if not u.port: return None
            uid = (u.username or "").strip()
            if not uid: return None

            conf = ProxyConfig(
                server=host,
                port=u.port,
                uuid=uid,
                type=q_simple.get('type', 'tcp'),
                security=q_simple.get('security', 'none'),
                path=q_simple.get('path') or None,
                host=q_simple.get('host') or None,
                sni=(q_simple.get('sni') or q_simple.get('peer')) or None,
                fp=q_simple.get('fp') or None,
                alpn=q_simple.get('alpn') or None,
                pbk=q_simple.get('pbk') or None,
                sid=q_simple.get('sid') or None,
                flow=q_simple.get('flow') or None,
                spx=q_simple.get('spx') or None,
                service_name=(q_simple.get('serviceName') or q_simple.get('servicename')) or None,
                raw_meta=LinkParser._extract_clean_meta(q_simple),
            )
            return ProxyNode(protocol="vless", config=conf, raw_uri=line)
        except Exception:
            return None

    @staticmethod
    def parse_vmess(line: str) -> Optional[ProxyNode]:
        if LinkParser._is_garbage(line): return None
        try:
            raw_json = LinkParser.decode_base64(line.replace("vmess://", "").strip())
            data = json.loads(raw_json)

            host = str(data.get('add', '')).strip()
            if not host or not LinkParser.is_valid_host(host): return None
            if not data.get('port'): return None
            uid = str(data.get('id', '')).strip()
            if not uid: return None

            VMESS_CONTROLLED = {
                "v", "ps", "add", "port", "id", "net", "tls",
                "path", "host", "sni", "fp", "alpn", "aid", "type"
            }
            
            aid = data.get('aid', 0)
            alter_id = int(aid) if str(aid).isdigit() else 0

            conf = ProxyConfig(
                server=host,
                port=int(data['port']),
                uuid=uid,
                type=str(data.get('net', 'tcp')).strip(),
                security="tls" if str(data.get('tls', '')).lower() in ("tls", "1", "true") else "none",
                path=urllib.parse.unquote(str(data.get('path', ''))).strip() or None,
                host=urllib.parse.unquote(str(data.get('host', ''))).strip() or None,
                sni=urllib.parse.unquote(str(data.get('sni', ''))).strip() or None,
                fp=str(data.get('fp', '')).strip() or None,
                alpn=str(data.get('alpn', '')).strip() or None,
                service_name=urllib.parse.unquote(str(data.get('path', ''))).strip() if str(data.get('net', '')).strip() == 'grpc' else None,
                alter_id=alter_id,
                raw_meta={k: v for k, v in data.items() if k.lower() not in VMESS_CONTROLLED},
            )
            return ProxyNode(protocol="vmess", config=conf, raw_uri=line)
        except Exception:
            return None

    @staticmethod
    def parse_trojan(line: str) -> Optional[ProxyNode]:
        if LinkParser._is_garbage(line): return None
        try:
            line = html.unescape(line).replace("/?", "?")
            u = urllib.parse.urlparse(line)
            q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
            q_simple = {k: urllib.parse.unquote(v[0]) for k, v in q.items() if v}

            host = u.hostname
            if not host or not LinkParser.is_valid_host(host): return None
            if not u.port: return None
            password = (u.username or "").strip()
            if not password: return None

            conf = ProxyConfig(
                server=host,
                port=u.port,
                password=urllib.parse.unquote(password),
                security=q_simple.get('security', 'tls'),
                type=q_simple.get('type', 'tcp'),
                path=q_simple.get('path') or None,
                host=q_simple.get('host') or None,
                sni=(q_simple.get('sni') or q_simple.get('peer')) or None,
                fp=q_simple.get('fp') or None,
                alpn=q_simple.get('alpn') or None,
                flow=q_simple.get('flow') or None,
                service_name=(q_simple.get('serviceName') or q_simple.get('servicename')) or None,
                raw_meta=LinkParser._extract_clean_meta(q_simple),
            )
            return ProxyNode(protocol="trojan", config=conf, raw_uri=line)
        except Exception:
            return None

    @staticmethod
    def parse_ss(line: str) -> Optional[ProxyNode]:
        if LinkParser._is_garbage(line): return None
        try:
            original_line = line
            line = html.unescape(line).strip()
            
            if not line.startswith("ss://"): return None
            rest = line[5:]
            
            if '#' in rest:
                rest, _ = rest.split('#', 1)

            query = ""
            if '/?' in rest:
                rest, query = rest.split('/?', 1)
            elif '?' in rest:
                rest, query = rest.split('?', 1)

            method = password = host = port_str = None

            if '@' in rest:
                cred_part, hostport = rest.rsplit('@', 1)
                try:
                    decoded_creds = LinkParser.decode_base64(cred_part)
                    if ':' in decoded_creds:
                        method, password = decoded_creds.split(':', 1)
                except Exception:
                    pass
                
                if not method or not password:
                    if ':' in cred_part:
                        method, password = cred_part.split(':', 1)
                    else:
                        return None
            else:
                try:
                    decoded = LinkParser.decode_base64(rest)
                    if '@' not in decoded: return None
                    cred_part, hostport = decoded.rsplit('@', 1)
                    if ':' not in cred_part: return None
                    method, password = cred_part.split(':', 1)
                except Exception:
                    return None

            if not hostport: return None

            if hostport.startswith('['):
                bracket_end = hostport.find(']')
                if bracket_end == -1: return None
                host = hostport[1:bracket_end]
                port_str = hostport[bracket_end+2:]
            else:
                if ':' not in hostport: return None
                host, port_str = hostport.rsplit(':', 1)

            try: 
                port = int(port_str)
            except ValueError: 
                return None

            method = method.strip().lower()
            password = urllib.parse.unquote(password.strip())
            clean_host = urllib.parse.unquote(host.strip().strip('[]'))

            if not LinkParser.is_valid_host(clean_host): return None
            if method not in SS_VALID_METHODS: return None 

            q_simple = {}
            if query:
                q = urllib.parse.parse_qs(query, keep_blank_values=True)
                q_simple = {k: urllib.parse.unquote(v[0]) for k, v in q.items() if v}

            conf = ProxyConfig(
                server=clean_host,
                port=port,
                method=method,
                password=password,
                type="tcp",
                raw_meta=LinkParser._extract_clean_meta(q_simple)
            )
            return ProxyNode(protocol="ss", config=conf, raw_uri=original_line)
        except Exception:
            return None

    @staticmethod
    def parse_hy2(line: str) -> Optional[ProxyNode]:
        if LinkParser._is_garbage(line): return None
        try:
            original_line = line
            line = html.unescape(line).strip()
            if line.startswith("hy2://"): line = "hysteria2://" + line[6:]

            u = urllib.parse.urlparse(line)
            q = urllib.parse.parse_qs(u.query, keep_blank_values=True)
            q_simple = {k: urllib.parse.unquote(v[0]) for k, v in q.items() if v}

            host = u.hostname
            if not host or not LinkParser.is_valid_host(host): return None
            if not u.port: return None
            password = (u.username or "").strip()
            if not password: return None

            HY2_CONTROLLED = {"sni", "peer", "obfs", "obfs-password"}
            
            conf = ProxyConfig(
                server=host,
                port=u.port,
                password=urllib.parse.unquote(password),
                sni=(q_simple.get('sni') or q_simple.get('peer')) or None,
                obfs=q_simple.get('obfs') or None,
                obfs_password=q_simple.get('obfs-password') or None,
                raw_meta={k: v for k, v in q_simple.items() if k.lower() not in HY2_CONTROLLED},
            )
            return ProxyNode(protocol="hysteria2", config=conf, raw_uri=original_line)
        except Exception:
            return None

    async def _fetch_url_with_retry(self, session: aiohttp.ClientSession, url: str, retries: int = 3) -> str:
        async with self.semaphore:
            for attempt in range(retries):
                try:
                    timeout = aiohttp.ClientTimeout(total=20)
                    async with session.get(url, timeout=timeout) as resp:
                        if resp.status == 200:
                            self.metrics[url] = {"parsed": 0, "alive": 0, "status": "OK"}
                            return await resp.text(errors='ignore')
                        if resp.status == 429:
                            if attempt < retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            self.metrics[url] = {"parsed": 0, "alive": 0, "status": "429 Rate Limited"}
                            return ""
                        self.metrics[url] = {"parsed": 0, "alive": 0, "status": f"HTTP {resp.status}"}
                        return ""
                except Exception as e:
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    self.metrics[url] = {"parsed": 0, "alive": 0, "status": f"Error: {str(e)[:60]}"}
            return ""

    async def fetch_and_parse(self) -> List[ProxyNode]:
        nodes: List[ProxyNode] =[]
        seen_ids: set = set()
        machine_counts: dict = {}
        
        max_accounts_per_server = CONFIG.parser.get("max_accounts_per_server", 5)

        raw_sources = CONFIG.SUBSCRIPTION_SOURCES
        if not raw_sources: 
            return[]

        if isinstance(raw_sources, list):
            sources = list(dict.fromkeys(s.strip() for s in raw_sources if s.strip()))
        else:
            sources = list(dict.fromkeys(s.strip() for s in raw_sources.splitlines() if s.strip()))

        logger.info(f"⭳ Загрузка {len(sources)} источников...")

        connector = aiohttp.TCPConnector(limit=15, ttl_dns_cache=300)
        async with aiohttp.ClientSession(connector=connector) as session:
            results = await asyncio.gather(*[self._fetch_url_with_retry(session, url) for url in sources])

        parsers = {
            "vless://": self.parse_vless,
            "vmess://": self.parse_vmess,
            "trojan://": self.parse_trojan,
            "ss://": self.parse_ss,
            "hy2://": self.parse_hy2,
            "hysteria2://": self.parse_hy2,
        }

        for i, content in enumerate(results):
            if not content: continue
            url = sources[i]

            content_hash = hashlib.md5(content.encode('utf-8', errors='ignore')).hexdigest()
            if content_hash in self._seen_content_hashes: 
                continue
            self._seen_content_hashes.add(content_hash)

            nodes_from_source = 0

            if "://" not in content[:200]:
                content = LinkParser.decode_base64(content)

            for raw_line in content.splitlines():
                line = raw_line.strip()
                if not line or line.startswith('#'): continue

                node = None
                for prefix, parser_fn in parsers.items():
                    if line.startswith(prefix):
                        node = parser_fn(line)
                        break
                
                if node:
                    if node.protocol in ("vless", "vmess", "trojan"):
                        if node.config.security in ("none", "") and node.config.type not in ("ws", "httpupgrade", "xhttp"):
                            continue

                    if node.strict_id not in seen_ids:
                        m_id = node.machine_id
                        
                        if machine_counts.get(m_id, 0) < max_accounts_per_server:
                            node.source_url = url
                            node.is_bs = RKNValidator.check_bs(node)
                            nodes.append(node)
                            seen_ids.add(node.strict_id)
                            machine_counts[m_id] = machine_counts.get(m_id, 0) + 1
                            nodes_from_source += 1

            if url in self.metrics:
                self.metrics[url]["parsed"] = nodes_from_source

        logger.info("📊 Статистика парсинга источников:")
        for url, stat in self.metrics.items():
            if stat["parsed"] > 0:
                logger.debug(f"  [+] {url} -> {stat['parsed']} узлов")
            else:
                logger.debug(f"  [-] {url} -> {stat['status']}")

        logger.success(f"✔ Распарсено: {len(nodes)} уникальных аккаунтов (Макс. {max_accounts_per_server} на сервер)")
        return nodes
