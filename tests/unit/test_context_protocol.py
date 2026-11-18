"""ContextProtocol 的契约测试：Context 必须提供协议声明的全部能力。"""

from ai_srpg.entitas.context import Context
from ai_srpg.entitas.context_protocol import ContextProtocol


def test_context_protocol_is_a_protocol() -> None:
    assert getattr(ContextProtocol, "_is_protocol", False) is True


def test_context_satisfies_protocol_surface() -> None:
    context = Context()

    for name in ContextProtocol.__protocol_attrs__:  # type: ignore[attr-defined]
        assert callable(getattr(context, name, None)), f"Context 缺少协议方法 {name}"
