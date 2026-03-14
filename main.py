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
    logger.info("==================================================================")
    logger.info("                  SCARLET DEVIL NETWORK CORE v16                  ")
    logger.info("==================================================================")

    shard_index = int(os.environ.get("SHARD_INDEX", "0"))
    shard_count = int(os.environ.get("SHARD_COUNT", "1"))
    logger.info(f"🦇 Активация Матричного Дрона [{shard_index + 1} / {shard_count}]")
    logger.info("==================================================================")

    try:
        await RKNValidator.load_lists()

        parser = LinkParser()
        nodes = await parser.fetch_and_parse()

        if not nodes:
            logger.error("✘ Нет валидных ссылок после парсинга. Завершение работы Дрона.")
            return
            
        if shard_count > 1:
            total_nodes = len(nodes)
            chunk_size = (total_nodes + shard_count - 1) // shard_count
            start_idx = shard_index * chunk_size
            end_idx = start_idx + chunk_size
            nodes = nodes[start_idx:end_idx]
            logger.info(f"⛨ Зона ответственности передана Дрону: {len(nodes)} узлов")
            
        inspector = Inspector()
        alive_nodes = await inspector.process_all(nodes)
        l4_dropped = inspector.l4_dropped
        
        logger.info("► [АГРЕГАЦИЯ]: Подсчет метрик и источников...")
        for node in alive_nodes:
            if node.source_url in parser.metrics:
                parser.metrics[node.source_url]["alive"] = parser.metrics[node.source_url].get("alive", 0) + 1

        dead_sources =[url for url, m in parser.metrics.items() if m.get("parsed", 0) > 0 and m.get("alive", 0) == 0]
        
        unique_alive = {}
        for n in alive_nodes:
            unique_alive[n.strict_id] = n
        alive_nodes = list(unique_alive.values())
        logger.info(f"✔ [ДЕДУПЛИКАЦИЯ]: Выжило уникальных узлов: {len(alive_nodes)}")

        duration = time.perf_counter() - start_time
        
        Exporter.save_files(
            alive_nodes, 
            shard_index=shard_index if shard_count > 1 else -1,
            parsed_count=len(nodes),
            dead_sources=dead_sources,
            duration=duration,
            l4_dropped=l4_dropped
        )
        
        logger.info("==================================================================")
        logger.info(f"✦ Дрон [{shard_index + 1}] успешно завершил миссию за {duration:.1f} сек. ✦")
        logger.info("==================================================================")

    except Exception as e:
        logger.exception(f"✘ КРИТИЧЕСКИЙ СБОЙ В ЯДРЕ ДРОНА: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if sys.platform != "win32":
        try:
            import uvloop
            uvloop.install()
        except ImportError:
            pass

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(1)
