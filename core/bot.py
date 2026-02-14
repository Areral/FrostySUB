#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import aiohttp
import base64
import json
import logging
import time
import urllib.parse
import sys
import os
import random
import datetime
import subprocess
import socket
from aiohttp_socks import ProxyConnector
from dataclasses import dataclass
from typing import List, Optional

# ===========================
# 🕒 НАСТРОЙКА ВРЕМЕНИ (MSK UTC+3)
# ===========================
def msk_converter(*args):
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).timetuple()

logging.Formatter.converter = msk_converter
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("SunnyBot")

# ===========================
# ⚙️ КОНФИГУРАЦИЯ (v6.1 Clean & Fast)
# ===========================
CONFIG = {
    # Файлы
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_SUB": "subscription.txt",
    "TEMPLATE_FILE": "config/template.html",
    "OUTPUT_INDEX": "index.html",
    
    # Ссылка для QR-кода на сайте (Здесь будет ваша Cloudflare ссылка)
    "PUBLIC_SUB_URL": "https://sub.areral.workers.dev", 
    
    # Настройки производительности (Ускорено!)
    "THREADS": 15,            # Увеличили потоки для скорости
    "TCP_TIMEOUT": 2,         # 2 секунды на пинг порта
    "PIPELINE_TIMEOUT": 15,   # Уменьшили до 15 сек (было 30). Долго думать некогда.
    
    # Anti-Ban / Speed Test
    "CHECK_URLS": ["https://www.google.com/generate_204", "https://www.cloudflare.com/cdn-cgi/trace"],
    
    # 8MB Test / 5 Mbps Min / 8 Mbps Early Exit
    "SPEED_TEST_URL": "http://speed.cloudflare.com/__down?bytes=8000000",
    "MIN_SPEED_MBPS": 5.0,
    "EARLY_EXIT_SPEED": 8.0,
    
    "GEO_API": "https://ipwho.is/",
    "USER_AGENT": "v2rayNG/1.8.5"
}

# ===========================
# 📦 УТИЛИТЫ
# ===========================
class Utils:
    @staticmethod
    def decode_b64(s: str) -> str:
        s = s.strip()
        if not s: return ""
        try:
            return base64.b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', 'ignore')
        except: return s

    @staticmethod
    def encode_b64(s: str) -> str:
        return base64.b64encode(s.encode('utf-8')).decode('utf-8').replace('+', '-').replace('/', '_').replace('=', '')

@dataclass
class ProxyNode:
    raw_uri: str
    protocol: str
    config: dict
    country_code: str = "UN"
    speed_mbps: float = 0.0

# ===========================
# 🌐 ГЕНЕРАТОР САЙТА
# ===========================
class WebGenerator:
    @staticmethod
    def build_site(alive_count: int, max_speed: float, update_time: str):
        try:
            with open(CONFIG["TEMPLATE_FILE"], "r", encoding="utf-8") as f:
                template = f.read()
            
            html = template.replace("{{UPDATE_TIME}}", update_time)
            html = html.replace("{{PROXY_COUNT}}", str(alive_count))
            html = html.replace("{{MAX_SPEED}}", str(max_speed))
            html = html.replace("{{SUB_LINK}}", CONFIG["PUBLIC_SUB_URL"])
            
            with open(CONFIG["OUTPUT_INDEX"], "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("🌐 Сайт index.html обновлен")
        except Exception as e:
            logger.error(f"⚠️ Ошибка генерации сайта: {e}")

# ===========================
# 🛠 SING-BOX MANAGER
# ===========================
class SingBoxManager:
    @staticmethod
    def generate_config(node: ProxyNode, local_port: int) -> dict:
        c = node.config
        outbound = {
            "type": "vless", "tag": "proxy", "server": c['server'], "server_port": c['port'],
            "uuid": c['uuid'], "packet_encoding": "xudp"
        }
        if c.get('security') == 'reality':
            outbound["tls"] = {
                "enabled": True, "server_name": c.get('sni'),
                "utls": {"enabled": True, "fingerprint": c.get('fp', 'chrome')},
                "reality": {"enabled": True, "public_key": c.get('pbk'), "short_id": c.get('sid')}
            }
        if c.get('flow'): outbound["flow"] = c.get('flow')
        return {
            "log": {"level": "fatal"}, "dns": {"servers": [{"tag": "google", "address": "8.8.8.8"}]},
            "inbounds": [{"type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": local_port, "sniff": True}],
            "outbounds": [outbound]
        }

# ===========================
# 🧠 CORE LOGIC
# ===========================
class SunnyBot:
    async def parse_links(self) -> List[ProxyNode]:
        nodes = []
        seen = set()
        try:
            with open(CONFIG["SOURCES_FILE"], "r") as f:
                urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        except: return []

        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=10) as resp:
                        content = await resp.text()
                        if "://" not in content[:50]: content = Utils.decode_b64(content)
                        for line in content.splitlines():
                            line = line.strip()
                            if line.startswith("vless://"):
                                p = urllib.parse.urlparse(line)
                                q = urllib.parse.parse_qs(p.query)
                                uid = f"{p.hostname}:{p.port}:{p.username}"
                                if uid not in seen:
                                    nodes.append(ProxyNode(line, "VLESS", {
                                        "server": p.hostname, "port": p.port, "uuid": p.username,
                                        "sni": q.get('sni',[''])[0], "pbk": q.get('pbk',[''])[0],
                                        "sid": q.get('sid',[''])[0], "fp": q.get('fp',['chrome'])[0],
                                        "security": q.get('security',[''])[0], "flow": q.get('flow',[''])[0]
                                    }))
                                    seen.add(uid)
                except: pass
        return nodes

    async def tcp_check(self, node: ProxyNode, sem: asyncio.Semaphore) -> bool:
        async with sem:
            try:
                loop = asyncio.get_running_loop()
                ip = await loop.run_in_executor(None, socket.gethostbyname, node.config['server'])
                conn = asyncio.open_connection(ip, node.config['port'])
                _, w = await asyncio.wait_for(conn, timeout=CONFIG["TCP_TIMEOUT"])
                w.close()
                await w.wait_closed()
                return True
            except: return False

    async def validate_node(self, node: ProxyNode, sem: asyncio.Semaphore) -> Optional[ProxyNode]:
        async with sem:
            port = random.randint(20000, 55000)
            cfg_path = f"t_{port}.json"
            with open(cfg_path, 'w') as f: json.dump(SingBoxManager.generate_config(node, port), f)
            proc = subprocess.Popen(["sing-box", "run", "-c", cfg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(2.5) # Ждем старта
            try:
                connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
                # Строгий таймаут на всю операцию
                async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=CONFIG["PIPELINE_TIMEOUT"])) as session:
                    # 1. AntiBan
                    async with session.get(random.choice(CONFIG["CHECK_URLS"]), timeout=4) as resp:
                        if resp.status >= 400: raise Exception("Ban")
                    # 2. Geo
                    async with session.get(CONFIG["GEO_API"], timeout=4) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('success'): node.country_code = data.get('country_code', 'UN')
                            else: raise Exception("GeoFail")
                    # 3. Speed
                    t_start = time.perf_counter()
                    async with session.get(CONFIG["SPEED_TEST_URL"]) as resp:
                        if resp.status == 200:
                            total = 0
                            async for chunk in resp.content.iter_chunked(65536):
                                total += len(chunk)
                                if total > 1500000: # Early exit > 1.5MB
                                    cur = (total*8/(time.perf_counter()-t_start))/1000000
                                    if cur >= CONFIG["EARLY_EXIT_SPEED"]:
                                        node.speed_mbps = round(cur, 1)
                                        logger.info(f"✨ FAST: {node.config['server']} | {node.speed_mbps} Mbps")
                                        return node
                                    if total > 3000000 and cur < 1.0: raise Exception("Slow")
                            
                            dur = time.perf_counter()-t_start
                            node.speed_mbps = round((total*8/(dur or 0.001))/1000000, 1)
                            if node.speed_mbps >= CONFIG["MIN_SPEED_MBPS"]:
                                logger.info(f"✅ OK: {node.config['server']} | {node.speed_mbps} Mbps")
                                return node
            except: pass
            finally:
                proc.terminate()
                try: proc.wait(timeout=2)
                except: proc.kill()
                if os.path.exists(cfg_path): os.remove(cfg_path)
            return None

    async def run(self):
        msk_now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        logger.info(f"🚀 SUNNY-BOT V6.1 START (MSK: {msk_now.strftime('%H:%M:%S')})")
        
        nodes = await self.parse_links()
        logger.info(f"🔎 Уникальных: {len(nodes)}")

        # TCP Check (50 потоков для скорости)
        tcp_sem = asyncio.Semaphore(50)
        tcp_res = await asyncio.gather(*[self.tcp_check(n, tcp_sem) for n in nodes])
        candidates = [n for n, ok in zip(nodes, tcp_res) if ok]
        logger.info(f"📉 Живых портов: {len(candidates)}")

        alive = []
        if candidates:
            # Singbox Check (15 потоков)
            sem = asyncio.Semaphore(CONFIG["THREADS"])
            res = await asyncio.gather(*[self.validate_node(n, sem) for n in candidates])
            alive = [r for r in res if r]
            alive.sort(key=lambda x: x.speed_mbps, reverse=True)

            update_time = msk_now.strftime('%d.%m %H:%M')
            
            # 1. СОХРАНЕНИЕ ПОДПИСКИ (ЧИСТЫЙ СПИСОК)
            final = [] # Убрали заголовки Utils.create_header
            for i, n in enumerate(alive, 1):
                flag = chr(ord(n.country_code[0])+127397) + chr(ord(n.country_code[1])+127397)
                nm = f"{i:02d} {flag} {n.country_code} | {n.config['sni'] or n.config['server']} | {n.protocol}"
                p = urllib.parse.urlparse(n.raw_uri)
                final.append(p._replace(fragment=urllib.parse.quote(nm)).geturl())
            
            with open(CONFIG["OUTPUT_SUB"], "w", encoding="utf-8") as f:
                f.write(Utils.encode_b64("\n".join(final)))
            
            logger.info(f"💾 Подписка сохранена: {len(alive)} узлов")

            # 2. ГЕНЕРАЦИЯ САЙТА
            max_spd = alive[0].speed_mbps if alive else 0
            WebGenerator.build_site(len(alive), max_spd, update_time)

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(SunnyBot().run())
