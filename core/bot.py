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
import socket
from aiohttp_socks import ProxyConnector
from dataclasses import dataclass
from typing import List, Optional

# ===========================
# 🕒 НАСТРОЙКА ВРЕМЕНИ (MSK UTC+3)
# ===========================
def msk_converter(*args):
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).timetuple()

logging.Formatter.converter = msk_converter
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("FrostyBot")

# ===========================
# ⚙️ КОНФИГУРАЦИЯ (v5.5 Full)
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    "SUB_TITLE": "_ _ _By Frosty XC_ _ _",
    
    # Ресурсы и лимиты
    "THREADS": 10,            # Потоки для Sing-box
    "TCP_THREADS": 50,        # Потоки для TCP отсева
    "TCP_TIMEOUT": 2,         # Секунды на проверку порта
    "PIPELINE_TIMEOUT": 30,   # Общий таймаут на 1 прокси
    
    # Тест скорости
    "SPEED_TEST_URL": "http://speed.cloudflare.com/__down?bytes=8000000",
    "MIN_SPEED_MBPS": 5.0,    # Порог входа в список
    "EARLY_EXIT_SPEED": 8.0,  # Скорость для мгновенного одобрения (Early Exit)
    
    "CHECK_URLS": [
        "https://www.google.com/generate_204",
        "https://www.cloudflare.com/cdn-cgi/trace"
    ],
    
    "GEO_API": "https://ipwho.is/",
    "USER_AGENT": "v2rayNG/1.8.5"
}

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
            "id": "00000000-0000-0000-0000-000000000000",
            "net": "tcp", "type": "none"
        }
        return "vmess://" + Utils.encode_b64(json.dumps(dummy))

@dataclass
class ProxyNode:
    raw_uri: str
    protocol: str
    config: dict
    country_code: str = "UN"
    speed_mbps: float = 0.0

# ===========================
# 🛠 МЕНЕДЖЕР SING-BOX
# ===========================

class SingBoxManager:
    @staticmethod
    def generate_config(node: ProxyNode, local_port: int) -> dict:
        c = node.config
        outbound = {
            "type": "vless", "tag": "proxy",
            "server": c['server'], "server_port": c['port'],
            "uuid": c['uuid'], "packet_encoding": "xudp"
        }
        if c.get('security') == 'reality':
            outbound["tls"] = {
                "enabled": True, "server_name": c.get('sni'),
                "utls": {"enabled": True, "fingerprint": c.get('fp', 'chrome')},
                "reality": {"enabled": True, "public_key": c.get('pbk'), "short_id": c.get('sid')}
            }
        if c.get('flow'): outbound["flow"] = c.get('flow')

        return {
            "log": {"level": "fatal"},
            "dns": {"servers": [{"tag": "google", "address": "8.8.8.8"}]},
            "inbounds": [{
                "type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": local_port,
                "sniff": True, "sniff_override_destination": True
            }],
            "outbounds": [outbound]
        }

# ===========================
# 🧠 КОР БОТА
# ===========================

class FullTesterBot:
    async def parse_links(self) -> List[ProxyNode]:
        """Загрузка и УДАЛЕНИЕ ДУБЛИКАТОВ"""
        nodes = []
        seen = set()
        try:
            with open(CONFIG["SOURCES_FILE"], "r") as f:
                urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        except: return []

        async with aiohttp.ClientSession() as session:
            for url in urls:
                try:
                    async with session.get(url, timeout=10) as resp:
                        content = await resp.text()
                        if "://" not in content[:50]: content = Utils.decode_b64(content)
                        
                        count_before = len(nodes)
                        for line in content.splitlines():
                            line = line.strip()
                            if line.startswith("vless://"):
                                p = urllib.parse.urlparse(line)
                                q = urllib.parse.parse_qs(p.query)
                                # Уникальный ID: хост + порт + uuid
                                uid = f"{p.hostname}:{p.port}:{p.username}"
                                if uid not in seen:
                                    nodes.append(ProxyNode(line, "VLESS", {
                                        "server": p.hostname, "port": p.port, "uuid": p.username,
                                        "sni": q.get('sni',[''])[0], "pbk": q.get('pbk',[''])[0],
                                        "sid": q.get('sid',[''])[0], "fp": q.get('fp',['chrome'])[0],
                                        "security": q.get('security',[''])[0], "flow": q.get('flow',[''])[0]
                                    }))
                                    seen.add(uid)
                        logger.info(f"📥 {url} -> Уникальных: {len(nodes) - count_before}")
                except: pass
        return nodes

    async def tcp_check(self, node: ProxyNode, sem: asyncio.Semaphore) -> bool:
        """Быстрый TCP отсев"""
        async with sem:
            try:
                loop = asyncio.get_running_loop()
                ip = await loop.run_in_executor(None, socket.gethostbyname, node.config['server'])
                conn = asyncio.open_connection(ip, node.config['port'])
                _, w = await asyncio.wait_for(conn, timeout=CONFIG["TCP_TIMEOUT"])
                w.close()
                await w.wait_closed()
                return True
            except: return False

    async def validate_node(self, node: ProxyNode, sem: asyncio.Semaphore) -> Optional[ProxyNode]:
        """Глубокая проверка (Sing-box + Early Exit Speed)"""
        async with sem:
            port = random.randint(20000, 55000)
            cfg_path = f"t_{port}.json"
            with open(cfg_path, 'w') as f: json.dump(SingBoxManager.generate_config(node, port), f)

            proc = subprocess.Popen(["sing-box", "run", "-c", cfg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(2.5) 

            try:
                connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
                async with aiohttp.ClientSession(connector=connector) as session:
                    # 1. Anti-Ban
                    async with session.get(random.choice(CONFIG["CHECK_URLS"]), timeout=5) as resp:
                        if resp.status >= 400: raise Exception("Banned")

                    # 2. GeoIP
                    async with session.get(CONFIG["GEO_API"], timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('success'): node.country_code = data.get('country_code', 'UN')
                            else: raise Exception("Geo Fail")

                    # 3. EARLY EXIT SPEED TEST
                    t_start = time.perf_counter()
                    async with session.get(CONFIG["SPEED_TEST_URL"]) as resp:
                        if resp.status == 200:
                            total_bytes = 0
                            async for chunk in resp.content.iter_chunked(1024 * 64):
                                total_bytes += len(chunk)
                                
                                # Проверка после 1.5 МБ
                                if total_bytes > 1_500_000:
                                    elapsed = time.perf_counter() - t_start
                                    current_speed = (total_bytes * 8 / elapsed) / 1_000_000
                                    
                                    if current_speed >= CONFIG["EARLY_EXIT_SPEED"]:
                                        node.speed_mbps = round(current_speed, 1)
                                        logger.info(f"✨ FAST: {node.config['server']} | {node.country_code} | {node.speed_mbps} Mbps")
                                        return node
                                    
                                    if total_bytes > 3_000_000 and current_speed < 1.0:
                                        raise Exception("Slow")

                            duration = time.perf_counter() - t_start
                            node.speed_mbps = round((total_bytes * 8 / (duration or 0.001)) / 1_000_000, 1)
                            if node.speed_mbps >= CONFIG["MIN_SPEED_MBPS"]:
                                logger.info(f"✅ OK: {node.config['server']} | {node.country_code} | {node.speed_mbps} Mbps")
                                return node
            except: pass
            finally:
                proc.terminate()
                try: proc.wait(timeout=2)
                except: proc.kill()
                if os.path.exists(cfg_path): os.remove(cfg_path)
            return None

    async def run(self):
        msk_now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        logger.info(f"🚀 FROSTY-BOT V5.5 (MSK: {msk_now.strftime('%H:%M:%S')})")
        
        # 1. Загрузка и Дедупликация
        all_nodes = await self.parse_links()
        logger.info(f"🔎 Уникальных ссылок: {len(all_nodes)}")

        # 2. Быстрый TCP отсев
        logger.info(f"📡 TCP отсев ({CONFIG['TCP_THREADS']} потоков)...")
        tcp_sem = asyncio.Semaphore(CONFIG["TCP_THREADS"])
        tcp_results = await asyncio.gather(*[self.tcp_check(n, tcp_sem) for n in all_nodes])
        candidates = [n for n, ok in zip(all_nodes, tcp_results) if ok]
        logger.info(f"📉 Осталось живых портов: {len(candidates)}")

        # 3. Глубокая проверка
        if candidates:
            logger.info(f"🏎️ Запуск Sing-box + Early Exit Speed...")
            sem = asyncio.Semaphore(CONFIG["THREADS"])
            results = await asyncio.gather(*[self.validate_node(n, sem) for n in candidates])
            
            alive = [r for r in results if r]
            alive.sort(key=lambda x: x.speed_mbps, reverse=True)

            # ЗАГОЛОВКИ
            update_time = (datetime.datetime.utcnow() + datetime.timedelta(hours=3)).strftime('%d.%m %H:%M')
            final_list = [
                Utils.create_header(f"ℹ️ {CONFIG['SUB_TITLE']}"),
                Utils.create_header(f"⚡ High Speed (Invisible Mbps)"),
                Utils.create_header(f"🔄 Updated: {update_time} (MSK)")
            ]

            # СБОРКА ЧИСТОГО СПИСКА
            for i, n in enumerate(alive, 1):
                flag = chr(ord(n.country_code[0]) + 127397) + chr(ord(n.country_code[1]) + 127397)
                sni = n.config['sni'] or n.config['server']
                # Название без цифр Mbps, но отсортировано!
                display_name = f"{i:02d} {flag} {n.country_code} | {sni} | {n.protocol}"
                
                p = urllib.parse.urlparse(n.raw_uri)
                final_list.append(p._replace(fragment=urllib.parse.quote(display_name)).geturl())

            with open(CONFIG["OUTPUT_FILE"], "w", encoding="utf-8") as f:
                f.write(Utils.encode_b64("\n".join(final_list)))

            logger.info(f"💾 Готово! Сохранено: {len(alive)} узлов.")

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(FullTesterBot().run())
