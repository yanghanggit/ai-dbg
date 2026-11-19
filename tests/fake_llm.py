"""测试用的 LLM 替身：描述刷新不发真实请求，也不依赖网络。

``conftest`` 的 autouse fixture 默认挂上它；需要检查「问了什么」的用例自己
monkeypatch 覆盖即可。
"""

from typing import List, Sequence

from ai_srpg.llm import ChatCompletionRequest, ChatCompletionResult
from ai_srpg.models import AIMessage

#: 固定回复的前缀；断言「确实刷新过」时按它匹配
FAKE_DESCRIPTION_PREFIX = "（测试描述）"


###############################################################################
def fake_completion(
    requests: Sequence[ChatCompletionRequest],
) -> List[ChatCompletionResult]:
    """按请求顺序造出成功结果：内容 = 前缀 + 请求标签。"""
    return [
        ChatCompletionResult(
            request=request,
            ai_message=AIMessage(content=f"{FAKE_DESCRIPTION_PREFIX}{request.label}"),
        )
        for request in requests
    ]


###############################################################################
def failed_completion(
    requests: Sequence[ChatCompletionRequest],
) -> List[ChatCompletionResult]:
    """按请求顺序造出失败结果：调用方必须保持底稿不变。"""
    from ai_srpg.llm.errors import ChatError

    return [
        ChatCompletionResult(
            request=request, error=ChatError(request.label, "boom", kind="api")
        )
        for request in requests
    ]


###############################################################################
__all__ = ["FAKE_DESCRIPTION_PREFIX", "failed_completion", "fake_completion"]
