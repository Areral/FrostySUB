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
from aiohttp_socks import ProxyConnector
from dataclasses import dataclass
from typing import List, Optional

# ===========================
# ⚙️ НАСТРОЙКИ
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    "SUB_TITLE": "_ _ _By Frosty XC_ _ _",
    
    "THREADS": 10,        # Количество одновременных проверок
    "TIMEOUT": 20,        # Общий таймаут
    "GEO_API": "https://ipwho.is/",
    "USER_AGENT": "v2rayNG/1.8.5"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("ProxyChecker")

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

    @staticmethod
    def create_header(text: str) -> str:
        dummy = {
            "v": "2", "ps": text, "add": "127.0.0.1", "port": "1080",
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "net": "tcp", "type": "none"
        }
        return "vmess://" + Utils.encode_b64(json.dumps(dummy))

@dataclass
class ProxyNode:
    raw_uri: str
    protocol: str
    config: dict
    country_code: str = "UN"
    latency: float = 9999.0

# ===========================
# 🛠 МЕНЕДЖЕР SING-BOX
# ===========================

class SingBoxManager:
    @staticmethod
    def generate_config(node: ProxyNode, local_port: int) -> dict:
        c = node.config
        outbound = {
            "type": "vless",
            "tag": "proxy",
            "server": c['server'],
            "server_port": c['port'],
            "uuid": c['uuid'],
            "packet_encoding": "xudp"
        }
        
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
        
        if c.get('flow'): 
            outbound["flow"] = c.get('flow')

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
    async def parse_links(self) -> List[ProxyNode]:
        nodes = []
        seen_identifiers = set() # Для удаления дубликатов
        
        try:
            with open(CONFIG["SOURCES_FILE"], "r") as f:
                urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        except: 
            logger.error("Файл источников не найден!")
            return []

        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=10) as resp:
                        content = await resp.text()
                        if "://" not in content[:50]:
                            content = Utils.decode_b64(content)
                            
                        count_before = len(nodes)
                        for line in content.splitlines():
                            line = line.strip()
                            if line.startswith("vless://"):
                                p = urllib.parse.urlparse(line)
                                q = urllib.parse.parse_qs(p.query)
                                
                                # Параметры для идентификации уникальности
                                server = p.hostname
                                port = p.port
                                uuid = p.username
                                
                                # Создаем уникальный ключ (ID) прокси
                                # Если сервер, порт и UUID совпадают — это один и тот же прокси
                                node_id = f"{server}:{port}:{uuid}"
                                
                                if node_id not in seen_identifiers:
                                    nodes.append(ProxyNode(line, "VLESS", {
                                        "server": server, "port": port, "uuid": uuid,
                                        "sni": q.get('sni',[''])[0], "pbk": q.get('pbk',[''])[0],
                                        "sid": q.get('sid',[''])[0], "fp": q.get('fp',['chrome'])[0],
                                        "security": q.get('security',[''])[0], "flow": q.get('flow',[''])[0]
                                    }))
                                    seen_identifiers.add(node_id)
                        
                        logger.info(f"📥 {url} -> Добавлено новых: {len(nodes) - count_before}")
                except Exception as e:
                    logger.warning(f"Ошибка источника {url}: {e}")
        
        return nodes

    async def validate_via_proxy(self, node: ProxyNode, semaphore: asyncio.Semaphore) -> Optional[ProxyNode]:
        async with semaphore:
            port = random.randint(20000, 40000)
            config_path = f"config_{port}.json"
            
            with open(config_path, 'w') as f:
                json.dump(SingBoxManager.generate_config(node, port), f)

            process = subprocess.Popen(
                ["sing-box", "run", "-c", config_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            
            await asyncio.sleep(2.5)

            t0 = time.perf_counter()
            try:
                connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(CONFIG["GEO_API"], timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('success'):
                                node.country_code = data.get('country_code', 'UN')
                                node.latency = (time.perf_counter() - t0) * 1000
                                logger.info(f"✅ OK: {node.config['server']} -> {node.country_code} ({int(node.latency)}ms)")
                                return node
            except:
                pass
            finally:
                process.terminate()
                try: process.wait(timeout=2)
                except: process.kill()
                if os.path.exists(config_path): os.remove(config_path)
            
            return None

    async def run(self):
        logger.info("🚀 ЗАПУСК ВАЛИДАЦИИ...")
        
        # 1. Загрузка и Дедупликация
        all_nodes = await self.parse_links()
        logger.info(f"🔎 После удаления дубликатов осталось: {len(all_nodes)} узлов")

        # 2. Проверка
        sem = asyncio.Semaphore(CONFIG["THREADS"])
        tasks = [self.validate_via_proxy(n, sem) for n in all_nodes]
        results = await asyncio.gather(*tasks)
        
        alive = [r for r in results if r]
        alive.sort(key=lambda x: x.latency)

        # 3. Сборка подписки
        final_list = [
            Utils.create_header(f"ℹ️ {CONFIG['SUB_TITLE']}"),
            Utils.create_header(f"🔄 Updated: {datetime.datetime.now().strftime('%d.%m %H:%M')}")
        ]

        for i, n in enumerate(alive, 1):
            flag = chr(ord(n.country_code[0]) + 127397) + chr(ord(n.country_code[1]) + 127397)
            # Отображаем SNI или сервер в названии
            sni_display = n.config['sni'] if n.config['sni'] else n.config['server']
            display_name = f"{i:02d} {flag} {n.country_code} | {sni_display} | {n.protocol}"
            
            parsed_uri = urllib.parse.urlparse(n.raw_uri)
            new_uri = parsed_uri._replace(fragment=urllib.parse.quote(display_name)).geturl()
            final_list.append(new_uri)

        with open(CONFIG["OUTPUT_FILE"], "w", encoding="utf-8") as f:
            f.write(Utils.encode_b64("\n".join(final_list)))

        logger.info(f"💾 Готово! Сохранено живых: {len(alive)}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(CheckerBot().run())
