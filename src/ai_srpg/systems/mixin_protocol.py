"""系统层 mixin 的核心骨架协议。"""

from typing import Protocol

from ..game.context import SRPGGame


###############################################################################################################################################
class SystemMixinProtocol(Protocol):
    """所有系统层 mixin 的意图标记与最小契约。

    mixin 不持有独立状态，只读写宿主 system 的 ``SRPGGame``。用 Protocol 显式标记
    这一共享契约，让 mixin 之间、mixin 与宿主 system 之间的依赖在类型层可见。
    """

    _game: SRPGGame
