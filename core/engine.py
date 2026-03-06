import asyncio
import json
import os
import re
import base64
import uuid
import time
import ipaddress
import random
import socket
import signal
import subprocess
import sys
import aiohttp
from aiohttp_socks import ProxyConnector
from loguru import logger
from typing import List, Optional

from core.models import ProxyNode
from core.settings import CONFIG

CHAMPION_BYTES = 10 * 1024 * 1024 
NORMAL_BYTES = 3 * 1024 * 1024    
CHUNK_SIZE = 65536
BATCH_HARD_TIMEOUT = 240.0

USER_AGENTS =[
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1"
]

class BatchEngine:
    _GEO_CACHE: dict = {}
    _PORT_COUNTER: int = 10000
    _PORT_LOCK: Optional[asyncio.Lock] = None

    def __init__(self):
        self.ping_semaphore = asyncio.Semaphore(100)
        self.speed_semaphore = asyncio.Semaphore(6) 
        logger.info("⚙ Engine готов. Strict Hijack Filter + Anti-OOM Protection.")

    @classmethod
    def _ensure_lock(cls):
        if cls._PORT_LOCK is None:
            cls._PORT_LOCK = asyncio.Lock()

    @classmethod
    async def _get_next_base_port(cls, batch_size: int) -> int:
        cls._ensure_lock()
        async with cls._PORT_LOCK:
            port = cls._PORT_COUNTER
            cls._PORT_COUNTER += batch_size + 10
            if cls._PORT_COUNTER > 60000:
                cls._PORT_COUNTER = 10000
            return port

    @staticmethod
    def _is_valid_uuid(val: str) -> bool:
        try:
            uuid.UUID(str(val))
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_valid_hex(val: str) -> bool:
        return bool(re.fullmatch(r'^[0-9a-fA-F]*$', val))

    @staticmethod
    def _validate_reality_node(c) -> bool:
        sni = c.sni or c.host
        if not sni: return False
        try:
            ipaddress.ip_address(sni.strip("[]"))
            return False
        except ValueError:
            pass
        return len(sni) >= 4 and "." in sni

    @staticmethod
    def _resolve_tls_sni(c, transport_type: str) -> Optional[str]:
        sni = c.sni
        if not sni and transport_type not in ("ws", "httpupgrade", "xhttp", "http", "h2"):
            sni = c.host
        if not sni: sni = c.server
            
        if sni:
            sni = sni.strip("[]")
            try:
                ipaddress.ip_address(sni)
                return None
            except ValueError:
                return sni
        return None

    @staticmethod
    def _generate_batch_config(nodes: List[ProxyNode], base_port: int) -> dict:
        inbounds = []
        outbounds = []
        
        rules =[
            {"protocol": "dns", "outbound": "direct"},
            {
                "ip_cidr":[
                    "127.0.0.0/8", "10.0.0.0/8", "192.168.0.0/16", 
                    "172.16.0.0/12", "::1/128", "fc00::/7", "fe80::/10"
                ],
                "outbound": "block"
            }
        ]

        for i, node in enumerate(nodes):
            tag = f"proxy-{i}"
            outbound = BatchEngine._node_to_outbound(node, tag)
            if not outbound: 
                continue
            
            local_port = base_port + i
            inbounds.append({
                "type": "socks",
                "tag": f"in-{i}",
                "listen": "127.0.0.1",
                "listen_port": local_port,
            })
            outbounds.append(outbound)
            rules.append({"inbound": [f"in-{i}"], "outbound": tag})

        outbounds.append({"type": "direct", "tag": "direct"})
        outbounds.append({"type": "block", "tag": "block"})

        return {
            "log": {"level": "fatal", "output": "discard"},
            "dns": {
                "servers":[{"tag": "remote-doh", "address": "https://1.1.1.1/dns-query", "detour": "direct"}],
                "independent_cache": True,
            },
            "inbounds": inbounds,
            "outbounds": outbounds,
            "route": {
                "rules": rules,
                "final": "block",
                "auto_detect_interface": True,
            },
        }

    @staticmethod
    def _node_to_outbound(node: ProxyNode, tag: str) -> Optional[dict]:
        c = node.config
        base = {"tag": tag, "server": c.server, "server_port": c.port}

        try:
            if node.protocol == "vless":
                if not c.uuid or not BatchEngine._is_valid_uuid(c.uuid): return None
                base.update({"type": "vless", "uuid": c.uuid})
                if c.flow:
                    base["flow"] = c.flow

            elif node.protocol == "vmess":
                if not c.uuid or not BatchEngine._is_valid_uuid(c.uuid): return None
                base.update({
                    "type": "vmess",
                    "uuid": c.uuid,
                    "security": "auto",
                    "alter_id": c.alter_id,
                })

            elif node.protocol == "trojan":
                if not c.password: return None
                base.update({"type": "trojan", "password": c.password})

            elif node.protocol == "ss":
                if not c.method or not c.password: return None
                base.update({
                    "type": "shadowsocks",
                    "method": c.method.lower(),
                    "password": c.password,
                })

            elif node.protocol == "hysteria2":
                if not c.password: return None
                base.update({"type": "hysteria2", "password": c.password})
                if c.obfs and c.obfs_password:
                    base["obfs"] = {"type": c.obfs, "password": c.obfs_password}
                
                sni = BatchEngine._resolve_tls_sni(c, "hysteria2")
                
                allow_insecure = False
                for k, v in c.raw_meta.items():
                    if k.lower() in ("allowinsecure", "insecure"):
                        if str(v).lower() in ("1", "true", "yes"):
                            allow_insecure = True
                            break

                tls_config = {"enabled": True}
                if allow_insecure:
                    tls_config["insecure"] = True

                if sni: tls_config["server_name"] = sni
                base["tls"] = tls_config
                return base

            if c.type in ("ws", "websocket"):
                base["transport"] = {"type": "ws", "path": c.path or "/"}
                if c.host: base["transport"]["headers"] = {"Host": c.host}
            elif c.type == "grpc":
                base["transport"] = {"type": "grpc", "service_name": c.service_name or c.path or ""}
            elif c.type in ("httpupgrade", "xhttp"):
                base["transport"] = {"type": "httpupgrade", "path": c.path or "/"}
                if c.host: base["transport"]["host"] = c.host
            elif c.type in ("http", "h2"):
                base["transport"] = {"type": "http", "path": c.path or "/"}
                if c.host: base["transport"]["host"] =[h.strip() for h in c.host.split(",") if h.strip()]
            elif c.type == "quic":
                base["transport"] = {"type": "quic"}

            if c.security in ("tls", "reality", "auto"):
                if c.security == "reality" and not BatchEngine._validate_reality_node(c): return None
                
                export_sni = BatchEngine._resolve_tls_sni(c, c.type)
                if not export_sni and c.security == "reality": return None

                tls = {"enabled": True}

                if c.fp:
                    clean_fp = c.fp.lower()
                    if clean_fp in {"chrome", "firefox", "edge", "safari", "360", "qq", "ios", "android", "random", "randomized"}:
                        tls["utls"] = {"enabled": True, "fingerprint": clean_fp}
                elif c.security in ("reality", "tls"):
                    tls["utls"] = {"enabled": True, "fingerprint": "chrome"}

                allow_insecure = False
                for k, v in c.raw_meta.items():
                    if k.lower() in ("allowinsecure", "insecure"):
                        if str(v).lower() in ("1", "true", "yes"):
                            allow_insecure = True
                            break

                if c.security != "reality":
                    if allow_insecure:
                        tls["insecure"] = True

                if export_sni: tls["server_name"] = export_sni

                if c.alpn:
                    tls["alpn"] =[x.strip() for x in c.alpn.split(",") if x.strip()]
                elif c.security in ("reality", "tls"):
                    tls["alpn"] =["h2", "http/1.1"]

                if c.security == "reality":
                    clean_pbk = c.pbk or ""
                    if len(clean_pbk) < 40 or len(clean_pbk) > 46: return None
                    try:
                        decoded = base64.urlsafe_b64decode(clean_pbk + '=' * (-len(clean_pbk) % 4))
                        if len(decoded) != 32: return None
                    except Exception: 
                        return None
                    
                    tls["reality"] = {"enabled": True, "public_key": clean_pbk}
                    if c.sid:
                        if not BatchEngine._is_valid_hex(c.sid) or len(c.sid) > 16 or len(c.sid) % 2 != 0: return None
                        tls["reality"]["short_id"] = c.sid
                    else:
                        tls["reality"]["short_id"] = ""

                base["tls"] = tls

            return base

        except Exception:
            return None

    async def _is_config_valid(self, config_data: dict, batch_id: str) -> bool:
        if not config_data.get("inbounds"): return False
            
        cfg_path = f"data/check_{batch_id}.json"
        try:
            with open(cfg_path, "w") as f:
                json.dump(config_data, f)
                
            proc = await asyncio.create_subprocess_exec(
                "sing-box", "check", "-c", cfg_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False
        finally:
            if os.path.exists(cfg_path):
                try: os.remove(cfg_path)
                except Exception: pass

    @staticmethod
    async def _wait_for_port(host: str, port: int, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=0.3
                )
                writer.close()
                try: await writer.wait_closed()
                except Exception: pass
                return True
            except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
                await asyncio.sleep(0.1)
        return False

    async def _ping_phase(self, node: ProxyNode, port: int, delay_sec: float) -> dict:
        if delay_sec > 0:
            await asyncio.sleep(delay_sec)
            
        connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{port}", rdns=True)
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        max_latency = CONFIG.checking.get("max_latency", 5000)
        
        all_urls = CONFIG.checking.get("connectivity_urls", ["http://www.gstatic.com/generate_204"])
        test_urls = random.sample(all_urls, min(2, len(all_urls)))

        try:
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with self.ping_semaphore:
                    for target_url in test_urls:
                        t0 = time.perf_counter()
                        try:
                            ping_timeout = aiohttp.ClientTimeout(total=8.0, connect=4.0)
                            async with session.get(target_url, allow_redirects=False, timeout=ping_timeout, ssl=False) as resp:
                                body = await resp.read()
                                
                                if "generate_204" in target_url:
                                    if resp.status != 204 or len(body) > 0:
                                        break
                                elif "apple.com" in target_url:
                                    if resp.status != 200 or b"Success" not in body:
                                        break
                                elif "firefox.com" in target_url:
                                    if resp.status != 200 or b"success" not in body:
                                        break
                                else:
                                    if resp.status not in (200, 204):
                                        break
                                
                                latency = int((time.perf_counter() - t0) * 1000)
                                if latency > max_latency: 
                                    return {"status": "high_latency"}
                                
                                return {"status": "ok", "node": node, "port": port, "latency": latency}
                                
                        except (asyncio.TimeoutError, aiohttp.ClientError):
                            continue
                            
                    return {"status": "error"}
                            
        except Exception:
            return {"status": "error"}

    async def _speed_phase(self, node_data: dict, is_champion: bool) -> dict:
        node = node_data["node"]
        port = node_data["port"]
        latency = node_data["latency"]
        
        connector = ProxyConnector.from_url(f"socks5://127.0.0.1:{port}", rdns=True)
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        min_speed = CONFIG.checking.get("min_speed", 1.0)
        
        try:
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                url = CONFIG.checking.get("champion_test_url" if is_champion else "speedtest_url")
                dl_timeout = aiohttp.ClientTimeout(total=15.0 if is_champion else 12.0)
                target_bytes = CHAMPION_BYTES if is_champion else NORMAL_BYTES

                async with self.speed_semaphore:
                    t_start = time.perf_counter()
                    total = 0
                    try:
                        async with session.get(url, timeout=dl_timeout, ssl=False) as resp:
                            if resp.status != 200: 
                                return {"status": "error"}
                            try:
                                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                                    total += len(chunk)
                                    cur_time = time.perf_counter() - t_start
                                    
                                    if cur_time > 3.5 and total < 65536:
                                        return {"status": "low_speed"}
                                        
                                    if total >= target_bytes: 
                                        break
                            except Exception: 
                                pass 
                    except asyncio.TimeoutError:
                        pass
                    except Exception:
                        pass

                if total < 256 * 1024:
                    return {"status": "drop"}

                dur = max(time.perf_counter() - t_start, 0.1)
                speed = round(min((total * 8) / (dur * 1_000_000), 3000.0), 1)

                if speed < min_speed: 
                    return {"status": "low_speed"}

                country = "UN"
                cache_key = node.strict_id
                
                if cache_key in BatchEngine._GEO_CACHE:
                    country = BatchEngine._GEO_CACHE[cache_key]
                else:
                    async def fetch_geo(geo_url: str, t_out: float) -> str:
                        try:
                            async with session.get(geo_url, timeout=aiohttp.ClientTimeout(total=t_out), ssl=False) as geo:
                                if geo.status == 200:
                                    content = await geo.text()
                                    if "cloudflare" in geo_url or "trace" in geo_url:
                                        for line in content.splitlines():
                                            if line.startswith("loc="):
                                                return line.split("=")[1].upper()
                                    else:
                                        data = json.loads(content)
                                        for k in ("countryCode", "country_code", "country"):
                                            val = data.get(k)
                                            if val and len(str(val)) == 2:
                                                return str(val).upper()
                        except Exception:
                            pass
                        return "UN"

                    await asyncio.sleep(random.uniform(0.1, 0.4))
                    geo_services =[
                        "http://cp.cloudflare.com/cdn-cgi/trace",
                        "https://cloudflare.com/cdn-cgi/trace",
                        "http://ip-api.com/json"
                    ]
                    random.shuffle(geo_services)
                    
                    for gu in geo_services:
                        res = await fetch_geo(gu, 4.0)
                        if res not in ("UN", "XX", ""):
                            country = res
                            BatchEngine._GEO_CACHE[cache_key] = country
                            break

                    if country in ("UN", "XX", ""):
                        country = "UN"
                        BatchEngine._GEO_CACHE[cache_key] = country

                updated_node = node.model_copy(update={"latency": latency, "speed": speed, "country": country})
                return {"status": "ok", "node": updated_node}
        except Exception:
            return {"status": "error"}

    async def check_batch(self, nodes: List[ProxyNode], is_champion: bool = False, batch_num: int = 0) -> List[ProxyNode]:
        if not nodes: return[]

        batch_id = uuid.uuid4().hex[:8]
        os.makedirs("data", exist_ok=True)
        base_port = await self._get_next_base_port(len(nodes))
        
        config_data = self._generate_batch_config(nodes, base_port)
        
        if not await self._is_config_valid(config_data, batch_id):
            valid_nodes = []
            for n in nodes:
                single_cfg = self._generate_batch_config([n], base_port)
                if await self._is_config_valid(single_cfg, batch_id):
                    valid_nodes.append(n)
            
            nodes = valid_nodes
            if not nodes: return[]
            config_data = self._generate_batch_config(nodes, base_port)

        config_path = f"data/run_{batch_id}.json"
        proc = None

        try:
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            kwargs = {}
            if sys.platform != "win32":
                kwargs["start_new_session"] = True
            else:
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            proc = await asyncio.create_subprocess_exec(
                "sing-box", "run", "-c", config_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                **kwargs
            )

            await asyncio.sleep(0.3)
            if proc.returncode is not None:
                try:
                    stderr_out = await asyncio.wait_for(proc.stderr.read(2048), timeout=1.0)
                    logger.error(f"sing-box упал при старте: {stderr_out.decode(errors='replace')}")
                except Exception:
                    pass
                return[]

            first_port = config_data["inbounds"][0]["listen_port"]
            if not await self._wait_for_port("127.0.0.1", first_port, timeout=5.0):
                return[]
                
            await asyncio.sleep(1.0)

            valid_tags = {ob["tag"] for ob in config_data["outbounds"] if ob.get("tag")}
            
            async def run_phases():
                ping_tasks =[]
                delay = 0.0
                for i in range(len(nodes)):
                    if f"proxy-{i}" in valid_tags:
                        ping_tasks.append(self._ping_phase(nodes[i], base_port + i, delay))
                        delay += 0.01

                ping_results = await asyncio.gather(*ping_tasks, return_exceptions=True)
                
                ping_stats = {"ok": 0, "timeout": 0, "high_latency": 0, "error": 0}
                valid_nodes_for_speed =[]
                
                for res in ping_results:
                    if isinstance(res, dict):
                        st = res.get("status", "error")
                        ping_stats[st] = ping_stats.get(st, 0) + 1
                        if st == "ok":
                            valid_nodes_for_speed.append(res)
                    else:
                        ping_stats["error"] += 1
                            
                log_prefix = f"[B-{batch_num}]" if batch_num else "[CHAMP]"
                logger.info(f"   {log_prefix} Ping: {ping_stats['ok']} OK | {ping_stats['timeout']} Timeout | {ping_stats['high_latency']} High Ping | {ping_stats['error']} Err")
                
                if not valid_nodes_for_speed:
                    return []

                speed_tasks =[self._speed_phase(vp, is_champion) for vp in valid_nodes_for_speed]
                speed_results = await asyncio.gather(*speed_tasks, return_exceptions=True)
                
                speed_stats = {"ok": 0, "low_speed": 0, "drop": 0, "error": 0}
                alive_nodes =[]
                
                for res in speed_results:
                    if isinstance(res, dict):
                        st = res.get("status", "error")
                        speed_stats[st] = speed_stats.get(st, 0) + 1
                        if st == "ok":
                            alive_nodes.append(res["node"])
                    else:
                        speed_stats["error"] += 1
                        
                logger.info(f"   {log_prefix} Speed: {speed_stats['ok']} OK | {speed_stats['low_speed']} Low | {speed_stats['drop']} Drop (Fake Page) | {speed_stats['error']} Err")
                return alive_nodes

            alive_nodes = await asyncio.wait_for(run_phases(), timeout=BATCH_HARD_TIMEOUT)

        except asyncio.TimeoutError:
            logger.warning(f"Жесткий таймаут батча {batch_id}.")
            return[]
        except Exception:
            return[]
        finally:
            if proc and proc.returncode is None:
                try:
                    proc.terminate() 
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except Exception:
                    try:
                        if sys.platform != "win32":
                            os.kill(proc.pid, signal.SIGKILL)
                        else:
                            os.kill(proc.pid, signal.CTRL_BREAK_EVENT)
                    except Exception: pass
            if os.path.exists(config_path):
                try: os.remove(config_path)
                except Exception: pass

        return alive_nodes

class Inspector:
    def __init__(self):
        self.batch_engine = BatchEngine()
        self.batch_semaphore = asyncio.Semaphore(2) 
        self.l4_dropped = 0

    async def _l4_check(self, node: ProxyNode, sem: asyncio.Semaphore) -> Optional[ProxyNode]:
        if node.protocol in ("hysteria2", "quic"):
            return node
            
        async with sem:
            host = node.config.server.strip("[]")
            port = node.config.port
            loop = asyncio.get_running_loop()
            
            try:
                addr_info = await asyncio.wait_for(
                    loop.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM),
                    timeout=2.0
                )
                ip_str = addr_info[0][4][0]
                ip_obj = ipaddress.ip_address(ip_str)
            except Exception:
                return None 

            if ip_obj.is_loopback or ip_obj.is_private:
                return None
                    
            forbidden_networks =[
                "1.1.1.0/24", "1.0.0.0/24", "8.8.8.0/24", "8.8.4.0/24",
                "162.159.0.0/16", "104.16.0.0/12", "172.64.0.0/13"
            ]
            for net_str in forbidden_networks:
                if ip_obj in ipaddress.ip_network(net_str):
                    return None

            try:
                await asyncio.sleep(random.uniform(0, 0.2))
                fut = asyncio.open_connection(ip_str, port)
                _, writer = await asyncio.wait_for(fut, timeout=3.5)
                writer.close()
                try: 
                    await writer.wait_closed()
                except Exception: 
                    pass
                return node
            except Exception:
                return None

    async def _process_batch_with_sema(self, batch: List[ProxyNode], batch_num: int, total_batches: int) -> List[ProxyNode]:
        async with self.batch_semaphore:
            logger.info(f"⬚ Батч {batch_num}/{total_batches}: старт ({len(batch)} узлов)...")
            results = await self.batch_engine.check_batch(batch, batch_num=batch_num)
            logger.info(f"   ✧ Живых в батче {batch_num}: {len(results)}/{len(batch)}")
            return results

    async def process_all(self, nodes: List[ProxyNode]) -> List[ProxyNode]:
        total_initial = len(nodes)
        logger.info(f"⏣ Фаза 0: Запуск L4 TCP-Пинга (Префильтрация) для {total_initial} узлов...")
        
        l4_sem = asyncio.Semaphore(75)
        chunk_size = 2000
        valid_nodes =[]
        
        for i in range(0, total_initial, chunk_size):
            chunk = nodes[i:i+chunk_size]
            res = await asyncio.gather(*(self._l4_check(n, l4_sem) for n in chunk), return_exceptions=True)
            valid_nodes.extend([n for n in res if isinstance(n, ProxyNode)])
            logger.info(f"   ... Обработано L4: {min(i+chunk_size, total_initial)}/{total_initial} (Выжило: {len(valid_nodes)})")
            
        nodes = valid_nodes
        total = len(nodes)
        self.l4_dropped += (total_initial - total)
        
        logger.info(f"✔ Фаза 0 завершена. Отброшено {total_initial - total} мертвых IP. В работу идет: {total} узлов.")

        if not nodes:
            return []

        alive_total: List[ProxyNode] =[]
        batch_size = min(getattr(CONFIG, "BATCH_SIZE", 100), 100)

        BatchEngine._GEO_CACHE.clear()
        
        total_batches = (total + batch_size - 1) // batch_size
        logger.info(f"⏣ Фаза 1: Matrix Protocol. {total} узлов, размер батча: {batch_size}, всего батчей: {total_batches}")

        tasks =[]
        for i in range(0, total, batch_size):
            batch = nodes[i: i + batch_size]
            batch_num = i // batch_size + 1
            tasks.append(self._process_batch_with_sema(batch, batch_num, total_batches))
            
        results_nested = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results_nested:
            if isinstance(res, list):
                alive_total.extend(res)

        return alive_total

    async def champion_run(self, nodes: List[ProxyNode]) -> float:
        if not nodes: return 0.0

        nodes.sort(key=lambda x: x.speed, reverse=True)
        candidates = nodes[:5]
        logger.info(f"⚝ Финал: топ-{len(candidates)} кандидатов (Full Speed)...")

        max_speed = 0.0
        for node in candidates:
            results = await self.batch_engine.check_batch([node], is_champion=True)
            if results:
                champ = results[0]
                logger.info(f"   ⪼ {champ.config.server} → {champ.speed} Mbps")
                for n in nodes:
                    if n.strict_id == champ.strict_id:
                        n.speed = champ.speed
                        break
                if champ.speed > max_speed:
                    max_speed = champ.speed
            else:
                pass

        return max_speed
