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
# ⚙️ КОНФИГУРАЦИЯ (v5.2 - Smart Speed)
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    "SUB_TITLE": "_ _ _By Frosty XC_ _ _",
    
    # Производительность
    "THREADS": 8,            # 8 потоков - оптимально
    "TCP_TIMEOUT": 2,        # Строгий отсев мертвых портов (2 сек)
    "PIPELINE_TIMEOUT": 30,  # Таймаут на всю проверку одного узла
    
    # Anti-Ban (Проверка доступа к "большому интернету")
    "CHECK_URLS": [
        "https://www.google.com/generate_204",
        "https://www.microsoft.com/",
        "https://www.github.com/",
        "https://www.cloudflare.com/"
    ],
    
    # 🚀 SMART SPEED TEST
    # Мы запрашиваем 15 МБ, чтобы увидеть реальную скорость 100+ Mbps.
    # Но мы прервем тест раньше, если узел медленный.
    "SPEED_TEST_URL": "http://speed.cloudflare.com/__down?bytes=15000000",
    
    # Порог "Элитности":
    # Если первые 512 КБ скачались медленнее 2 Mbps, мы дропаем соединение,
    # чтобы не тратить трафик на слабый прокси.
    "MIN_SPEED_MBPS": 10.0,   # В итоговый файл попадут только мощные узлы (>= 10 Mbps в тесте)
    
    "GEO_API": "https://ipwho.is/",
    "USER_AGENT": "v2rayNG/1.8.5"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("SmartBot")

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
    speed_mbps: float = 0.0

# ===========================
# 🛠 SING-BOX CONFIG
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
                "type": "socks", "tag": "socks-in",
                "listen": "127.0.0.1", "listen_port": local_port,
                "sniff": True, "sniff_override_destination": True
            }],
            "outbounds": [outbound]
        }

# ===========================
# 🧠 SMART PIPELINE
# ===========================

class SmartTesterBot:
    async def parse_links(self) -> List[ProxyNode]:
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
                        for line in content.splitlines():
                            line = line.strip()
                            if line.startswith("vless://"):
                                p = urllib.parse.urlparse(line)
                                q = urllib.parse.parse_qs(p.query)
                                # Дедупликация: Сервер + Порт + UUID
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

    async def tcp_check(self, node: ProxyNode) -> bool:
        try:
            loop = asyncio.get_running_loop()
            ip = await loop.run_in_executor(None, socket.gethostbyname, node.config['server'])
            conn = asyncio.open_connection(ip, node.config['port'])
            _, w = await asyncio.wait_for(conn, timeout=CONFIG["TCP_TIMEOUT"])
            w.close()
            await w.wait_closed()
            return True
        except: return False

    async def run_pipeline(self, node: ProxyNode, sem: asyncio.Semaphore) -> Optional[ProxyNode]:
        async with sem:
            port = random.randint(20000, 50000)
            cfg_path = f"t_{port}.json"
            
            with open(cfg_path, 'w') as f:
                json.dump(SingBoxManager.generate_config(node, port), f)

            proc = subprocess.Popen(["sing-box", "run", "-c", cfg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(2.5)

            try:
                connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
                async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=CONFIG["PIPELINE_TIMEOUT"])) as session:
                    
                    # 1. Anti-Ban (Быстрый чек)
                    try:
                        async with session.get(random.choice(CONFIG["CHECK_URLS"]), timeout=4) as resp:
                            if resp.status >= 400: raise Exception("Ban")
                    except: raise Exception("Dead")

                    # 2. GeoIP
                    async with session.get(CONFIG["GEO_API"], timeout=4) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('success'):
                                node.country_code = data.get('country_code', 'UN')
                            else: raise Exception("Geo Fail")
                        else: raise Exception("Geo Fail")

                    # 3. SMART SPEED TEST (Экономия трафика)
                    t_start = time.perf_counter()
                    async with session.get(CONFIG["SPEED_TEST_URL"]) as resp:
                        if resp.status == 200:
                            total_bytes = 0
                            chunk_count = 0
                            
                            # Читаем поток чанками (кусками)
                            async for chunk in resp.content.iter_chunked(1024 * 64): # 64KB chunks
                                total_bytes += len(chunk)
                                chunk_count += 1
                                
                                # ПРОВЕРКА ПОСЛЕ 1 МБ (16 чанков)
                                if chunk_count == 16:
                                    elapsed = time.perf_counter() - t_start
                                    current_speed = (total_bytes * 8 / elapsed) / 1_000_000
                                    
                                    # Если на старте скорость меньше 3 Mbps — отрубаем!
                                    # Это экономит ~14 МБ трафика на каждом слабом узле.
                                    if current_speed < 3.0:
                                        # logger.info(f"🐌 Slow: {node.config['server']} (~{int(current_speed)} Mbps) - Skipped")
                                        raise Exception("Too slow")
                            
                            # Если дошли до конца (скачали 15 МБ), считаем итоговую скорость
                            duration = time.perf_counter() - t_start
                            if duration < 0.001: duration = 0.001
                            
                            speed_mbps = (total_bytes * 8 / duration) / 1_000_000
                            node.speed_mbps = round(speed_mbps, 1)
                            
                            # Логируем только хорошие
                            if node.speed_mbps >= CONFIG["MIN_SPEED_MBPS"]:
                                logger.info(f"🚀 {node.config['server']} | {node.country_code} | {node.speed_mbps} Mbps")
                                return node

            except Exception:
                pass
            finally:
                proc.terminate()
                try: proc.wait(timeout=2)
                except: proc.kill()
                if os.path.exists(cfg_path): os.remove(cfg_path)
            
            return None

    async def run(self):
        logger.info("🔰 ЗАПУСК SMART-BOT V5.2...")
        
        all_nodes = await self.parse_links()
        logger.info(f"🔎 Уникальных узлов: {len(all_nodes)}")

        logger.info("📡 TCP Check (Отсев мертвых)...")
        tcp_res = await asyncio.gather(*[self.tcp_check(n) for n in all_nodes])
        candidates = [n for n, ok in zip(all_nodes, tcp_res) if ok]
        logger.info(f"📉 Кандидатов на SpeedTest: {len(candidates)}")

        if candidates:
            logger.info("🏎️ Smart Speed Test (Target: 15MB)...")
            sem = asyncio.Semaphore(CONFIG["THREADS"])
            results = await asyncio.gather(*[self.run_pipeline(n, sem) for n in candidates])
            
            alive = [r for r in results if r and r.speed_mbps >= CONFIG["MIN_SPEED_MBPS"]]
            alive.sort(key=lambda x: x.speed_mbps, reverse=True)

            final_list = [
                Utils.create_header(f"ℹ️ {CONFIG['SUB_TITLE']}"),
                Utils.create_header(f"⚡ High Speed Only (10+ Mbps)"),
                Utils.create_header(f"🔄 Updated: {datetime.datetime.now().strftime('%d.%m %H:%M')}")
            ]

            for i, n in enumerate(alive, 1):
                flag = chr(ord(n.country_code[0]) + 127397) + chr(ord(n.country_code[1]) + 127397)
                sni = n.config['sni'] or n.config['server']
                # Формат: 01 🇺🇸 US | google.com | 🚀 85.4 Mbps
                display_name = f"{i:02d} {flag} {n.country_code} | {sni} | 🚀 {n.speed_mbps} Mbps"
                
                p = urllib.parse.urlparse(n.raw_uri)
                final_list.append(p._replace(fragment=urllib.parse.quote(display_name)).geturl())

            with open(CONFIG["OUTPUT_FILE"], "w", encoding="utf-8") as f:
                f.write(Utils.encode_b64("\n".join(final_list)))

            logger.info(f"💾 Сохранено {len(alive)} элитных узлов.")
            if alive:
                logger.info(f"🏆 MAX Скорость: {alive[0].speed_mbps} Mbps")

if __name__ == "__main__":
    if sys.platform == 'win32': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(SmartTesterBot().run())
