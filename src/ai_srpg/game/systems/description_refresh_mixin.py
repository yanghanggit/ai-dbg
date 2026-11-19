"""用 LLM 重写「当前描述」的 mixin：问模型、写回记忆。

只在 system 内部有意义，因此不做成模块级函数：全局函数等于没有边界。
"""

from typing import Dict, List, Sequence

from loguru import logger

from ...deepseek import batch_complete
from ...entitas import Entity
from ...llm import ChatCompletionRequest
from ...models import ChatMessage, HumanMessage
from ..memory import add_human_message, get_agent_memory
from .system_mixin import SystemMixin


###############################################################################
class DescriptionRefreshMixin(SystemMixin):
    """给描述类 system 提供「问模型 / 写记忆」两个动作。"""

    ###########################################################################
    async def complete_descriptions(
        self,
        entities: Sequence[Entity],
        *,
        label: str,
        instruction: str,
        include_events: bool = True,
    ) -> Dict[str, str]:
        """返回「实体名 → 文本」；失败的实体不出现。

        ``include_events=False`` 滤掉领域事件广播——它们天生是「谁在场、谁做了什么」。
        """
        if not entities:
            return {}

        requests = [
            ChatCompletionRequest(
                label=f"{label}:{entity.name}",
                input_message=instruction,
                messages=self._history_for(entity, include_events=include_events),
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
    def _history_for(
        self, entity: Entity, *, include_events: bool
    ) -> List[ChatMessage]:
        """取这个实体要发给模型的历史，事件广播按需滤掉。"""
        messages = get_agent_memory(self._game, entity).messages
        if include_events:
            return list(messages)
        return [
            message
            for message in messages
            if getattr(message, "agent_event", None) is None
        ]

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
        """把当前描述与底稿一起写回记忆，避免两者在后续推理里打架。"""
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
