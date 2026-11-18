class EntityNotEnabled(Exception):
    """The entity is not enabled."""


class AlreadyAddedComponent(Exception):
    """The entity already contains this type of component."""


class MissingComponent(Exception):
    """The entity does not contain this type of component."""


class MissingEntity(Exception):
    """The context does not contain this entity."""


class GroupSingleEntity(Exception):
    """The group contains more than one entity."""


class EntitasException(Exception):
    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message + "\n" + hint if hint else message)


class StopPipeline(BaseException):
    """调度信号：本 pass 不再执行后续 processor。

    它是**控制流**而不是错误：不参与 ``ErrorPolicy``，也不会被
    ``except Exception`` 吞掉（继承 ``BaseException``，与
    :class:`asyncio.CancelledError` 同类）。pipeline 逐层向上传递，
    由应用边界（``process_pipeline``）消费并转成 ``PassResult(aborted_by=...)``。
    """

    def __init__(self, reason: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
