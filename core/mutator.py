from typing import List
from loguru import logger
from core.models import ProxyNode

#Движок самолечения конфигураций
#Создает синтетические копии прокси с исправленными параметрами для повышения выживаемости
class NodeMutator:

    @staticmethod
    def mutate(node: ProxyNode) -> List[ProxyNode]:
        mutations =[node]
        c = node.config

        if c.alpn and "h2" in c.alpn:
            m1 = node.model_copy(deep=True)
            m1.config.alpn = "http/1.1"
            m1.config.raw_meta["mutated"] = "alpn_downgrade"
            mutations.append(m1)

        if c.fp and c.fp not in ("chrome", "firefox", "safari", "ios"):
            m2 = node.model_copy(deep=True)
            m2.config.fp = "chrome"
            m2.config.raw_meta["mutated"] = "fp_stabilize"
            mutations.append(m2)

        if len(mutations) > 1:
            logger.debug(f"Mutator: Создано {len(mutations)-1} клонов-мутантов для {node.machine_id}")

        return mutations
