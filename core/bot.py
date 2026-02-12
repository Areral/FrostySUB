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
from aiohttp_socks import ProxyConnector # Библиотека для работы через SOCKS5
from dataclasses import dataclass
from typing import List, Optional

# ===========================
# ⚙️ НАСТРОЙКИ
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    "SUB_TITLE": "_ _ _By Frosty XC_ _ _",
    
    "THREADS": 5,        # Ограничим до 5, так как запуск sing-box требует ресурсов
    "TIMEOUT": 15,       # Время на всё: старт прокси + запрос к API
    "GEO_API": "https://ipwho.is/",
    "USER_AGENT": "v2rayNG/1.8.5"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("ProxyChecker")

# ===========================
# 📦 КЛАССЫ
# ===========================

@dataclass
class ProxyNode:
    raw_uri: str
    protocol: str
    config: dict  # Распарсенные параметры (UUID, PBK, SNI и т.д.)
    country_code: str = "UN"
    latency: float = 9999.0

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

# ===========================
# 🛠 SING-BOX CONFIG GENERATOR
# ===========================

class SingBoxManager:
    @staticmethod
    def generate_config(node: ProxyNode, local_port: int) -> dict:
        """Создает минимальный конфиг для Sing-box, чтобы поднять SOCKS5 прокси"""
        c = node.config
        
        # Шаблон для VLESS Reality
        outbound = {
            "type": "vless",
            "tag": "proxy",
            "server": c['server'],
            "server_port": c['port'],
            "uuid": c['uuid'],
            "packet_encoding": "xudp"
        }
        
        # Добавляем Reality / TLS если есть
        if c.get('security') == 'reality':
            outbound["tls"] = {
                "enabled": True,
                "server_name": c.get('sni'),
                "utls": {"enabled": True, "fingerprint": c.get('fp', 'chrome')},
                "reality": {
                    "enabled": True,
                    "public_key": c.get('pbk'),
                    "short_id": c.get('sid')
                }
            }
        
        if c.get('flow'): outbound["flow"] = c.get('flow')

        return {
            "log": {"level": "error"},
            "inbounds": [{
                "type": "socks",
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "listen_port": local_port
            }],
            "outbounds": [outbound]
        }

# ===========================
# 🧠 ОСНОВНОЙ БОТ
# ===========================

class CheckerBot:
    def __init__(self):
        self.geo_cache = {}

    async def parse_links(self) -> List[ProxyNode]:
        nodes = []
        try:
            with open(CONFIG["SOURCES_FILE"], "r") as f:
                urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        except: return []

        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=10) as resp:
                        text = Utils.decode_b64(await resp.text())
                        for line in text.splitlines():
                            if line.startswith("vless://"):
                                p = urllib.parse.urlparse(line)
                                q = urllib.parse.parse_qs(p.query)
                                nodes.append(ProxyNode(line, "VLESS", {
                                    "server": p.hostname, "port": p.port, "uuid": p.username,
                                    "sni": q.get('sni',[''])[0], "pbk": q.get('pbk',[''])[0],
                                    "sid": q.get('sid',[''])[0], "fp": q.get('fp',['chrome'])[0],
                                    "security": q.get('security',[''])[0], "flow": q.get('flow',[''])[0]
                                }))
                except: pass
        return nodes

    async def validate_via_proxy(self, node: ProxyNode, semaphore: asyncio.Semaphore) -> Optional[ProxyNode]:
        async with semaphore:
            port = random.randint(20000, 40000)
            config_path = f"config_{port}.json"
            
            # 1. Генерируем конфиг
            with open(config_path, 'w') as f:
                json.dump(SingBoxManager.generate_config(node, port), f)

            # 2. Запускаем Sing-box
            process = subprocess.Popen(
                ["sing-box", "run", "-c", config_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            
            # Даем прокси 2 секунды на старт
            await asyncio.sleep(2)

            # 3. Делаем запрос через прокси
            connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
            t0 = time.perf_counter()
            try:
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(CONFIG["GEO_API"], timeout=8) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('success'):
                                node.country_code = data.get('country_code', 'UN')
                                node.latency = (time.perf_counter() - t0) * 1000
                                logger.info(f"✅ Успех: {node.config['server']} -> {node.country_code} ({int(node.latency)}ms)")
                                return node
            except Exception as e:
                pass
            finally:
                process.terminate()
                if os.path.exists(config_path): os.remove(config_path)
            
            return None

    async def run(self):
        logger.info("🚀 ЗАПУСК ВАЛИДАЦИИ ЧЕРЕЗ SING-BOX...")
        all_nodes = await self.parse_links()
        logger.info(f"🔎 Найдено {len(all_nodes)} узлов. Начинаю проверку...")

        sem = asyncio.Semaphore(CONFIG["THREADS"])
        results = await asyncio.gather(*[self.validate_via_proxy(n, sem) for n in all_nodes])
        
        alive = [r for r in results if r]
        alive.sort(key=lambda x: x.latency)

        # Сохранение
        final = [
            Utils.create_header(f"ℹ️ {CONFIG['SUB_TITLE']}"),
            Utils.create_header(f"🔄 Updated: {datetime.datetime.now().strftime('%d.%m %H:%M')}")
        ]

        for i, n in enumerate(alive, 1):
            flag = chr(ord(n.country_code[0]) + 127397) + chr(ord(n.country_code[1]) + 127397)
            new_name = f"{i:02d} {flag} {n.country_code} | {n.config['sni'] or n.config['server']} | {n.protocol}"
            p = urllib.parse.urlparse(n.raw_uri)
            final.append(p._replace(fragment=urllib.parse.quote(new_name)).geturl())

        with open(CONFIG["OUTPUT_FILE"], "w") as f:
            f.write(Utils.encode_base64("\n".join(final)))

        logger.info(f"💾 Готово! Живых: {len(alive)}")

if __name__ == "__main__":
    asyncio.run(CheckerBot().run())
