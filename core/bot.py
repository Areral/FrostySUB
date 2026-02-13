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
# ⚙️ КОНФИГУРАЦИЯ (v5.1 - High Speed)
# ===========================
CONFIG = {
    "SOURCES_FILE": "config/sources.txt",
    "OUTPUT_FILE": "subscription.txt",
    "SUB_TITLE": "_ _ _By Frosty XC_ _ _",
    
    # Настройки производительности
    "THREADS": 8,            # 8 потоков оптимально для SpeedTest в GitHub Actions
    "TCP_TIMEOUT": 3,        # Таймаут на открытие порта (быстрый отсев)
    "PIPELINE_TIMEOUT": 25,  # Общий таймаут на проверку одного прокси (Singbox + HTTP)
    
    # 🌍 Anti-Ban System
    # Перед GeoIP мы стучимся сюда. Если не открывает - прокси в мусорку.
    "CHECK_URLS": [
        "https://www.google.com/generate_204",
        "https://www.microsoft.com/",
        "https://www.github.com/",
        "https://www.cloudflare.com/",
        "https://www.amazon.com/"
    ],
    
    # 🚀 Speed Test (Точность для 100+ Mbps)
    # Скачиваем 5 MB (40 Mbits). Это золотая середина между точностью и скоростью работы.
    "SPEED_TEST_URL": "http://speed.cloudflare.com/__down?bytes=5000000",
    "MIN_SPEED_MBPS": 1.0,   # Отсеиваем все, что медленнее 1 Мбит/с
    
    "GEO_API": "https://ipwho.is/",
    "USER_AGENT": "v2rayNG/1.8.5 (Linux; Android 13; K)"
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("SpeedBot")

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
# 🛠 SING-BOX GENERATOR
# ===========================

class SingBoxManager:
    @staticmethod
    def generate_config(node: ProxyNode, local_port: int) -> dict:
        c = node.config
        
        # Настройка Outbound (Исходящее соединение)
        outbound = {
            "type": "vless",
            "tag": "proxy",
            "server": c['server'],
            "server_port": c['port'],
            "uuid": c['uuid'],
            "packet_encoding": "xudp" # Включаем поддержку UDP (Full Cone)
        }
        
        # Reality / TLS
        if c.get('security') == 'reality':
            outbound["tls"] = {
                "enabled": True, "server_name": c.get('sni'),
                "utls": {"enabled": True, "fingerprint": c.get('fp', 'chrome')},
                "reality": {
                    "enabled": True, "public_key": c.get('pbk'), "short_id": c.get('sid')
                }
            }
        
        if c.get('flow'): outbound["flow"] = c.get('flow')

        # Полный конфиг
        return {
            "log": {"level": "fatal"}, # Минимальный лог для скорости
            "dns": {"servers": [{"tag": "google", "address": "8.8.8.8"}]},
            "inbounds": [{
                "type": "socks",
                "tag": "socks-in",
                "listen": "127.0.0.1",
                "listen_port": local_port,
                "sniff": True, # Важно для Reality
                "sniff_override_destination": True
            }],
            "outbounds": [outbound]
        }

# ===========================
# 🧠 ЯДРО: ПРОВЕРКА И ТЕСТЫ
# ===========================

class SpeedTesterBot:
    async def parse_links(self) -> List[ProxyNode]:
        nodes = []
        seen = set() # Для дедупликации
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
                        if "://" not in content[:50]: content = Utils.decode_b64(content)
                        
                        count_new = 0
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
                                    count_new += 1
                        logger.info(f"📥 {url}: +{count_new} узлов")
                except Exception as e:
                    logger.warning(f"Ошибка загрузки {url}: {e}")
        return nodes

    async def tcp_check(self, node: ProxyNode) -> bool:
        """Быстрый пинг порта. Если порт закрыт - дальше не проверяем."""
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
        """Полный цикл проверки: Singbox -> AntiBan -> Geo -> SpeedTest"""
        async with sem:
            # Рандомный порт, чтобы процессы не мешали друг другу
            port = random.randint(20000, 50000)
            cfg_path = f"test_{port}.json"
            
            # Генерация конфига
            with open(cfg_path, 'w') as f:
                json.dump(SingBoxManager.generate_config(node, port), f)

            # Запуск ядра
            proc = subprocess.Popen(["sing-box", "run", "-c", cfg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Ждем инициализации Reality (Handshake занимает время)
            await asyncio.sleep(2.5)

            try:
                connector = ProxyConnector.from_url(f'socks5://127.0.0.1:{port}')
                # Увеличиваем таймаут сессии для скачивания файла
                async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=CONFIG["PIPELINE_TIMEOUT"])) as session:
                    
                    # 1. ANTI-BAN Check (Ротация URL)
                    # Проверяем, пускает ли прокси в "большой интернет"
                    check_url = random.choice(CONFIG["CHECK_URLS"])
                    async with session.get(check_url, timeout=5) as resp:
                        if resp.status not in [200, 204, 301, 302]:
                            raise Exception("Anti-Ban check failed")

                    # 2. GEOIP Check
                    async with session.get(CONFIG["GEO_API"], timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get('success'):
                                node.country_code = data.get('country_code', 'UN')
                            else:
                                raise Exception("GeoAPI Error")
                        else:
                            raise Exception("GeoAPI HTTP Error")

                    # 3. SPEED TEST (Замер скорости скачивания)
                    # Используем perf_counter для точности
                    start_dl = time.perf_counter()
                    async with session.get(CONFIG["SPEED_TEST_URL"]) as resp:
                        if resp.status == 200:
                            # Читаем байты (скачиваем файл в память)
                            content = await resp.read()
                            duration = time.perf_counter() - start_dl
                            
                            # Защита от деления на ноль при мгновенном скачивании
                            if duration < 0.001: duration = 0.001
                            
                            file_size_bits = len(content) * 8
                            speed_mbps = (file_size_bits / duration) / 1_000_000
                            
                            node.speed_mbps = round(speed_mbps, 1)
                            
                            logger.info(f"🚀 {node.config['server']} | {node.country_code} | {node.speed_mbps} Mbps")
                            return node

            except Exception:
                pass # Любая ошибка (таймаут, разрыв, бан) = провал теста
            finally:
                # Очистка ресурсов
                proc.terminate()
                try: proc.wait(timeout=2)
                except: proc.kill()
                if os.path.exists(cfg_path): os.remove(cfg_path)
            
            return None

    async def run(self):
        logger.info("🔰 ЗАПУСК SPEED-BOT V5.1...")
        
        # 1. Загрузка и Дедупликация
        all_nodes = await self.parse_links()
        logger.info(f"🔎 Уникальных узлов: {len(all_nodes)}")

        # 2. Быстрый TCP отсев
        logger.info("📡 TCP Check (Отсев мертвых портов)...")
        tcp_res = await asyncio.gather(*[self.tcp_check(n) for n in all_nodes])
        candidates = [n for n, ok in zip(all_nodes, tcp_res) if ok]
        logger.info(f"📉 Осталось кандидатов: {len(candidates)}")

        if not candidates:
            logger.error("Нет доступных узлов после TCP проверки!")
            return

        # 3. Глубокая проверка (Speed + Geo + AntiBan)
        logger.info("🏎️ Запуск Speed Test & Validation (может занять время)...")
        sem = asyncio.Semaphore(CONFIG["THREADS"])
        results = await asyncio.gather(*[self.run_pipeline(n, sem) for n in candidates])
        
        # Фильтруем: только живые и быстрее минимума
        alive = [r for r in results if r and r.speed_mbps >= CONFIG["MIN_SPEED_MBPS"]]
        
        # Сортировка: Самые быстрые вверху
        alive.sort(key=lambda x: x.speed_mbps, reverse=True)

        # 4. Сохранение результата
        final_list = [
            Utils.create_header(f"ℹ️ {CONFIG['SUB_TITLE']}"),
            Utils.create_header(f"🔄 Updated: {datetime.datetime.now().strftime('%d.%m %H:%M')}")
        ]

        for i, n in enumerate(alive, 1):
            flag = chr(ord(n.country_code[0]) + 127397) + chr(ord(n.country_code[1]) + 127397)
            sni = n.config['sni'] or n.config['server']
            
            # ФОРМАТ ВЫВОДА:
            # 01 🇩🇪 DE | google.com | 🚀 145.2 Mbps
            display_name = f"{i:02d} {flag} {n.country_code} | {sni} | 🚀 {n.speed_mbps} Mbps"
            
            p = urllib.parse.urlparse(n.raw_uri)
            final_list.append(p._replace(fragment=urllib.parse.quote(display_name)).geturl())

        # Запись в файл
        with open(CONFIG["OUTPUT_FILE"], "w", encoding="utf-8") as f:
            f.write(Utils.encode_b64("\n".join(final_list)))

        logger.info(f"💾 Успешно сохранено: {len(alive)} узлов.")
        if alive:
            logger.info(f"🏆 Топ скорость: {alive[0].speed_mbps} Mbps")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(SpeedTesterBot().run())
