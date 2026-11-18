"""玩法编排：一次 pass 的运行时、job 定义与派发、定时调度、离线一局。

本包只做应用编排，不依赖 HTTP。``jobs`` 模块在 import 时向 Procrastinate
注册 task，因此只由进程入口显式导入，不在 ``__init__`` 里聚合。
"""
