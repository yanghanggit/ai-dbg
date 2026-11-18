"""实体身份分配。"""

from typing import final


###############################################################################################################################################
@final
class EntityNaming:
    """为实体分配递增的创建顺序（写入 ``IdentityComponent.creation_order``）。

    只负责「下一个序号是多少」，不关心实体本身；实体名称由 ECS 名称索引维护。
    """

    def __init__(self, counter: int = 0) -> None:
        self._counter: int = counter

    ###########################################################################
    @property
    def counter(self) -> int:
        """已经分配到的最大创建顺序。"""
        return self._counter

    ###########################################################################
    def next_creation_order(self) -> int:
        """分配下一个创建顺序，从 1 开始单调递增。"""
        self._counter += 1
        return self._counter


###############################################################################
__all__ = ["EntityNaming"]
