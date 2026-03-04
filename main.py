import asyncio
import time
import sys
import os
from loguru import logger

from core.settings import CONFIG
from core.parser import LinkParser
from core.engine import Inspector
from core.exporter import Exporter
from core.validator import RKNValidator

async def main():
    start_time = time.perf_counter()
    logger.info("⏣ Запуск Scarlet Devil Network v14 (Matrix Sharding Edition)")

    shard_index = int(os.environ.get("SHARD_INDEX", "0"))
    shard_count = int(os.environ.get("SHARD_COUNT", "1"))
    logger.info(f"🦇 Инициализация дрона {shard_index + 1} из {shard_count}")

    try:
        await RKNValidator.load_lists()

        parser = LinkParser()
        nodes = await parser.fetch_and_parse()

        if not nodes:
            logger.error("✘ Нет валидных ссылок. Завершение.")
            sys.exit(0)
            
        if shard_count > 1:
            total_nodes = len(nodes)
            chunk_size = (total_nodes + shard_count - 1) // shard_count
            start_idx = shard_index * chunk_size
            end_idx = start_idx + chunk_size
            nodes = nodes[start_idx:end_idx]
            logger.info(f"✂️ Дрон взял на себя {len(nodes)} узлов (с {start_idx} по {min(end_idx, total_nodes)}).")

        inspector = Inspector()
        logger.info("⚙ Пакетная проверка (Batch Engine)...")

        alive_nodes = await inspector.process_all(nodes)
        
        for node in alive_nodes:
            if node.source_url in parser.metrics:
                parser.metrics[node.source_url]["alive"] = parser.metrics[node.source_url].get("alive", 0) + 1

        dead_sources =[url for url, m in parser.metrics.items() if m.get("parsed", 0) > 0 and m.get("alive", 0) == 0]
        
        if dead_sources:
            logger.warning(f"⚠ Обнаружено {len(dead_sources)} источников с нулевым выходом. Запуск Retry Phase...")
            retry_nodes =[n for n in nodes if n.source_url in dead_sources]
            retry_alive = await inspector.process_all(retry_nodes)
            
            if retry_alive:
                logger.success(f"⚑ Retry Phase спасла {len(retry_alive)} узлов!")
                alive_nodes.extend(retry_alive)
                
                for node in retry_alive:
                    if node.source_url in parser.metrics:
                        parser.metrics[node.source_url]["alive"] = parser.metrics[node.source_url].get("alive", 0) + 1
                        
            dead_sources =[url for url, m in parser.metrics.items() if m.get("parsed", 0) > 0 and m.get("alive", 0) == 0]
        
        unique_alive = {}
        for n in alive_nodes:
            unique_alive[n.strict_id] = n
        alive_nodes = list(unique_alive.values())

        if dead_sources:
            logger.warning("Источники, окончательно выдавшие 0 рабочих прокси (после Retry):")
            for src in dead_sources:
                safe_src = src.replace("://", ":\u200b//").replace(".", ".\u200b")
                logger.warning(f"   - {safe_src}")

        logger.success(f"⚑ Проверка завершена. Живых: {len(alive_nodes)}/{len(nodes)}")

        Exporter.save_files(
            alive_nodes, 
            shard_index=shard_index if shard_count > 1 else -1,
            parsed_count=len(nodes),
            dead_sources=dead_sources
        )

        duration = time.perf_counter() - start_time
        logger.info(f"✔ Завершено за {duration:.2f} сек. Дрон отключен.")
        
        sys.exit(0)
        
    except Exception as e:
        logger.exception(f"Критический сбой в main(): {e}")
        sys.exit(1)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    else:
        try:
            import uvloop
            uvloop.install()
        except ImportError:
            pass

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Остановка пользователем")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"FATAL ERROR ВНЕ EVENT LOOP: {e}")
        sys.exit(1)
