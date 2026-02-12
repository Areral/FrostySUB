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
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ===========================
# ⚙️ НАСТРОЙКИ
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    
    # Имя подписки, которое будет видно в v2rayNG/NekoBox
    "SUB_TITLE": "❄️ Frosty XC",
    
    "TIMEOUT": 10,
    "MAX_CONCURRENT": 20, # Снизили до 20 для стабильности Geo API
    "MAX_LATENCY": 2500,
    
    # 🌍 Улучшенный порядок API для точности (ipwho.is точнее для Европы/Датацентров)
    "GEO_APIS": [
        "https://ipwho.is/{ip}",                                              # Самый точный free tier
        "http://ip-api.com/json/{ip}?fields=status,country,countryCode",      # Классика (иногда врет про датацентры)
        "https://api.dtech.lol/ip/{ip}"                                       # Резерв
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
        if not code or code == 'UN' or len(code) != 2: return "🌐"
        # Магия перевода кода страны в Emoji флаг
        return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)

    @staticmethod
    def clean_sni(sni: str, host: str) -> str:
        target = sni if sni else host
        if not target: return "No-SNI"
        if len(target) > 25: return "Generic"
        return target

    @staticmethod
    def create_info_node(text: str) -> str:
        """Создает фейковый VMESS узел, который служит заголовком"""
        # Используем 127.0.0.1, чтобы клиент не пытался реально подключиться
        dummy_data = {
            "v": "2", "ps": text, "add": "127.0.0.1", "port": "1080",
            "id": "00000000-0000-0000-0000-000000000000",
            "aid": "0", "net": "tcp", "type": "none", "host": "", "path": "", "tls": ""
        }
        return "vmess://" + Utils.encode_base64(json.dumps(dummy_data))

# ===========================
# 🧠 ПАРСЕР И ПРОВЕРКА
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

    async def resolve_geo(self, ip: str, session: aiohttp.ClientSession) -> Tuple[str, str]:
        if ip in self.geo_cache: return self.geo_cache[ip]

        # Перебор API пока не найдем ответ
        for api_tpl in CONFIG["GEO_APIS"]:
            try:
                url = api_tpl.format(ip=ip)
                async with session.get(url, timeout=3, ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Унификация полей от разных API
                        cc = data.get('countryCode') or data.get('country_code') or 'UN'
                        cn = data.get('country') or data.get('country_name') or 'Unknown'
                        
                        # Если API вернуло UN или XX, пробуем следующий API
                        if cc and cc not in ['UN', 'XX']:
                            self.geo_cache[ip] = (cc, cn)
                            return cc, cn
            except: continue
        
        return "UN", "Unknown"

    async def check_proxy(self, raw_link: str, session: aiohttp.ClientSession) -> Optional[ProxyNode]:
        node = None
        try:
            # Парсинг (упрощенный)
            if raw_link.startswith("vless://"):
                p = urllib.parse.urlparse(raw_link)
                q = urllib.parse.parse_qs(p.query)
                node = ProxyNode(raw_link, "VLESS", p.hostname, p.port, q.get('sni',[''])[0], q.get('host',[''])[0])
            elif raw_link.startswith("vmess://"):
                d = json.loads(Utils.decode_base64(raw_link[8:]))
                node = ProxyNode(raw_link, "VMESS", d['add'], int(d['port']), d.get('sni','') or d.get('host',''), d.get('host',''))
            
            if not node: return None

            # 1. Пинг (TCP Connect)
            t0 = time.perf_counter()
            fut = asyncio.open_connection(node.address, node.port)
            r, w = await asyncio.wait_for(fut, timeout=5)
            w.close()
            await w.wait_closed()
            node.latency = (time.perf_counter() - t0) * 1000

            if node.latency > CONFIG["MAX_LATENCY"]: return None

            # 2. GeoIP (только для живых)
            node.country_code, node.country_name = await self.resolve_geo(node.address, session)
            return node

        except: return None

    async def run(self):
        logger.info("🚀 Запуск обновления...")
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

        # Сортировка по пингу
        valid_nodes.sort(key=lambda x: x.latency)
        logger.info(f"✅ Доступно узлов: {len(valid_nodes)}")

        final_lines = []

        # === 1. ДОБАВЛЕНИЕ ЗАГОЛОВКА ===
        # Добавляем "Info Node" самым первым
        header_title = f"ℹ️ === {CONFIG['SUB_TITLE']} === ℹ️"
        final_lines.append(Utils.create_info_node(header_title))
        
        # Добавляем дату обновления
        update_time = datetime.datetime.now().strftime("%d.%m %H:%M")
        header_date = f"🔄 Updated: {update_time}"
        final_lines.append(Utils.create_info_node(header_date))
        
        # Добавляем разделитель
        final_lines.append(Utils.create_info_node("---------------------------------"))

        # === 2. ФОРМИРОВАНИЕ СПИСКА ===
        for i, node in enumerate(valid_nodes, 1):
            flag = Utils.get_flag(node.country_code)
            sni = Utils.clean_sni(node.sni, node.address)
            
            # Имя: 01 🇫🇮 FI | google.com | 45ms
            new_name = f"{i:02d} {flag} {node.country_code} | {sni} | {int(node.latency)}ms"
            
            if node.protocol == "VLESS":
                p = urllib.parse.urlparse(node.raw_uri)
                final_lines.append(p._replace(fragment=urllib.parse.quote(new_name)).geturl())
            elif node.protocol == "VMESS":
                try:
                    js = json.loads(Utils.decode_base64(node.raw_uri[8:]))
                    js['ps'] = new_name
                    final_lines.append("vmess://" + Utils.encode_base64(json.dumps(js, separators=(',', ':'))))
                except: pass

        # Сохранение
        with open(CONFIG["OUTPUT_FILE"], "w", encoding="utf-8") as f:
            f.write(Utils.encode_base64("\n".join(final_lines)))
        
        logger.info("💾 Готово!")

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(Bot().run())
