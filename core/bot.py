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
    
    # Заголовок подписки
    "SUB_TITLE": "_ _ _By Frosty XC_ _ _",
    
    "TIMEOUT": 10,       # Таймаут на TCP соединение
    "MAX_LATENCY": 2500, # Максимальный пинг (мс)
    "THREADS": 15,       # Количество одновременных проверок
    
    # Основной и самый точный API
    "GEO_API": "https://ipwho.is/{ip}",
    
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
    address: str      # Домен из конфига
    resolved_ip: str  # Реальный IP после DNS
    port: int
    sni: str = ""
    country_code: str = "UN"
    latency: float = 9999.0

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
        """Превращает 'CA' в 🇨🇦"""
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
        """Создает карточку-заголовок"""
        dummy = {
            "v": "2", "ps": text, "add": "127.0.0.1", "port": "1080",
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "net": "tcp", "type": "none"
        }
        return "vmess://" + Utils.encode_base64(json.dumps(dummy))

# ===========================
# 🧠 ЛОГИКА БОТА
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

    async def resolve_dns(self, domain: str) -> str:
        """Превращаем домен в IP, чтобы GeoIP не ошибался"""
        try:
            socket.inet_aton(domain)
            return domain # Это уже IP
        except: pass
        
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(None, socket.gethostbyname, domain)
        except:
            return domain

    async def get_geo_info(self, ip: str, session: aiohttp.ClientSession) -> str:
        """Парсинг JSON от ipwho.is"""
        if ip in self.geo_cache: return self.geo_cache[ip]

        # Небольшая пауза перед запросом для стабильности
        await asyncio.sleep(random.uniform(0.2, 0.5))
        
        url = CONFIG["GEO_API"].format(ip=ip)
        try:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Проверяем "success": true из присланного вами JSON
                    if data.get('success') is True:
                        # Берем "country_code": "CA"
                        cc = data.get('country_code')
                        if cc:
                            self.geo_cache[ip] = cc
                            return cc
        except: pass
        
        return "UN"

    async def check_node(self, node: ProxyNode, session: aiohttp.ClientSession) -> Optional[ProxyNode]:
        try:
            # 1. DNS: Узнаем реальный IP
            node.resolved_ip = await self.resolve_dns(node.address)

            # 2. Ping: Проверяем доступность по IP
            t0 = time.perf_counter()
            fut = asyncio.open_connection(node.resolved_ip, node.port)
            r, w = await asyncio.wait_for(fut, timeout=CONFIG["TIMEOUT"])
            w.close()
            await w.wait_closed()
            node.latency = (time.perf_counter() - t0) * 1000
            
            if node.latency > CONFIG["MAX_LATENCY"]: return None

            # 3. Geo: Определяем страну по IP
            node.country_code = await self.get_geo_info(node.resolved_ip, session)
            return node
        except:
            return None

    async def run(self):
        logger.info("🚀 ЗАПУСК...")
        raw_links = await self.fetch_links()
        
        # Парсинг строк в объекты
        nodes = []
        for l in raw_links:
            try:
                if l.startswith("vless://"):
                    p = urllib.parse.urlparse(l)
                    q = urllib.parse.parse_qs(p.query)
                    nodes.append(ProxyNode(l, "VLESS", p.hostname, "", p.port, q.get('sni',[''])[0]))
                elif l.startswith("vmess://"):
                    d = json.loads(Utils.decode_base64(l[8:]))
                    nodes.append(ProxyNode(l, "VMESS", d['add'], "", int(d['port']), d.get('sni','') or d.get('host','')))
            except: pass

        # Проверка
        alive_nodes = []
        sem = asyncio.Semaphore(CONFIG["THREADS"])
        async with aiohttp.ClientSession() as session:
            async def worker(n):
                async with sem:
                    return await self.check_node(n, session)
            
            results = await asyncio.gather(*[worker(n) for n in nodes])
            alive_nodes = [r for r in results if r]

        alive_nodes.sort(key=lambda x: x.latency)
        logger.info(f"✅ Живых: {len(alive_nodes)}")

        # Формирование подписки
        final_lines = []
        final_lines.append(Utils.create_header(f"ℹ️ {CONFIG['SUB_TITLE']}"))
        final_lines.append(Utils.create_header(f"🔄 Updated: {datetime.datetime.now().strftime('%d.%m %H:%M')}"))

        for i, node in enumerate(alive_nodes, 1):
            flag = Utils.get_flag(node.country_code)
            sni = Utils.clean_sni(node.sni, node.address)
            
            # Название: 01 🇨🇦 CA | sni.com | VLESS
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

        # Сохранение в Base64
        with open(CONFIG["OUTPUT_FILE"], "w", encoding="utf-8") as f:
            f.write(Utils.encode_base64("\n".join(final_lines)))
        
        logger.info(f"💾 Файл {CONFIG['OUTPUT_FILE']} обновлен успешно!")

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(Bot().run())
