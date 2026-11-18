"""HTTP 适配层：路由、依赖注入、错误映射与传输契约（``schemas``）。

包本身不聚合任何对象：``services.api.schemas`` 会被客户端复用，因此不能在
``__init__`` 里 import 路由（那会连带 FastAPI 与数据库）。挂载入口见 ``routes``。
"""
