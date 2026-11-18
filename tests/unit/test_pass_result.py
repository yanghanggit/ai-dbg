"""PassResult 调度结果的纯数据测试。"""

from dataclasses import FrozenInstanceError

import pytest

from ai_srpg.entitas import PassResult


def test_default_result_is_empty_and_completed() -> None:
    result = PassResult()

    assert result.ran == ()
    assert result.skipped == ()
    assert result.aborted_by is None
    assert result.completed


def test_result_with_skipped_systems_is_not_completed() -> None:
    result = PassResult(ran=("A",), skipped=("B", "C"), aborted_by="B")

    assert result.completed is False
    assert result.aborted_by == "B"
    assert result.skipped == ("B", "C")


def test_result_is_frozen() -> None:
    result = PassResult(ran=("A",))

    with pytest.raises(FrozenInstanceError):
        result.ran = ("B",)  # type: ignore[misc]


def test_results_compare_by_value() -> None:
    assert PassResult(ran=("A",)) == PassResult(ran=("A",))
    assert PassResult(ran=("A",)) != PassResult(ran=("B",))
