"""系统改变状态的入口基类。

凡是会改动记忆或 ECS 状态的行动，都必须在 pipeline 里显式出现：系统只能通过继承
本类的 mixin 方法动手，于是「谁在哪个系统里改了状态」在 systems 执行链上直接可读，
不需要额外的注释解释。
"""

from typing import Final

from ..context import SRPGGame


class SystemMixin:
    """系统的共用状态：一个成员，当前这一局的 ``game``。"""

    def __init__(self, game: SRPGGame) -> None:
        self._game: Final[SRPGGame] = game


###############################################################################
__all__ = ["SystemMixin"]
