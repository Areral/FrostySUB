import os
import json
import glob
import datetime
import asyncio
import aiohttp
from loguru import logger
from core.settings import CONFIG

async def send_telegram_report(stats: dict):
    logger.info("► [ТЕЛЕМЕТРИЯ]: Инициализация отправки отчета в Telegram")
    if not CONFIG.TG_BOT_TOKEN or not CONFIG.TG_CHAT_ID: 
        logger.warning("► [ТЕЛЕМЕТРИЯ]: TG_BOT_TOKEN или TG_CHAT_ID не заданы. Пропуск.")
        return
        
    public_url = CONFIG.app.get("public_url", "")
    dead_text = f"\n\n🗑️ <b>Dead Sources:</b> {len(stats['dead_sources'])}" if stats['dead_sources'] else ""

    msg = (
        f"🦇 <b>Scarlet Devil | Matrix Report</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>Собрано (Total):</b> <code>{stats['parsed']}</code>\n"
        f"🛡️ <b>Убито L4 фильтром:</b> <code>{stats['l4_dropped']}</code>\n"
        f"🔋 <b>Живых (Unique):</b> <code>{stats['unique_alive']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👻 <b>Nightbird (БС):</b> <code>{stats['bs_count']}</code>\n"
        f"☄️ <b>Vampire Dash (ЧС):</b> <code>{stats['unique_alive'] - stats['bs_count']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Max Speed:</b> <code>{stats['top_speed']:.1f} Mbps</code>\n\n"
        f"⚙️ <b>Matrix Performance:</b>\n"
    )
    
    for shard_idx, dur in sorted(stats['durations'].items()):
        msg += f"   └ Drone {shard_idx}: <code>{dur:.1f}s</code>\n"
        
    msg += f"{dead_text}\n━━━━━━━━━━━━━━━━━━\n🩸 <a href='{public_url}'>Mansion Status</a>"

    payload = {
        "chat_id": CONFIG.TG_CHAT_ID, 
        "text": msg, 
        "parse_mode": "HTML", 
        "disable_web_page_preview": True
    }
    
    target_topic = 7
    if CONFIG.TG_TOPIC_ID:
        try:
            target_topic = int(CONFIG.TG_TOPIC_ID)
        except ValueError:
            target_topic = 7

    payload["message_thread_id"] = target_topic
            
    url = f"https://api.telegram.org/bot{CONFIG.TG_BOT_TOKEN}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        try: 
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                logger.info("✔ [ТЕЛЕМЕТРИЯ]: Telegram-отчет успешно доставлен")
        except Exception as e:
            logger.error(f"✘ [ТЕЛЕМЕТРИЯ]: Сбой отправки в Telegram: {e}")

def build_html(total_alive: int, top_speed: float):
    logger.info("► [ВЕБ-ИНТЕРФЕЙС]: Генерация Dashboard (index.html)")
    template_path = "config/web/template.html"
    css_path = "config/web/style.css"
    js_path = "config/web/main.js"

    if not os.path.exists(template_path): 
        return

    try:
        with open(template_path, "r", encoding="utf-8") as f:
            tpl = f.read()
        
        css = ""
        if os.path.exists(css_path):
            with open(css_path, "r", encoding="utf-8") as f:
                css = f.read()

        js = ""
        if os.path.exists(js_path):
            with open(js_path, "r", encoding="utf-8") as f:
                js = f.read()

        now = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)
        public_url = CONFIG.app.get("public_url", "")

        html_out = (
            tpl.replace("{{INJECT_CSS}}", css)
               .replace("{{INJECT_JS}}", js)
               .replace("{{UPDATE_TIME}}", now.strftime("%d.%m %H:%M"))
               .replace("{{PROXY_COUNT}}", str(total_alive))
               .replace("{{MAX_SPEED}}", str(int(top_speed)))
               .replace("{{SUB_LINK}}", f"{public_url}/sub")
        )
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_out)
            
        logger.info("✔ [ВЕБ-ИНТЕРФЕЙС]: Dashboard успешно скомпилирован")
    except Exception as e:
        logger.error(f"✘ [ВЕБ-ИНТЕРФЕЙС]: Ошибка при генерации HTML: {e}")

def merge_subscription_files(pattern: str, output_file: str, title: str):
    logger.info(f"► [СКЛЕЙКА]: Объединение артефактов (Target: {output_file})")
    files = glob.glob(pattern)
    unique_map = {}
    
    for f_path in files:
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    base_uri = line.split('#')[0]
                    if base_uri not in unique_map:
                        unique_map[base_uri] = line
        except Exception:
            pass

    sorted_links = list(unique_map.values())
    sorted_links.sort()

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"#profile-title: {title}\n")
        f.write("#profile-update-interval: 6\n")
        for link in sorted_links:
            f.write(f"{link}\n")
            
    logger.info(f"✔ [СКЛЕЙКА]: Файл {output_file} собран (Узлов: {len(sorted_links)})")
    return len(sorted_links)

def main():
    logger.info("==================================================================")
    logger.info("          🩸 ЗАПУСК SCARLET NEXUS (СБОРКА И ДЕДУПЛИКАЦИЯ)         ")
    logger.info("==================================================================")
    
    stats = {
        "parsed": 0,
        "l4_dropped": 0,
        "top_speed": 0.0,
        "dead_sources": set(),
        "durations": {},
        "unique_alive": 0,
        "bs_count": 0
    }
    
    stat_files = glob.glob("shards_temp/shard-data-*/stats_*.json")
    logger.info(f"► [NEXUS]: Найдено файлов статистики от дронов: {len(stat_files)}")
    
    for f_path in stat_files:
        try:
            shard_idx = f_path.split("stats_")[-1].replace(".json", "")
            
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                stats["parsed"] += data.get("parsed", 0)
                stats["l4_dropped"] += data.get("l4_dropped", 0)
                
                if data.get("top_speed", 0) > stats["top_speed"]:
                    stats["top_speed"] = data.get("top_speed", 0)
                    
                stats["durations"][shard_idx] = data.get("duration", 0.0)
                
                for src in data.get("dead_sources", []):
                    stats["dead_sources"].add(src)
        except Exception:
            pass

    stats["unique_alive"] = merge_subscription_files("shards_temp/shard-data-*/sub_all_*.txt", "sub_all.txt", "Scarlet Devil | Gungnir (MIX)")
    stats["bs_count"] = merge_subscription_files("shards_temp/shard-data-*/sub_bs_*.txt", "sub_bs.txt", "Scarlet Devil | Nightbird (БС)")
    merge_subscription_files("shards_temp/shard-data-*/sub_chs_*.txt", "sub_chs.txt", "Scarlet Devil | Vampire Dash (ЧС)")
    
    build_html(stats["unique_alive"], stats["top_speed"])
    asyncio.run(send_telegram_report(stats))
    
    logger.info("==================================================================")
    logger.info("          🩸 NEXUS ЗАВЕРШИЛ РАБОТУ. ДАННЫЕ ОПУБЛИКОВАНЫ.          ")
    logger.info("==================================================================")

if __name__ == "__main__":
    main()
