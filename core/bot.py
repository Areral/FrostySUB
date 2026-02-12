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
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ===========================
# ⚙️ НАСТРОЙКИ
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    "TIMEOUT": 10,                # Таймаут проверки сокета (сек)
    "MAX_CONCURRENT": 30,         # Кол-во одновременных проверок
    "MAX_LATENCY": 2000,          # Отсеивать узлы с пингом выше этого (мс)
    
    # API для определения страны (с ротацией, чтобы избежать банов)
    "GEO_APIS": [
        "http://ip-api.com/json/{ip}?fields=status,country,countryCode",
        "https://ipwho.is/{ip}",
        "https://api.dtech.lol/ip/{ip}"
    ],
    
    # Маскировка под реальное приложение (Решает проблему с kissthenight.ru)
    "USER_AGENT": "v2rayNG/1.8.5 (Linux; Android 13; K)"
}

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("Bot")

# ===========================
# 📦 STRUCURES & UTILS
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
    speed_score: float = 0.0

class Utils:
    @staticmethod
    def decode_base64(text: str) -> str:
        """Умное декодирование Base64 с исправлением padding"""
        text = text.strip()
        if not text: return ""
        
        # Если текст уже похож на список ссылок, возвращаем как есть
        if "vless://" in text or "vmess://" in text:
            return text

        try:
            # Исправляем URL-safe символы и padding
            text = text.replace('-', '+').replace('_', '/')
            padding = len(text) % 4
            if padding:
                text += '=' * (4 - padding)
            
            decoded_bytes = base64.b64decode(text)
            return decoded_bytes.decode('utf-8', 'ignore')
        except:
            # Если не удалось декодировать, возвращаем оригинал (возможно это plain text)
            return text

    @staticmethod
    def encode_base64(text: str) -> str:
        """Кодирование в URL-safe Base64 (стандарт подписок)"""
        return base64.b64encode(text.encode('utf-8')).decode('utf-8').replace('+', '-').replace('/', '_').replace('=', '')

    @staticmethod
    def get_flag(code: str) -> str:
        """Превращает 'RU' в 🇷🇺"""
        if not code or code == 'UN' or len(code) != 2: return "🏴"
        return chr(ord(code[0]) + 127397) + chr(ord(code[1]) + 127397)

    @staticmethod
    def clean_sni(sni: str, host: str) -> str:
        target = sni if sni else host
        if not target: return "No-SNI"
        # Убираем слишком длинные или мусорные домены
        if len(target) > 30: return "Generic"
        return target

# ===========================
# 🧠 PARSER
# ===========================

class Parser:
    @staticmethod
    def parse(link: str) -> Optional[ProxyNode]:
        link = link.strip()
        if not link or link.startswith("#"): return None

        try:
            # === VLESS ===
            if link.startswith("vless://"):
                parsed = urllib.parse.urlparse(link)
                params = urllib.parse.parse_qs(parsed.query)
                
                sni = params.get('sni', [''])[0]
                host = params.get('host', [''])[0]
                
                return ProxyNode(
                    raw_uri=link,
                    protocol="VLESS",
                    address=parsed.hostname,
                    port=parsed.port,
                    sni=sni,
                    host=host
                )

            # === VMESS ===
            elif link.startswith("vmess://"):
                b64 = link.replace("vmess://", "")
                json_str = Utils.decode_base64(b64)
                data = json.loads(json_str)
                
                return ProxyNode(
                    raw_uri=link,
                    protocol="VMESS",
                    address=data.get('add'),
                    port=int(data.get('port')),
                    sni=data.get('sni', '') or data.get('host', ''),
                    host=data.get('host', '')
                )
        except Exception:
            return None
        return None

# ===========================
# 🚀 CORE BOT LOGIC
# ===========================

class ProxyBot:
    def __init__(self):
        self.geo_cache = {}
        self.headers = {'User-Agent': CONFIG["USER_AGENT"]}

    async def fetch_sources(self) -> List[str]:
        """Загрузка ссылок из файла конфигурации"""
        raw_proxies = []
        try:
            with open(CONFIG["SOURCES_FILE"], "r") as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except FileNotFoundError:
            logger.error("❌ Файл config/sources.txt не найден!")
            return []

        async with aiohttp.ClientSession(headers=self.headers) as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=15) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            # 1. Декодируем (если это base64)
                            decoded = Utils.decode_base64(text)
                            # 2. Разбиваем по строкам
                            lines = decoded.splitlines()
                            count = 0
                            for line in lines:
                                if "://" in line:
                                    raw_proxies.append(line)
                                    count += 1
                            logger.info(f"📥 {url}: получено {count} узлов")
                        else:
                            logger.error(f"⚠️ Ошибка {resp.status} для {url}")
                except Exception as e:
                    logger.error(f"⚠️ Сбой загрузки {url}: {e}")
        
        return list(set(raw_proxies)) # Удаляем дубликаты

    async def resolve_geo(self, ip: str, session: aiohttp.ClientSession) -> Tuple[str, str]:
        """Определение страны с защитой от сбоев"""
        if ip in self.geo_cache: return self.geo_cache[ip]

        for api_tpl in CONFIG["GEO_APIS"]:
            try:
                url = api_tpl.format(ip=ip)
                async with session.get(url, timeout=2, ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        cc = data.get('countryCode') or data.get('country_code') or 'UN'
                        cn = data.get('country') or data.get('country_name') or 'Unknown'
                        if cc != 'UN':
                            self.geo_cache[ip] = (cc, cn)
                            return cc, cn
            except:
                continue
        return "UN", "Unknown"

    async def check_node(self, node: ProxyNode, session: aiohttp.ClientSession) -> Optional[ProxyNode]:
        """Проверка доступности (TCP Ping) и сбор инфо"""
        t_start = time.perf_counter()
        try:
            # TCP Handshake Check
            future = asyncio.open_connection(node.address, node.port)
            reader, writer = await asyncio.wait_for(future, timeout=CONFIG["TIMEOUT"])
            latency = (time.perf_counter() - t_start) * 1000
            
            writer.close()
            await writer.wait_closed()
            
            node.latency = latency
            
            # Если пинг слишком высокий - пропускаем
            if latency > CONFIG["MAX_LATENCY"]:
                return None

            # Определяем страну
            cc, cn = await self.resolve_geo(node.address, session)
            node.country_code = cc
            node.country_name = cn
            
            # Эмуляция "Speed Score" на основе пинга (чем ниже пинг, тем выше теоретическая скорость)
            # Это нужно для сортировки, так как реальный спидтест в GitHub Actions сложен
            base_speed = 300 if latency < 100 else (10000 / latency)
            node.speed_score = base_speed 

            return node
        except:
            return None # Узел недоступен

    def rename_node(self, node: ProxyNode, index: int) -> str:
        """Переименование узла для красивого списка"""
        flag = Utils.get_flag(node.country_code)
        sni = Utils.clean_sni(node.sni, node.address)
        
        # Формат: 01 🇩🇪 DE | amazon.com | VLESS
        new_name = f"{index:02d} {flag} {node.country_code} | {sni} | {node.protocol}"
        
        # Обновляем имя внутри ссылки
        if node.protocol == "VLESS":
            parsed = urllib.parse.urlparse(node.raw_uri)
            # Меняем фрагмент (имя после #)
            return parsed._replace(fragment=urllib.parse.quote(new_name)).geturl()
            
        elif node.protocol == "VMESS":
            try:
                b64 = node.raw_uri.replace("vmess://", "")
                js = json.loads(Utils.decode_base64(b64))
                js['ps'] = new_name
                return "vmess://" + Utils.encode_base64(json.dumps(js, separators=(',', ':')))
            except:
                return node.raw_uri
        
        return node.raw_uri

    async def run(self):
        logger.info("🚀 Запуск бота...")
        
        # 1. Сбор
        links = await self.fetch_sources()
        nodes = []
        for l in links:
            n = Parser.parse(l)
            if n: nodes.append(n)
            
        logger.info(f"✅ Успешно распарсено: {len(nodes)} узлов. Начинаем проверку...")

        # 2. Проверка (Multithreading)
        alive_nodes = []
        sem = asyncio.Semaphore(CONFIG["MAX_CONCURRENT"])
        
        async with aiohttp.ClientSession() as session:
            async def worker(node):
                async with sem:
                    return await self.check_node(node, session)
            
            tasks = [worker(n) for n in nodes]
            results = await asyncio.gather(*tasks)
            
            for res in results:
                if res: alive_nodes.append(res)

        # 3. Сортировка (Сначала быстрые)
        alive_nodes.sort(key=lambda x: x.latency)

        logger.info(f"🏁 Живых узлов: {len(alive_nodes)}")

        # 4. Сохранение
        final_lines = []
        for i, node in enumerate(alive_nodes, 1):
            final_lines.append(self.rename_node(node, i))

        # Кодируем весь список в Base64 (стандарт подписок)
        output_str = "\n".join(final_lines)
        b64_output = Utils.encode_base64(output_str)

        with open(CONFIG["OUTPUT_FILE"], "w", encoding="utf-8") as f:
            f.write(b64_output)

        logger.info(f"💾 Файл сохранен: {CONFIG['OUTPUT_FILE']}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(ProxyBot().run())
