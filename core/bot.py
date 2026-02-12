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
from typing import List, Optional

# ===========================
# ⚙️ НАСТРОЙКИ
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    
    # Заголовок
    "SUB_TITLE": "_ _ _By Frosty XC_ _ _",
    
    # Таймауты и потоки
    "TIMEOUT": 10,       
    "MAX_LATENCY": 2500, 
    "THREADS": 15,       # Оптимально для ротации API
    
    # 🌍 СПИСОК GEO-API (Ротация)
    # Бот будет случайно выбирать один из них для каждого прокси
    "GEO_APIS": [
        # API 1: Очень точный, лояльный лимит
        "https://ipwho.is/{ip}",
        # API 2: Стандартный
        "http://ip-api.com/json/{ip}?fields=status,country,countryCode",
        # API 3: Альтернатива
        "https://freeipapi.com/api/json/{ip}",
        # API 4: Еще один источник
        "https://api.iplocation.net/?ip={ip}",
        # API 5: Резерв
        "https://api.dtech.lol/ip/{ip}"
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
    address: str      # Домен или IP из ссылки
    resolved_ip: str  # Реальный IP после DNS запроса
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

    # --- DNS RESOLVER ---
    # Это ключевой момент: мы превращаем домен в IP ПЕРЕД тем как спросить GeoAPI
    async def resolve_dns(self, domain: str) -> str:
        # Если это уже IP, возвращаем его
        try:
            socket.inet_aton(domain)
            return domain
        except: pass
        
        # Если домен, резолвим
        loop = asyncio.get_running_loop()
        try:
            ip = await loop.run_in_executor(None, socket.gethostbyname, domain)
            return ip
        except:
            return domain # Если не вышло, возвращаем домен (но это плохо для geo)

    # --- GEO RESOLVER (ROTATION) ---
    async def get_geo_info(self, ip: str, session: aiohttp.ClientSession) -> str:
        if ip in self.geo_cache: return self.geo_cache[ip]

        # Перемешиваем список API, чтобы каждый запрос шел к случайному сервису
        apis = CONFIG["GEO_APIS"].copy()
        random.shuffle(apis)

        for api_tpl in apis:
            try:
                # Пауза перед запросом (Jitter)
                await asyncio.sleep(random.uniform(0.1, 0.4))
                
                url = api_tpl.format(ip=ip)
                async with session.get(url, timeout=4, ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Парсинг разных форматов ответов
                        cc = (
                            data.get('countryCode') or 
                            data.get('country_code') or 
                            data.get('country_iso') or # iplocation.net
                            'UN'
                        )
                        
                        if cc and cc not in ['UN', 'XX']:
                            self.geo_cache[ip] = cc
                            return cc
            except: continue
        
        return "UN"

    # --- CHECKER ---
    async def check_node(self, node: ProxyNode, session: aiohttp.ClientSession) -> Optional[ProxyNode]:
        try:
            # 1. DNS Resolve (Узнаем реальный IP сервера)
            # Мы проверяем не конфиг целиком, а именно адрес, куда пойдет трафик
            node.resolved_ip = await self.resolve_dns(node.address)

            # 2. Ping (TCP Connect к IP)
            t0 = time.perf_counter()
            fut = asyncio.open_connection(node.resolved_ip, node.port) # Коннектимся по IP!
            r, w = await asyncio.wait_for(fut, timeout=CONFIG["TIMEOUT"])
            w.close()
            await w.wait_closed()
            node.latency = (time.perf_counter() - t0) * 1000
            
            if node.latency > CONFIG["MAX_LATENCY"]: return None

            # 3. GeoIP (По IP адресу, а не домену)
            node.country_code = await self.get_geo_info(node.resolved_ip, session)
            return node

        except: return None

    async def run(self):
        logger.info("🚀 START...")
        raw_links = await self.fetch_links()
        
        nodes = []
        for l in raw_links:
            try:
                if l.startswith("vless://"):
                    p = urllib.parse.urlparse(l)
                    q = urllib.parse.parse_qs(p.query)
                    nodes.append(ProxyNode(
                        raw_uri=l, protocol="VLESS", 
                        address=p.hostname, resolved_ip="", 
                        port=p.port, sni=q.get('sni',[''])[0], host=q.get('host',[''])[0]
                    ))
                elif l.startswith("vmess://"):
                    d = json.loads(Utils.decode_base64(l[8:]))
                    nodes.append(ProxyNode(
                        raw_uri=l, protocol="VMESS", 
                        address=d['add'], resolved_ip="", 
                        port=int(d['port']), sni=d.get('sni','') or d.get('host',''), host=d.get('host','')
                    ))
            except: pass

        logger.info(f"⚡️ Проверка {len(nodes)} узлов...")
        
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

        # --- СОХРАНЕНИЕ ---
        final_lines = []
        final_lines.append(Utils.create_header(f"ℹ️ {CONFIG['SUB_TITLE']}"))
        final_lines.append(Utils.create_header(f"🔄 Updated: {datetime.datetime.now().strftime('%d.%m %H:%M')}"))

        for i, node in enumerate(alive_nodes, 1):
            flag = Utils.get_flag(node.country_code)
            sni = Utils.clean_sni(node.sni, node.address)
            
            # Формат вывода
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
