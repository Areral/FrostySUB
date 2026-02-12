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
import socket
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ===========================
# ⚙️ НАСТРОЙКИ
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    
    "SUB_TITLE": "_ _ _By Frosty XC_ _ _",
    
    "TIMEOUT": 10,       # Таймаут на подключение
    "MAX_LATENCY": 2000, # Максимальный пинг
    "PING_THREADS": 40,  # Пинг делаем быстро и много
    
    # 🌍 ВАЖНО: Список ручных исправлений
    # Если бот все равно ошибается, впишите часть домена и нужный код сюда
    "MANUAL_OVERRIDES": {
        "ge.spectrum.vu": "DE",
        "de.spectrum.vu": "DE",
        ".ru": "RU",
        ".de": "DE"
    },
    
    # API используем по очереди
    "GEO_APIS": [
        "https://ipwho.is/{ip}",
        "http://ip-api.com/json/{ip}?fields=status,country,countryCode"
    ],
    
    "USER_AGENT": "v2rayNG/1.8.5 (Linux; Android 13; K)"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("Bot")

# ===========================
# 📦 КЛАССЫ
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
    ip_resolved: str = "" # Сюда сохраним реальный IP

class Utils:
    @staticmethod
    def decode_base64(text: str) -> str:
        text = text.strip()
        if not text: return ""
        if "://" in text: return text
        try:
            text = text.replace('-', '+').replace('_', '/')
            pad = len(text) % 4
            if pad: text += '=' * (4 - pad)
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
    def create_header(text: str) -> str:
        dummy = {
            "v": "2", "ps": text, "add": "127.0.0.1", "port": "1080",
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "net": "tcp", "type": "none"
        }
        return "vmess://" + Utils.encode_base64(json.dumps(dummy))

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
                except: pass
        return list(set(links))

    # --- 1. ПИНГЕР (БЫСТРО, ПАРАЛЛЕЛЬНО) ---
    async def ping_node(self, node: ProxyNode) -> Optional[ProxyNode]:
        try:
            # Сначала пытаемся разрешить DNS, чтобы узнать реальный IP
            # Это пригодится для GeoIP, чтобы не спрашивать у API домен
            loop = asyncio.get_running_loop()
            try:
                # В Linux/Docker это работает быстро
                ip = await loop.run_in_executor(None, socket.gethostbyname, node.address)
                node.ip_resolved = ip
            except:
                node.ip_resolved = node.address # Если не вышло, оставляем как есть

            t0 = time.perf_counter()
            fut = asyncio.open_connection(node.address, node.port)
            r, w = await asyncio.wait_for(fut, timeout=CONFIG["TIMEOUT"])
            w.close()
            await w.wait_closed()
            node.latency = (time.perf_counter() - t0) * 1000
            
            return node
        except:
            return None

    # --- 2. ГЕОЛОКАТОР (МЕДЛЕННО, ПОСЛЕДОВАТЕЛЬНО) ---
    async def resolve_geo_sequential(self, node: ProxyNode, session: aiohttp.ClientSession):
        # 1. Проверка ручных правил (MANUAL_OVERRIDES)
        for key, val in CONFIG["MANUAL_OVERRIDES"].items():
            if key in node.address:
                node.country_code = val
                return

        target = node.ip_resolved if node.ip_resolved else node.address
        
        if target in self.geo_cache:
            node.country_code = self.geo_cache[target]
            return

        # 2. Запрос к API (строго по одному)
        for api_tpl in CONFIG["GEO_APIS"]:
            try:
                # Небольшая пауза, чтобы API не забанил за спам
                await asyncio.sleep(0.2) 
                
                url = api_tpl.format(ip=target)
                async with session.get(url, timeout=5, ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        cc = data.get('countryCode') or data.get('country_code')
                        
                        if cc and cc not in ['UN', 'XX']:
                            self.geo_cache[target] = cc
                            node.country_code = cc
                            return # Успех
            except: continue
        
        # Если ничего не помогло
        node.country_code = "UN"

    async def run(self):
        logger.info("🚀 START...")
        raw_links = await self.fetch_links()
        
        # --- ЭТАП 1: ПАРСИНГ ---
        nodes = []
        for l in raw_links:
            try:
                if l.startswith("vless://"):
                    p = urllib.parse.urlparse(l)
                    q = urllib.parse.parse_qs(p.query)
                    nodes.append(ProxyNode(l, "VLESS", p.hostname, p.port, q.get('sni',[''])[0], q.get('host',[''])[0]))
                elif l.startswith("vmess://"):
                    d = json.loads(Utils.decode_base64(l[8:]))
                    nodes.append(ProxyNode(l, "VMESS", d['add'], int(d['port']), d.get('sni','') or d.get('host',''), d.get('host','')))
            except: pass

        # --- ЭТАП 2: МАССОВЫЙ ПИНГ ---
        alive_nodes = []
        sem = asyncio.Semaphore(CONFIG["PING_THREADS"])
        
        async def pinger(n):
            async with sem:
                res = await self.ping_node(n)
                if res and res.latency <= CONFIG["MAX_LATENCY"]:
                    return res
                return None

        logger.info(f"⚡️ Пингуем {len(nodes)} узлов...")
        results = await asyncio.gather(*[pinger(n) for n in nodes])
        alive_nodes = [r for r in results if r]
        
        # Сортировка по пингу
        alive_nodes.sort(key=lambda x: x.latency)
        logger.info(f"✅ Живых: {len(alive_nodes)}. Запуск GeoIP...")

        # --- ЭТАП 3: GEOIP (ПОСЛЕДОВАТЕЛЬНО) ---
        # Мы проходим циклом for, а не gather. Это гарантирует отсутствие банов.
        async with aiohttp.ClientSession() as session:
            for i, node in enumerate(alive_nodes):
                await self.resolve_geo_sequential(node, session)
                # Логируем прогресс каждые 10 узлов
                if i % 10 == 0: logger.info(f"🌍 Geo прогресс: {i}/{len(alive_nodes)}")

        # --- ЭТАП 4: СБОРКА ФАЙЛА ---
        final_lines = []
        final_lines.append(Utils.create_header(f"ℹ️ {CONFIG['SUB_TITLE']}"))
        final_lines.append(Utils.create_header(f"🔄 Updated: {datetime.datetime.now().strftime('%d.%m %H:%M')}"))

        for i, node in enumerate(alive_nodes, 1):
            flag = Utils.get_flag(node.country_code)
            sni = Utils.clean_sni(node.sni, node.address)
            
            # 01 🇩🇪 DE | google.com | VLESS
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
        
        logger.info("💾 ГОТОВО!")

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(Bot().run())
