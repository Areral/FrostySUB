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
def msk_now(): return datetime.datetime.utcnow() + datetime.timedelta(hours=3)
def msk_converter(*args): return msk_now().timetuple()
logging.Formatter.converter = msk_converter
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("SunnyBot")

# ===========================
# ⚙️ КОНФИГУРАЦИЯ (v6.6 Debug Edition)
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_SUB": "subscription.txt",
    "TEMPLATE_FILE": "config/template.html",
    "OUTPUT_INDEX": "index.html",
    "PUBLIC_URL": "https://sunny-areral.vercel.app/", 
    
    "THREADS": 10, 
    "TCP_TIMEOUT": 3, 
    "PIPELINE_TIMEOUT": 35,   # Увеличили таймаут для стабильности
    
    "SPEED_TEST_URL": "http://speed.cloudflare.com/__down?bytes=8000000",
    "MIN_SPEED_MBPS": 2.5,   
    "EARLY_EXIT_SPEED": 8.0, 
    "CHAMPION_TEST_URL": "http://speed.cloudflare.com/__down?bytes=50000000",
    
    "CHECK_URLS": ["https://www.google.com/generate_204", "https://www.cloudflare.com/cdn-cgi/trace"],
    "GEO_API": "https://ipwho.is/", 
    "USER_AGENT": "v2rayNG/1.8.5"
}

class Utils:
    @staticmethod
    def decode_b64(s: str) -> str:
        s = s.strip()
        if not s: return ""
        try: return base64.b64decode(s + '=' * (-len(s) % 4)).decode('utf-8', 'ignore')
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

class WebGenerator:
    @staticmethod
    def build(count: int, top_speed: float):
        try:
            with open(CONFIG["TEMPLATE_FILE"], "r", encoding="utf-8") as f: template = f.read()
            html = template.replace("{{UPDATE_TIME}}", msk_now().strftime('%d.%m %H:%M'))
            html = html.replace("{{PROXY_COUNT}}", str(count))
            html = html.replace("{{MAX_SPEED}}", str(int(top_speed)))
            html = html.replace("{{SUB_LINK}}", CONFIG["PUBLIC_URL"])
            with open(CONFIG["OUTPUT_INDEX"], "w", encoding="utf-8") as f: f.write(html)
            logger.info("🌐 Сайт обновлен")
        except Exception as e: logger.error(f"⚠️ Ошибка сайта: {e}")

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
            "log": {"level": "fatal"}, "dns": {"servers": [{"tag": "google", "address": "8.8.8.8"}]},
            "inbounds": [{"type": "socks", "tag": "socks-in", "listen": "127.0.0.1", "listen_port": local_port, "sniff": True}],
            "outbounds": [outbound]
        }

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

    async def tcp_check(self, node: ProxyNode, sem: asyncio.Semaphore) -> bool:
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

    async def pipeline(self, node: ProxyNode, sem: asyncio.Semaphore) -> Optional[ProxyNode]:
        async with sem:
            port = random.randint(20000, 55000)
            cfg = f"t_{port}.json"
            with open(cfg, 'w') as f: json.dump(SingBoxManager.generate_config(node, port), f)
            proc = subprocess.Popen(["sing-box", "run", "-c", cfg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(2.5)
            
            try:
                connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
                async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=CONFIG["PIPELINE_TIMEOUT"])) as session:
                    # 1. Anti-Ban (Google/Cloudflare)
                    try:
                        async with session.get(random.choice(CONFIG["CHECK_URLS"]), timeout=6) as resp:
                            if resp.status >= 400: 
                                logger.debug(f"❌ {node.config['server']} - Banned or No Access (Status: {resp.status})")
                                raise Exception()
                    except: 
                        return None # Узел не видит интернет

                    # 2. GeoIP
                    try:
                        async with session.get(CONFIG["GEO_API"], timeout=6) as resp:
                            data = await resp.json()
                            if data.get('success'): 
                                node.country_code = data.get('country_code', 'UN')
                            else: raise Exception()
                    except:
                        logger.debug(f"❌ {node.config['server']} - GeoIP Fail")
                        return None

                    # 3. Speed Test
                    t_start = time.perf_counter()
                    try:
                        async with session.get(CONFIG["SPEED_TEST_URL"]) as resp:
                            total = 0
                            async for chunk in resp.content.iter_chunked(65536):
                                total += len(chunk)
                                if total > 1500000:
                                    cur = (total*8/(time.perf_counter()-t_start))/1000000
                                    if cur >= CONFIG["EARLY_EXIT_SPEED"]:
                                        node.speed_mbps = round(cur, 1)
                                        logger.info(f"✨ FAST: {node.config['server']} | {node.country_code} | {node.speed_mbps} Mbps")
                                        return node
                            
                            dur = time.perf_counter() - t_start
                            node.speed_mbps = round((total*8/(dur or 0.1))/1000000, 1)
                            if node.speed_mbps >= CONFIG["MIN_SPEED_MBPS"]:
                                logger.info(f"✅ OK: {node.config['server']} | {node.country_code} | {node.speed_mbps} Mbps")
                                return node
                            else:
                                logger.debug(f"🐌 {node.config['server']} - Too Slow ({node.speed_mbps} Mbps)")
                    except:
                        logger.debug(f"❌ {node.config['server']} - Speed Test Timeout/Error")
                        return None
            except: pass
            finally:
                proc.terminate()
                if os.path.exists(cfg): os.remove(cfg)
            return None

    async def champion(self, node: ProxyNode) -> float:
        logger.info(f"🏆 Чемпион: {node.config['server']}...")
        port = random.randint(55001, 60000)
        cfg = f"ch_{port}.json"
        with open(cfg, 'w') as f: json.dump(SingBoxManager.generate_config(node, port), f)
        proc = subprocess.Popen(["sing-box", "run", "-c", cfg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        await asyncio.sleep(3.0)
        spd = node.speed_mbps
        try:
            connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
            async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=60)) as session:
                t0 = time.perf_counter()
                async with session.get(CONFIG["CHAMPION_TEST_URL"]) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        spd = round(((len(content)*8)/(time.perf_counter()-t0))/1000000, 1)
                        logger.info(f"🚀 MAX: {spd} Mbps")
        except: pass
        finally:
            proc.terminate()
            if os.path.exists(cfg): os.remove(cfg)
        return spd

    async def run(self):
        logger.info(f"🚀 DEBUG MODE START (MSK: {msk_now().strftime('%H:%M:%S')})")
        
        # Step 0: Deduplication
        nodes = await self.get_nodes()
        logger.info(f"🔎 Step 0: Найдено уникальных: {len(nodes)}")

        # Step 1: TCP Check
        tcp_sem = asyncio.Semaphore(50)
        tcp_res = await asyncio.gather(*[self.tcp_check(n, tcp_sem) for n in nodes])
        candidates = [n for n, ok in zip(nodes, tcp_res) if ok]
        logger.info(f"📡 Step 1: Прошли TCP тест (порт открыт): {len(candidates)}")

        # Step 2-4: Deep Check
        alive = []
        if candidates:
            logger.info(f"🏎️ Step 2-4: Запуск глубокой проверки через Sing-box...")
            res = await asyncio.gather(*[self.pipeline(n, asyncio.Semaphore(CONFIG["THREADS"])) for n in candidates])
            alive = [r for r in res if r]
            alive.sort(key=lambda x: x.speed_mbps, reverse=True)
            logger.info(f"🏁 Итог глубокой проверки: {len(alive)} узлов")
            
            top_spd = 0.0
            if alive: top_spd = await self.champion(alive[0])
            
            # Step 5: Save Sub
            final = []
            for i, n in enumerate(alive, 1):
                flag = chr(ord(n.country_code[0])+127397) + chr(ord(n.country_code[1])+127397)
                nm = f"{i:02d} {flag} {n.country_code} | {n.config['sni'] or n.config['server']} | {n.protocol}"
                p = urllib.parse.urlparse(n.raw_uri)
                final.append(p._replace(fragment=urllib.parse.quote(nm)).geturl())
            
            with open(CONFIG["OUTPUT_SUB"], "w", encoding="utf-8") as f: f.write(Utils.encode_b64("\n".join(final)))
            
            # Step 6: Build Web
            WebGenerator.build(len(alive), top_spd)
            logger.info("💾 ГОТОВО")

if __name__ == "__main__":
    asyncio.run(SunnyBot().run())
