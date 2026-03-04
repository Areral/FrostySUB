import os
import json
import glob
import datetime
import asyncio
import aiohttp
from loguru import logger
from core.settings import CONFIG

async def send_telegram_report(total_parsed: int, total_alive: int, bs_count: int, top_speed: float, dead_sources: set):
    if not CONFIG.TG_BOT_TOKEN or not CONFIG.TG_CHAT_ID: 
        logger.warning("Telegram токены не настроены, отчет пропущен.")
        return
        
    public_url = CONFIG.app.get("public_url", "")
    
    dead_text = ""
    if dead_sources:
        dead_text = f"\n\n🗑️ <b>Dead Sources:</b> {len(dead_sources)}"

    msg = (
        f"🦇 <b>Scarlet Devil | Matrix Report</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📡 <b>Собрано (Total):</b> <code>{total_parsed}</code>\n"
        f"🔋 <b>Живых (Alive):</b> <code>{total_alive}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <b>Phantom Route (БС):</b> <code>{bs_count}</code>\n"
        f"☄️ <b>Dash Route (ЧС):</b> <code>{total_alive - bs_count}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Max Speed:</b> <code>{top_speed:.1f} Mbps</code>\n"
        f"⏱️ <b>Cycle:</b> <code>{duration:.1f}s</code>"
        f"{dead_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🩸 <a href='{public_url}'>Mansion Status</a>"
    )

    payload = {"chat_id": CONFIG.TG_CHAT_ID, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True}
    if CONFIG.TG_TOPIC_ID: payload["message_thread_id"] = CONFIG.TG_TOPIC_ID
    url = f"https://api.telegram.org/bot{CONFIG.TG_BOT_TOKEN}/sendMessage"
    
    async with aiohttp.ClientSession() as session:
        try: 
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                logger.success("Telegram Matrix Report отправлен!")
        except Exception as e:
            logger.error(f"Telegram report failed: {e}")

def build_html(total_alive: int, top_speed: float):
    template_path = "config/web/template.html"
    css_path = "config/web/style.css"
    js_path = "config/web/main.js"

    if not os.path.exists(template_path): 
        logger.error("Шаблон не найден!")
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

        now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
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
        logger.success("HTML успешно собран!")
    except Exception as e:
        logger.error(f"HTML build error: {e}")

def main():
    logger.info("🧬 Запуск Matrix Merge Protocol...")
    
    total_parsed = 0
    total_alive = 0
    top_speed = 0.0
    dead_sources = set()
    
    stat_files = glob.glob("shards_temp/shard-data-*/stats_*.json")
    for f_path in stat_files:
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                total_parsed += data.get("parsed", 0)
                total_alive += data.get("alive", 0)
                if data.get("top_speed", 0) > top_speed:
                    top_speed = data.get("top_speed", 0)
                for src in data.get("dead_sources", []):
                    dead_sources.add(src)
        except Exception as e:
            logger.error(f"Ошибка чтения статы {f_path}: {e}")

    bs_count = 0
    try:
        with open("sub_bs.txt", "r", encoding="utf-8") as f:
            bs_count = sum(1 for line in f if "://" in line)
    except Exception: pass

    logger.info(f"📊 ИТОГИ МАТРИЦЫ: Parsed: {total_parsed} | Alive: {total_alive} | Max Speed: {top_speed} Mbps")
    
    build_html(total_alive, top_speed)
    asyncio.run(send_telegram_report(total_parsed, total_alive, bs_count, top_speed, dead_sources))

if __name__ == "__main__":
    main()
