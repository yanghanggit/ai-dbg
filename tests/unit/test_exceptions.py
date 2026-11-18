"""ECS 异常类型与 StopPipeline 的语义测试。"""

from ai_srpg.entitas import StopPipeline
from ai_srpg.entitas.exceptions import (
    AlreadyAddedComponent,
    EntitasException,
    EntityNotEnabled,
    GroupSingleEntity,
    MissingComponent,
    MissingEntity,
)


def test_entitas_exception_appends_hint() -> None:
    error = EntitasException("boom", "try this")

    assert str(error) == "boom\ntry this"


def test_entitas_exception_without_hint_keeps_message() -> None:
    assert str(EntitasException("boom", "")) == "boom"


def test_ordinary_exceptions_are_exception_subclasses() -> None:
    for error_type in (
        AlreadyAddedComponent,
        EntityNotEnabled,
        GroupSingleEntity,
        MissingComponent,
        MissingEntity,
    ):
        assert issubclass(error_type, Exception)


def test_stop_pipeline_carries_reason() -> None:
    error = StopPipeline("campaign finished")

    assert error.reason == "campaign finished"
    assert str(error) == "campaign finished"


def test_stop_pipeline_default_reason_is_empty() -> None:
    assert StopPipeline().reason == ""


def test_stop_pipeline_is_not_an_exception() -> None:
    """控制流信号必须避开 ``except Exception``。"""
    assert issubclass(StopPipeline, BaseException)
    assert not issubclass(StopPipeline, Exception)
