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
from dataclasses import dataclass
from typing import List, Optional

# ===========================
# ⚙️ НАСТРОЙКИ
# ===========================
FILES = {
    "INPUT": "sources.txt",
    "DEBUG": "debug.txt",
    "SUB": "subscription.txt"
}

CONFIG = {
    "MAX_LATENCY": 1500,         # Макс пинг (мс)
    "THREADS": 50,               # Потоки
    "GEO_API": "http://ip-api.com/json/"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("GitHubBot")

# ===========================
# 🛠 УТИЛИТЫ
# ===========================
class Utils:
    @staticmethod
    def get_flag(code: str) -> str:
        if not code or code == 'UN': return "🏴"
        return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)

    @staticmethod
    def safe_b64decode(s: str) -> str:
        s = s.strip().replace('-', '+').replace('_', '/')
        return base64.b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', 'ignore')

    @staticmethod
    def safe_b64encode(s: str) -> str:
        return base64.b64encode(s.encode('utf-8')).decode('utf-8').replace('+', '-').replace('/', '_').replace('=', '')

    @staticmethod
    def clean_sni(sni: str) -> str:
        if not sni: return "No-SNI"
        if len(sni) > 25: return "Generic"
        return sni

# ===========================
# 📦 ОБЪЕКТ ПРОКСИ
# ===========================
@dataclass
class ProxyNode:
    original_uri: str
    protocol: str
    address: str
    port: int
    sni: str = ""
    country_code: str = "UN"
    latency: float = 9999.0

    def generate_name(self, rank: int) -> str:
        flag = Utils.get_flag(self.country_code)
        clean_sni = Utils.clean_sni(self.sni)
        # Формат: #1 🇫🇮 FI | google.com
        return f"#{rank} {flag} {self.country_code} | {clean_sni}"

    def get_uri_with_new_name(self, rank: int) -> str:
        new_name = self.generate_name(rank)
        if self.protocol == "VLESS":
            try:
                parsed = urllib.parse.urlparse(self.original_uri)
                encoded_name = urllib.parse.quote(new_name)
                return parsed._replace(fragment=encoded_name).geturl()
            except: return self.original_uri
        elif self.protocol == "VMESS":
            try:
                b64 = self.original_uri.replace("vmess://", "")
                data = json.loads(Utils.safe_b64decode(b64))
                data['ps'] = new_name
                new_json = json.dumps(data, separators=(',', ':'))
                return "vmess://" + Utils.safe_b64encode(new_json)
            except: return self.original_uri
        return self.original_uri

# ===========================
# 🧠 ЛОГИКА
# ===========================
class Bot:
    def __init__(self):
        self.geo_cache = {}

    async def run_once(self):
        logger.info("🚀 ЗАПУСК СКРИПТА НА GITHUB ACTIONS")
        
        # 1. Чтение источников
        if not os.path.exists(FILES["INPUT"]):
            logger.error("Файл sources.txt не найден!")
            return

        with open(FILES["INPUT"], "r") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        # 2. Скачивание
        links = []
        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=10) as resp:
                        text = await resp.text()
                        if "://" not in text[:50] and len(text) > 20:
                            text = Utils.safe_b64decode(text)
                        links.extend(text.splitlines())
                        logger.info(f"📥 Скачано: {url}")
                except: pass
        
        unique_links = list(set(links))
        nodes = []
        
        # 3. Парсинг
        for link in unique_links:
            try:
                link = link.strip()
                if not link or link.startswith("#"): continue
                
                node = None
                if link.startswith("vless://"):
                    p = urllib.parse.urlparse(link)
                    q = urllib.parse.parse_qs(p.query)
                    sni = q.get('sni', [q.get('host', [''])])[0]
                    node = ProxyNode(link, "VLESS", p.hostname, p.port, sni)
                elif link.startswith("vmess://"):
                    d = json.loads(Utils.safe_b64decode(link.replace("vmess://", "")))
                    sni = d.get('sni') or d.get('host') or ""
                    node = ProxyNode(link, "VMESS", d['add'], int(d['port']), sni)
                
                if node: nodes.append(node)
            except: pass

        logger.info(f"🔎 Найдено уникальных: {len(nodes)}")

        # 4. Проверка (Ping + Geo)
        sem = asyncio.Semaphore(CONFIG["THREADS"])
        async with aiohttp.ClientSession() as session:
            async def worker(n):
                async with sem:
                    # Ping
                    t0 = time.monotonic()
                    try:
                        fut = asyncio.open_connection(n.address, n.port)
                        r, w = await asyncio.wait_for(fut, timeout=1.5)
                        w.close()
                        await w.wait_closed()
                        n.latency = (time.monotonic() - t0) * 1000
                    except: return n

                    # Geo
                    if n.latency <= CONFIG["MAX_LATENCY"]:
                        if n.address not in self.geo_cache:
                            try:
                                async with session.get(f"{CONFIG['GEO_API']}{n.address}?fields=countryCode", timeout=2) as resp:
                                    d = await resp.json()
                                    self.geo_cache[n.address] = d.get('countryCode', 'UN')
                            except: self.geo_cache[n.address] = 'UN'
                        n.country_code = self.geo_cache[n.address]
                    return n

            nodes = await asyncio.gather(*[worker(n) for n in nodes])

        # 5. Фильтрация и Сортировка
        alive = [n for n in nodes if n.latency <= CONFIG["MAX_LATENCY"]]
        alive.sort(key=lambda x: x.latency) # Сортировка по пингу

        logger.info(f"✅ Живых: {len(alive)}")

        # 6. Сохранение
        final_links = []
        debug_lines = []
        
        for rank, node in enumerate(alive, 1):
            final_links.append(node.get_uri_with_new_name(rank))
            debug_lines.append(f"{node.generate_name(rank)} | Ping: {int(node.latency)}ms")

        with open(FILES["SUB"], "w") as f:
            f.write(Utils.safe_b64encode("\n".join(final_links)))

        with open(FILES["DEBUG"], "w") as f:
            f.write("\n".join(debug_lines))

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(Bot().run_once())
