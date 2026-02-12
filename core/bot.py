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
import datetime
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ===========================
# ⚙️ НАСТРОЙКИ
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    
    # Заголовок подписки
    "SUB_TITLE": "_ _ _By Frosty XC_ _ _",
    
    "TIMEOUT": 10,
    "MAX_LATENCY": 2000,
    
    # Снижаем кол-во потоков, чтобы GeoAPI не банил нас и не выдавал "Индию"
    "MAX_CONCURRENT": 10, 
    
    # Список API. ipwho.is стоит первым, так как он лояльнее к запросам
    "GEO_APIS": [
        "https://ipwho.is/{ip}",
        "http://ip-api.com/json/{ip}?fields=status,country,countryCode",
        "https://api.dtech.lol/ip/{ip}"
    ],
    
    "USER_AGENT": "v2rayNG/1.8.5 (Linux; Android 13; K)"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("Bot")

# ===========================
# 📦 КЛАССЫ И УТИЛИТЫ
# ===========================

@dataclass
class ProxyNode:
    raw_uri: str
    protocol: str
    address: str
    port: int
    sni: str = ""
    host: str = ""
    country_code: str = "UN"
    country_name: str = "Unknown"
    latency: float = 9999.0

class Utils:
    @staticmethod
    def decode_base64(text: str) -> str:
        text = text.strip()
        if not text: return ""
        if "://" in text: return text
        try:
            text = text.replace('-', '+').replace('_', '/')
            padding = len(text) % 4
            if padding: text += '=' * (4 - padding)
            return base64.b64decode(text).decode('utf-8', 'ignore')
        except: return text

    @staticmethod
    def encode_base64(text: str) -> str:
        return base64.b64encode(text.encode('utf-8')).decode('utf-8').replace('+', '-').replace('/', '_').replace('=', '')

    @staticmethod
    def get_flag(code: str) -> str:
        if not code or code == 'UN' or len(code) != 2: return "🌐"
        return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)

    @staticmethod
    def clean_sni(sni: str, host: str) -> str:
        target = sni if sni else host
        if not target: return "No-SNI"
        if len(target) > 25: return "Generic"
        return target

    @staticmethod
    def create_info_node(text: str) -> str:
        """Создает заголовок (фейковый VMESS)"""
        dummy_data = {
            "v": "2", "ps": text, "add": "127.0.0.1", "port": "1080",
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "aid": "0", "net": "tcp", "type": "none", "host": "", "path": "", "tls": ""
        }
        return "vmess://" + Utils.encode_base64(json.dumps(dummy_data))

# ===========================
# 🧠 ЛОГИКА
# ===========================

class Bot:
    def __init__(self):
        self.geo_cache = {}
        self.headers = {'User-Agent': CONFIG["USER_AGENT"]}

    async def fetch_links(self):
        links = []
        try:
            with open(CONFIG["SOURCES_FILE"], "r") as f:
                urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        except: return []

        async with aiohttp.ClientSession(headers=self.headers) as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=15) as resp:
                        if resp.status == 200:
                            content = await resp.text()
                            decoded = Utils.decode_base64(content)
                            for line in decoded.splitlines():
                                if "://" in line: links.append(line.strip())
                            logger.info(f"📥 {url} -> OK")
                except Exception as e:
                    logger.warning(f"Ошибка источника {url}: {e}")
        return list(set(links))

    async def resolve_geo(self, ip: str, session: aiohttp.ClientSession) -> Tuple[str, str]:
        if ip in self.geo_cache: return self.geo_cache[ip]

        # ⚡️ JITTER: Случайная задержка 0.1-0.5 сек перед запросом к API.
        # Это решает проблему блокировки и выдачи "Индии" (IP раннера)
        await asyncio.sleep(random.uniform(0.1, 0.5))

        for api_tpl in CONFIG["GEO_APIS"]:
            try:
                url = api_tpl.format(ip=ip)
                async with session.get(url, timeout=5, ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Проверка: не вернул ли API ошибку
                        if 'status' in data and data['status'] == 'fail':
                            continue

                        cc = data.get('countryCode') or data.get('country_code') or 'UN'
                        cn = data.get('country') or data.get('country_name') or 'Unknown'
                        
                        if cc and cc not in ['UN', 'XX']:
                            self.geo_cache[ip] = (cc, cn)
                            return cc, cn
            except: continue
        
        return "UN", "Unknown"

    async def check_proxy(self, raw_link: str, session: aiohttp.ClientSession) -> Optional[ProxyNode]:
        node = None
        try:
            # Парсинг
            if raw_link.startswith("vless://"):
                p = urllib.parse.urlparse(raw_link)
                q = urllib.parse.parse_qs(p.query)
                node = ProxyNode(
                    raw_uri=raw_link, 
                    protocol="VLESS", 
                    address=p.hostname, 
                    port=p.port, 
                    sni=q.get('sni',[''])[0], 
                    host=q.get('host',[''])[0]
                )
            elif raw_link.startswith("vmess://"):
                d = json.loads(Utils.decode_base64(raw_link[8:]))
                node = ProxyNode(
                    raw_uri=raw_link, 
                    protocol="VMESS", 
                    address=d['add'], 
                    port=int(d['port']), 
                    sni=d.get('sni','') or d.get('host',''), 
                    host=d.get('host','')
                )
            
            if not node: return None

            # 1. Пинг
            t0 = time.perf_counter()
            fut = asyncio.open_connection(node.address, node.port)
            r, w = await asyncio.wait_for(fut, timeout=CONFIG["TIMEOUT"])
            w.close()
            await w.wait_closed()
            node.latency = (time.perf_counter() - t0) * 1000

            if node.latency > CONFIG["MAX_LATENCY"]: return None

            # 2. GeoIP (только если порт открыт)
            node.country_code, node.country_name = await self.resolve_geo(node.address, session)
            return node

        except: return None

    async def run(self):
        logger.info("🚀 Запуск...")
        raw_links = await self.fetch_links()
        
        valid_nodes = []
        sem = asyncio.Semaphore(CONFIG["MAX_CONCURRENT"])

        async with aiohttp.ClientSession() as session:
            async def worker(link):
                async with sem:
                    return await self.check_proxy(link, session)
            
            tasks = [worker(l) for l in raw_links]
            results = await asyncio.gather(*tasks)
            valid_nodes = [r for r in results if r]

        # Сортировка: сначала быстрые
        valid_nodes.sort(key=lambda x: x.latency)
        logger.info(f"✅ Живых: {len(valid_nodes)}")

        final_lines = []

        # === ЗАГОЛОВКИ ===
        # 1. Название подписки
        header_title = f"ℹ️ {CONFIG['SUB_TITLE']}"
        final_lines.append(Utils.create_info_node(header_title))
        
        # 2. Дата обновления
        update_time = datetime.datetime.now().strftime("%d.%m %H:%M")
        header_date = f"🔄 Updated: {update_time}"
        final_lines.append(Utils.create_info_node(header_date))

        # === УЗЛЫ ===
        for i, node in enumerate(valid_nodes, 1):
            flag = Utils.get_flag(node.country_code)
            sni = Utils.clean_sni(node.sni, node.address)
            
            # ФОРМАТ: 01 🇫🇮 FI | sni.com | VLESS
            # (Пинг убрали, добавили Тип протокола)
            new_name = f"{i:02d} {flag} {node.country_code} | {sni} | {node.protocol}"
            
            if node.protocol == "VLESS":
                p = urllib.parse.urlparse(node.raw_uri)
                final_lines.append(p._replace(fragment=urllib.parse.quote(new_name)).geturl())
            elif node.protocol == "VMESS":
                try:
                    js = json.loads(Utils.decode_base64(node.raw_uri[8:]))
                    js['ps'] = new_name
                    final_lines.append("vmess://" + Utils.encode_base64(json.dumps(js, separators=(',', ':'))))
                except: pass

        with open(CONFIG["OUTPUT_FILE"], "w", encoding="utf-8") as f:
            f.write(Utils.encode_base64("\n".join(final_lines)))
        
        logger.info("💾 Сохранено!")

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(Bot().run())
