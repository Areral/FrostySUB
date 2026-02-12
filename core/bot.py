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
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ===========================
# ⚙️ НАСТРОЙКИ
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    "SUBSCRIPTION_TITLE": "❄️ Frosty XC ❄️", # Название, которое будет первым в списке
    "TIMEOUT": 10,
    "MAX_CONCURRENT": 20,
    "MAX_LATENCY": 1500,
    
    # 🌍 УЛУЧШЕННАЯ ГЕОЛОКАЦИЯ
    # ipwho.is чаще дает точные данные по датацентрам Европы (Финляндия/Германия)
    "GEO_APIS": [
        "https://ipwho.is/{ip}",
        "http://ip-api.com/json/{ip}?fields=status,country,countryCode",
        "https://api.dtech.lol/ip/{ip}"
    ],
    "USER_AGENT": "v2rayNG/1.8.5 (Linux; Android 13; K)"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("Bot")

# ===========================
# 📦 УТИЛИТЫ
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
    latency: float = 9999.0

class Utils:
    @staticmethod
    def decode_base64(text: str) -> str:
        text = text.strip()
        if not text: return ""
        if "vless://" in text or "vmess://" in text: return text
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
        if not code or code == 'UN' or len(code) != 2: return "🏴"
        # Исправление для "Индии" если это реально не Индия (на всякий случай флаг ставим)
        return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)

    @staticmethod
    def clean_sni(sni: str, host: str) -> str:
        target = sni if sni else host
        if not target: return "No-SNI"
        if len(target) > 25: return target[:25] + "..."
        return target

# ===========================
# 🧠 ПАРСЕР
# ===========================
class Parser:
    @staticmethod
    def parse(link: str) -> Optional[ProxyNode]:
        link = link.strip()
        if not link or link.startswith("#"): return None
        try:
            if link.startswith("vless://"):
                parsed = urllib.parse.urlparse(link)
                params = urllib.parse.parse_qs(parsed.query)
                sni = params.get('sni', [''])[0]
                host = params.get('host', [''])[0]
                return ProxyNode(link, "VLESS", parsed.hostname, parsed.port, sni, host)
            elif link.startswith("vmess://"):
                b64 = link.replace("vmess://", "")
                data = json.loads(Utils.decode_base64(b64))
                return ProxyNode(link, "VMESS", data.get('add'), int(data.get('port')), data.get('sni', '') or data.get('host', ''), data.get('host', ''))
        except: return None
        return None

# ===========================
# 🚀 ЛОГИКА БОТА
# ===========================
class ProxyBot:
    def __init__(self):
        self.geo_cache = {}
        self.headers = {'User-Agent': CONFIG["USER_AGENT"]}

    async def fetch_sources(self) -> List[str]:
        raw = []
        try:
            with open(CONFIG["SOURCES_FILE"], "r") as f:
                urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        except: return []

        async with aiohttp.ClientSession(headers=self.headers) as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=15) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            decoded = Utils.decode_base64(text)
                            for line in decoded.splitlines():
                                if "://" in line: raw.append(line)
                            logger.info(f"📥 {url}: OK")
                except Exception as e: logger.warning(f"Ошибка {url}: {e}")
        return list(set(raw))

    async def resolve_geo(self, ip: str, session: aiohttp.ClientSession) -> str:
        """
        Умное определение ГЕО.
        Если первый API говорит 'IN' (Индия) или 'US' (США), мы спрашиваем второй API,
        так как дешевые базы часто путают Финляндию/Германию с Индией/США.
        """
        if ip in self.geo_cache: return self.geo_cache[ip]

        final_cc = "UN"
        
        for api_tpl in CONFIG["GEO_APIS"]:
            try:
                url = api_tpl.format(ip=ip)
                async with session.get(url, timeout=3, ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Унификация ответов разных API
                        cc = data.get('countryCode') or data.get('country_code') or 'UN'
                        
                        if cc != 'UN':
                            # Если определили как Индию или США - это подозрительно для многих VPN.
                            # Попробуем следующий API для подтверждения, если это был первый проход.
                            if cc in ['IN', 'US'] and api_tpl == CONFIG["GEO_APIS"][0]:
                                logger.info(f"🤔 IP {ip} определен как {cc}. Перепроверяем...")
                                final_cc = cc # Запоминаем, но идем к следующему API
                                continue      # Пробуем следующий API
                            
                            # Если второй API тоже что-то выдал, верим ему больше
                            self.geo_cache[ip] = cc
                            return cc
            except: continue
        
        # Если прошли все API и ничего точнее не нашли, возвращаем что было
        self.geo_cache[ip] = final_cc
        return final_cc

    async def check_node(self, node: ProxyNode, session: aiohttp.ClientSession) -> Optional[ProxyNode]:
        try:
            t0 = time.perf_counter()
            fut = asyncio.open_connection(node.address, node.port)
            r, w = await asyncio.wait_for(fut, timeout=CONFIG["TIMEOUT"])
            w.close()
            await w.wait_closed()
            
            node.latency = (time.perf_counter() - t0) * 1000
            if node.latency > CONFIG["MAX_LATENCY"]: return None
            
            node.country_code = await self.resolve_geo(node.address, session)
            return node
        except: return None

    def create_title_node(self) -> str:
        """Создает фальшивый узел-заголовок"""
        # Используем VMESS, так как в него проще всего вшить произвольное имя
        title_json = {
            "v": "2",
            "ps": CONFIG["SUBSCRIPTION_TITLE"], # ИМЯ ПОДПИСКИ
            "add": "127.0.0.1",
            "port": "1080",
            "id": "00000000-0000-0000-0000-000000000000",
            "aid": "0",
            "net": "tcp",
            "type": "none",
            "host": "github.com",
            "path": "/",
            "tls": ""
        }
        return "vmess://" + Utils.encode_base64(json.dumps(title_json))

    def rename_node(self, node: ProxyNode, index: int) -> str:
        flag = Utils.get_flag(node.country_code)
        sni = Utils.clean_sni(node.sni, node.host)
        
        # Формат имени: 01 🇫🇮 FI | google.com
        new_name = f"{index:02d} {flag} {node.country_code} | {sni}"

        if node.protocol == "VLESS":
            p = urllib.parse.urlparse(node.raw_uri)
            return p._replace(fragment=urllib.parse.quote(new_name)).geturl()
        elif node.protocol == "VMESS":
            try:
                b64 = node.raw_uri.replace("vmess://", "")
                js = json.loads(Utils.decode_base64(b64))
                js['ps'] = new_name
                return "vmess://" + Utils.encode_base64(json.dumps(js))
            except: return node.raw_uri
        return node.raw_uri

    async def run(self):
        links = await self.fetch_sources()
        nodes = [Parser.parse(l) for l in links if Parser.parse(l)]
        logger.info(f"Найдено: {len(nodes)}")

        alive = []
        sem = asyncio.Semaphore(CONFIG["MAX_CONCURRENT"])
        async with aiohttp.ClientSession() as session:
            async def work(n):
                async with sem: return await self.check_node(n, session)
            results = await asyncio.gather(*[work(n) for n in nodes])
            alive = [r for r in results if r]

        alive.sort(key=lambda x: x.latency)
        
        final_lines = []
        
        # 1. ДОБАВЛЯЕМ ЗАГОЛОВОК (Первая строка в клиенте)
        final_lines.append(self.create_title_node())
        
        # 2. Добавляем реальные прокси
        for i, n in enumerate(alive, 1):
            final_lines.append(self.rename_node(n, i))

        with open(CONFIG["OUTPUT_FILE"], "w") as f:
            f.write(Utils.encode_base64("\n".join(final_lines)))
        
        logger.info("Готово! Подписка обновлена.")

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(ProxyBot().run())
