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
# 🕒 МСК ВРЕМЯ (UTC+3)
# ===========================
def msk_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=3)

def msk_converter(*args):
    return msk_now().timetuple()

logging.Formatter.converter = msk_converter
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("SunnyBot")

# ===========================
# ⚙️ КОНФИГУРАЦИЯ (v6.4 Champion)
# ===========================
CONFIG = {
    # Файлы
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_SUB": "subscription.txt",
    "TEMPLATE_FILE": "config/template.html",
    "OUTPUT_INDEX": "index.html",
    
    # Новая ссылка Netlify
    "PUBLIC_URL": "https://sunny-areral.netlify.app/", 
    
    # Ресурсы
    "THREADS": 10,            # Потоки Sing-box
    "TCP_TIMEOUT": 2,         # Отсев портов
    "PIPELINE_TIMEOUT": 20,   # Таймаут обычной проверки
    
    # Массовая проверка (Экономим трафик)
    # Если прокси выдал >8 Mbps, мы его берем и останавливаем тест.
    "SPEED_TEST_URL": "http://speed.cloudflare.com/__down?bytes=8000000",
    "MIN_SPEED_MBPS": 5.0,
    "EARLY_EXIT_SPEED": 8.0,
    
    # Чемпионский тест (Только для ТОП-1)
    # Качаем 50 МБ, чтобы разогнать канал до предела
    "CHAMPION_TEST_URL": "http://speed.cloudflare.com/__down?bytes=50000000",
    
    "CHECK_URLS": ["https://www.google.com/generate_204", "https://www.cloudflare.com/cdn-cgi/trace"],
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

@dataclass
class ProxyNode:
    raw_uri: str
    protocol: str
    config: dict
    country_code: str = "UN"
    speed_mbps: float = 0.0

# ===========================
# 🌐 ГЕНЕРАТОР САЙТА
# ===========================
class WebGenerator:
    @staticmethod
    def build(count: int, top_speed: float):
        try:
            with open(CONFIG["TEMPLATE_FILE"], "r", encoding="utf-8") as f:
                template = f.read()
            
            update_str = msk_now().strftime('%d.%m %H:%M')
            
            html = template.replace("{{UPDATE_TIME}}", update_str)
            html = html.replace("{{PROXY_COUNT}}", str(count))
            # Округляем до целого для красоты (например, 350 вместо 350.2)
            html = html.replace("{{MAX_SPEED}}", str(int(top_speed)))
            html = html.replace("{{SUB_LINK}}", CONFIG["PUBLIC_URL"])
            
            with open(CONFIG["OUTPUT_INDEX"], "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"🌐 Сайт обновлен. Топ скорость: {int(top_speed)} Mbps")
        except Exception as e:
            logger.error(f"⚠️ Ошибка генерации сайта: {e}")

# ===========================
# 🛠 SING-BOX MANAGER
# ===========================
class SingBoxManager:
    @staticmethod
    def generate_config(node: ProxyNode, local_port: int) -> dict:
        c = node.config
        outbound = {
            "type": "vless", "tag": "proxy", "server": c['server'], "server_port": c['port'],
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
            "inbounds": [{"type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": local_port, "sniff": True}],
            "outbounds": [outbound]
        }

# ===========================
# 🧠 CORE LOGIC
# ===========================
class SunnyBot:
    async def get_nodes(self) -> List[ProxyNode]:
        nodes, seen = [], set()
        async with aiohttp.ClientSession() as session:
            try:
                with open(CONFIG["SOURCES_FILE"], "r") as f:
                    urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            except: return []

            for url in urls:
                try:
                    async with session.get(url, timeout=10) as resp:
                        text = await resp.text()
                        if "://" not in text[:50]: text = Utils.decode_b64(text)
                        for line in text.splitlines():
                            if line.startswith("vless://"):
                                p = urllib.parse.urlparse(line)
                                q = urllib.parse.parse_qs(p.query)
                                uid = f"{p.hostname}:{p.port}:{p.username}"
                                if uid not in seen:
                                    nodes.append(ProxyNode(line, "VLESS", {
                                        "server": p.hostname, "port": p.port, "uuid": p.username,
                                        "sni": q.get('sni',[''])[0], "pbk": q.get('pbk',[''])[0],
                                        "sid": q.get('sid',[''])[0], "fp": q.get('fp',['chrome'])[0],
                                        "security": q.get('security',[''])[0], "flow": q.get('flow',[''])[0]
                                    }))
                                    seen.add(uid)
                except: pass
        return nodes

    async def tcp_test(self, node: ProxyNode, sem: asyncio.Semaphore) -> bool:
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

    async def standard_check(self, node: ProxyNode, sem: asyncio.Semaphore) -> Optional[ProxyNode]:
        """Обычная проверка (с ранним выходом)"""
        async with sem:
            port = random.randint(20000, 55000)
            cfg = f"t_{port}.json"
            
            with open(cfg, 'w') as f: json.dump(SingBoxManager.generate_config(node, port), f)
            proc = subprocess.Popen(["sing-box", "run", "-c", cfg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(2.0)

            try:
                connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
                async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=CONFIG["PIPELINE_TIMEOUT"])) as session:
                    # 1. AntiBan
                    async with session.get(random.choice(CONFIG["CHECK_URLS"]), timeout=4) as resp:
                        if resp.status >= 400: raise Exception("Ban")
                    # 2. Geo
                    async with session.get(CONFIG["GEO_API"], timeout=4) as resp:
                        data = await resp.json()
                        if data.get('success'): node.country_code = data.get('country_code', 'UN')
                        else: raise Exception("GeoFail")
                    # 3. Efficiency Speed Test
                    t_start = time.perf_counter()
                    async with session.get(CONFIG["SPEED_TEST_URL"]) as resp:
                        total = 0
                        async for chunk in resp.content.iter_chunked(65536):
                            total += len(chunk)
                            if total > 1500000: # Early exit
                                cur = (total*8/(time.perf_counter()-t_start))/1000000
                                if cur >= CONFIG["EARLY_EXIT_SPEED"]:
                                    node.speed_mbps = round(cur, 1)
                                    return node
                        
                        dur = time.perf_counter()-t_start
                        node.speed_mbps = round((total*8/(dur or 0.1))/1000000, 1)
                        if node.speed_mbps >= CONFIG["MIN_SPEED_MBPS"]:
                            return node
            except: pass
            finally:
                proc.terminate()
                if os.path.exists(cfg): os.remove(cfg)
            return None

    async def champion_test(self, node: ProxyNode) -> float:
        """ЭКСТРЕМАЛЬНЫЙ ТЕСТ ТОЛЬКО ДЛЯ ТОП-1"""
        logger.info(f"🏆 Запуск Чемпионского теста для {node.config['server']}...")
        port = random.randint(55001, 60000)
        cfg = f"champ_{port}.json"
        
        with open(cfg, 'w') as f: json.dump(SingBoxManager.generate_config(node, port), f)
        proc = subprocess.Popen(["sing-box", "run", "-c", cfg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(2.5) # Даем чуть больше времени на разгон

        max_speed = node.speed_mbps # Берем старую как минимум

        try:
            connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
            # Таймаут побольше для скачивания 50МБ
            async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=60)) as session:
                t_start = time.perf_counter()
                async with session.get(CONFIG["CHAMPION_TEST_URL"]) as resp:
                    if resp.status == 200:
                        content = await resp.read() # Качаем ВСЁ до конца
                        duration = time.perf_counter() - t_start
                        
                        size_bits = len(content) * 8
                        real_speed = (size_bits / duration) / 1_000_000
                        max_speed = round(real_speed, 1)
                        logger.info(f"🚀 ИСТИННАЯ СКОРОСТЬ: {max_speed} Mbps")
        except Exception as e:
            logger.warning(f"Сбой чемпионского теста: {e}")
        finally:
            proc.terminate()
            if os.path.exists(cfg): os.remove(cfg)
        
        return max_speed

    async def run(self):
        logger.info(f"🚀 SUNNY-BOT V6.4 CHAMPION (MSK: {msk_now().strftime('%H:%M:%S')})")
        nodes = await self.get_nodes()
        logger.info(f"🔎 Уникальных ссылок: {len(nodes)}")

        tcp_sem = asyncio.Semaphore(50)
        tcp_res = await asyncio.gather(*[self.tcp_test(n, tcp_sem) for n in nodes])
        candidates = [n for n, ok in zip(nodes, tcp_res) if ok]

        alive = []
        if candidates:
            # 1. МАССОВАЯ ПРОВЕРКА (БЫСТРАЯ)
            sem = asyncio.Semaphore(CONFIG["THREADS"])
            results = await asyncio.gather(*[self.standard_check(n, sem) for n in candidates])
            alive = [r for r in results if r]
            alive.sort(key=lambda x: x.speed_mbps, reverse=True)

            # 2. ЧЕМПИОНСКИЙ ТЕСТ (ТОЛЬКО ТОП-1)
            top_speed = 0.0
            if alive:
                top_node = alive[0]
                # Обновляем скорость чемпиона в списке
                top_speed = await self.champion_test(top_node)
                top_node.speed_mbps = top_speed

            # 3. ПОДПИСКА (ЧИСТАЯ)
            final_sub = []
            for i, n in enumerate(alive, 1):
                flag = chr(ord(n.country_code[0])+127397) + chr(ord(n.country_code[1])+127397)
                nm = f"{i:02d} {flag} {n.country_code} | {n.config['sni'] or n.config['server']} | {n.protocol}"
                p = urllib.parse.urlparse(n.raw_uri)
                final_sub.append(p._replace(fragment=urllib.parse.quote(nm)).geturl())
            
            with open(CONFIG["OUTPUT_SUB"], "w", encoding="utf-8") as f:
                f.write(Utils.encode_b64("\n".join(final_sub)))

            # 4. ГЕНЕРАЦИЯ САЙТА (С РЕАЛЬНОЙ МАКС СКОРОСТЬЮ)
            WebGenerator.build(len(alive), top_speed)
            logger.info("💾 Цикл завершен успешно")

if __name__ == "__main__":
    asyncio.run(SunnyBot().run())
