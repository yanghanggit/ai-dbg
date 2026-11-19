"""用 LLM 重写「当前描述」的 mixin：问模型、写回记忆。

这两件事只在 system 内部有意义，所以挂在 mixin 上而不是模块级函数——能被任意代码
调用的全局函数等于没有边界。
"""

from typing import Dict, Sequence

from loguru import logger

from ...deepseek import batch_complete
from ...entitas import Entity
from ...llm import ChatCompletionRequest
from ...models import HumanMessage
from ..memory import add_human_message, get_agent_memory
from .system_mixin import SystemMixin


###############################################################################
class DescriptionRefreshMixin(SystemMixin):
    """用 LLM 重写「当前描述」的能力：问模型、写回记忆。

    这两件事只在 system 内部有意义，所以挂在 mixin 上而不是模块级函数——能被任意代码
    调用的全局函数等于没有边界。
    """

    ###########################################################################
    async def complete_descriptions(
        self,
        entities: Sequence[Entity],
        *,
        label: str,
        instruction: str,
    ) -> Dict[str, str]:
        """按实体记忆批量补全描述，返回「实体名 → 文本」；失败的实体不出现。"""
        if not entities:
            return {}

        requests = [
            ChatCompletionRequest(
                label=f"{label}:{entity.name}",
                input_message=instruction,
                messages=list(get_agent_memory(self._game, entity).messages),
            )
            for entity in entities
        ]
        results = await batch_complete(requests)

        texts: Dict[str, str] = {}
        for entity, result in zip(entities, results):
            if result.error is not None:
                logger.warning(
                    f"{label} 生成失败，保留底稿: {entity.name} / {result.error}"
                )
                continue
            text = result.content.strip()
            if text == "":
                logger.warning(f"{label} 生成结果为空，保留底稿: {entity.name}")
                continue
            texts[entity.name] = text
        return texts

    ###########################################################################
    def record_description_update(
        self,
        entity: Entity,
        *,
        description: str,
        current_label: str,
        base_label: str,
        base: str,
    ) -> None:
        """把这次更新写回实体记忆：名字、当前描述与底稿三者在同一条消息里对齐。"""
        add_human_message(
            self._game,
            entity,
            HumanMessage(
                content="\n".join(
                    [
                        f"你的{current_label}已更新为：{description}",
                        f"{base_label}（不随状态改变）：{base}",
                    ]
                )
            ),
        )


###############################################################################
__all__ = ["DescriptionRefreshMixin"]
