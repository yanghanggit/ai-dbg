# entitas

`ai-srpg` 使用的最小 ECS（Entity–Component–System）核心：把游戏的**数据**（组件）与**身份**（实体句柄）分离，由 `Context` 统一存储与查询，便于以线性流程编排游戏逻辑。

## 核心原则：组件数据只能从 add / replace / remove 三个点被改变

> **组件数据的任何变更，都必须且只能通过 `Entity` 的 `add` / `replace` / `remove` 发生。**
> `get()` 只读；拿到组件后改字段、改列表、改嵌套对象都不算数据变更——它们不触发事件，
> 也不会被分组 / 反应式系统观察到。

- **创建期新增**：`add()`（按字段传参）；`set()` 是它的实例版（直接给已构造好的组件），同样只允许在创建期使用。
- **运行期写入**：`replace()`，同时覆盖「新增」与「替换」两种语义。
- **删除**：`remove()`。

以下写法一律禁止（都属于绕过 `replace` 的隐式写入）：

```python
entity.get(Comp).field = value          # 字段赋值
entity.get(Comp).items.append(x)        # 容器原地增删
entity.get(Comp).cards[:] = []          # 切片赋值
entity.get(Comp).stats.hp = 1           # 改嵌套模型
random.shuffle(entity.get(Comp).cards)  # 交给原地修改的函数
```

需要改嵌套数据时，先构造新值，再整体写回：

```python
old = hero.get(Inventory)
new_items = [item for item in old.items if item.id != target_id]
hero.replace(Inventory, old.name, new_items)
```

## 核心概念

| 概念 | 作用 |
| --- | --- |
| `Component` | 纯数据，Pydantic `BaseModel` 子类。 |
| `Context` | 组件存储 + 查询分组；实体的唯一归属。 |
| `Entity` | 轻量句柄，只持有 `(context, index, name)`，组件不在句柄上。 |
| `Matcher` | 组件条件：`all_of` / `any_of` / `none_of`。 |
| `Group` | 满足某 `Matcher` 的实体集合，随组件增删自动更新。 |
| `Collector` | 订阅 `Group` 的增删事件，收集待处理实体。 |
| `ReactiveProcessor` | 每帧「收集 → 过滤 → 批量处理」的处理器基类。 |
| `ProcessorPipeline` | 按 `Initialize → Execute → Cleanup → TearDown` 编排多个处理器。 |
| `Initialize/Execute/Cleanup/TearDownProcessor` | 处理器生命周期的抽象契约（`ABC`）。 |

## 最小用法

```python
from ai_srpg.entitas import Component, Context, Matcher


class Position(Component):
    x: float
    y: float


context = Context()

hero = context.create_entity()
hero.add(Position, 0.0, 0.0)             # 按字段顺序传参
# 或：hero.set(Position, Position(x=0.0, y=0.0))  # 直接放组件实例

for entity in context.get_group(Matcher(Position)).entities:
    print(entity, entity.get(Position))

hero.replace(Position, 9.0, 9.0)
hero.remove(Position)
context.destroy_entity(hero)
```

## 组件写入模型：add / replace / remove 是唯一写入口

`Entity` 把组件数据的所有变更收敛到三个方法——**只有这 3 个点能变换组件数据**，
每一次写入都能被 `on_component_added` / `on_component_replaced` /
`on_component_removed` 这三个事件明确观察到：

- `add()`：仅用于实体创建阶段（组件尚不存在时）；
- `replace()`：运行期**唯一**的写入方式，同时覆盖「新增」与「替换」；
- `remove()`：移除组件。

`get()` 是**只读**的：拿到组件后不要直接改它的字段，也不要改它内部持有的列表、
字典或嵌套模型（`component.cards.append(...)`、`component.stats.hp = ...` 都属于隐式
写入）。这类修改不经过 `replace`，不会触发事件，也不会被分组 / 反应式系统观察到。

需要修改嵌套数据时，先构造新值，再整体写回：

```python
# 正确：读 → 构造新值 → replace
old = hero.get(Inventory)
new_items = [item for item in old.items if item.id != target_id]
hero.replace(Inventory, old.name, new_items)

# 错误：就地修改，事件系统看不到
hero.get(Inventory).items.remove(target)
```

处理器（可选）：

```python
from ai_srpg.entitas import GroupEvent, Matcher, ProcessorPipeline, ReactiveProcessor


class OnMove(ReactiveProcessor):
    def get_trigger(self):
        return {Matcher(Position): GroupEvent.ADDED}

    def filter(self, entity) -> bool:
        return True

    async def react(self, entities) -> None:
        ...


pipeline = ProcessorPipeline()
pipeline.add(OnMove(context))
await pipeline.execute()
pipeline.cleanup()
```

## 失败与提前结束（pass 语义）

pipeline 只定义调度，不解释失败的严重性。一次 `execute()` 称为一个 **pass**，
结果是 `PassResult`：

- `completed`：所有 processor 都正常返回（可能含 `CONTINUE` 记录的失败）；
- `interrupted`：失败按策略传播，剩余 processor 被跳过；
- `aborted_by is not None`：显式提前结束；
- `ran` / `failures` / `skipped`：逐项记录执行、失败与被跳过的 processor。

### 错误策略由组装方声明

processor 抛异常只表示「这一步没完成」，不表示「整条 pipeline 该停」。
停不停由组装方按 processor 在序列中的位置声明：

```python
from ai_srpg.entitas import ErrorPolicy, ExecuteProcessor


class CollectBonus(ExecuteProcessor):
    error_policy = ErrorPolicy.CONTINUE  # 旁路逻辑：失败也继续

    async def execute(self) -> None:
        ...
```

默认 `ErrorPolicy.PROPAGATE`：pipeline 的意义就是顺序依赖，某一步没有完成时
序列不再可信，剩余 processor 被跳过，异常继续上抛。`CONTINUE` 的失败会进
`PassResult.failures`，pass 仍算 `completed`。

### 显式提前结束

`StopPipeline` 是控制流信号，不是错误。它继承 `BaseException`，因此不会被
`except Exception` 吞掉；pipeline 记录 `aborted_by` 与 `skipped` 后逐层上抛，
由应用边界消费。

```python
from ai_srpg.entitas import StopPipeline

if game.is_over:
    raise StopPipeline("campaign finished")
```

### 应用边界

`process_pipeline(pipeline, observer)` 负责：执行一次 pass、保证 `cleanup()`
一定运行、把 `StopPipeline` 转成 `PassResult` 而不当作失败。真正的失败仍然
上抛，由上层决定重试与状态处理；最近一次结果保存在 `pipeline.last_pass`。

### initialize / tear_down 的策略

`initialize()` 与 `tear_down()` 与 `execute()` 共用 `ErrorPolicy` 默认值
（`PROPAGATE`）：初始化是启动顺序的一部分，关闭也可能相互依赖，失败默认
中断后续步骤并上抛。需要「失败也继续」的 processor 自行声明
`CONTINUE`，失败的 processor 仍会通过 observer 的
`on_processor_failed` 记录。

两者的 `observer` 由调用方显式传入；`StopPipeline` 在任一阶段都表示显式
中止，不是失败，直接上抛给启动/关闭的边界处理。`cleanup()` 是 pass 的收尾，
不参与 `error_policy`：`process_pipeline` 保证它一定运行，失败只记录。

## 序列化（dump / load）

以**实体名作 key** 的纯 dict 表示，只保存「重建 Context 核心」所需的组件；`pools` /
`handles` / `groups` / 事件接线 / 名称索引等运行期成员一律不存，加载时重建。

```python
ComponentData = dict[str, Any]              # 组件字段名 -> 值
EntityData    = dict[str, ComponentData]    # 组件类型名 -> 组件数据
ContextData   = dict[str, EntityData]       # 实体名 -> 实体数据

dump_entity(entity, *, component_filter=None) -> EntityData
dump_components(*components) -> EntityData                      # 由组件实例直接构造
dump_entities(entities, *, component_filter=None) -> ContextData
dump_context(context, *, component_filter=None) -> ContextData  # 按 slot index 顺序
load_context(context, data, resolve_type) -> dict[str, Entity]  # 注入 resolver，静默写入
```

```python
from ai_srpg.entitas import Context, dump_components, dump_context, load_context


# 导出：{"hero": {"Position": {"x": 1.0, "y": 2.0}}}
data = dump_context(context)

# 蓝图/工厂里直接构造：{"Position": {"x": 1.0, "y": 2.0}, "Marker": {}}
entity_data = dump_components(Position(x=1.0, y=2.0), Marker())


# 还原进一个空 Context（组件类型名 -> 类 由调用方注入）
def resolve(name: str, comp_data: dict) -> type:
    return {"Position": Position, "Marker": Marker}[name]


restored = load_context(Context(), data, resolve)
```

契约：

- `dump_*` 要求实体 `name` **非空且唯一**（重名会静默丢数据）。
- `load_context` 仅用于**空 Context**；直接写 storage、**不触发组件事件**，故分组应在 load 之后创建。
- entitas 不认识组件注册表：类型解析由 `resolve_type` 注入（游戏层用 `resolve_component_type`）。

## 设计要点

- **index 化存储**：组件按类型分池 `dict[type, list]`，用实体 `index` 直寻址（sparse-set / SoA）。
- **实体即句柄**：身份 = 句柄对象本身；`index` 只用于在 `Context` 中定位组件，槽位不做回收/复用。
- **查询**：`Group` 内部只存 `index`，`entities` 按需物化句柄；组件变更通过事件增量维护。
- **类型解耦**：`ContextProtocol`（`typing.Protocol`）以结构化类型描述 `Context` 对外接口，避免 `Entity`/`Group` 与 `Context` 的循环导入。
- **导入统一**：使用者只需 `from ai_srpg.entitas import ...`。

## 说明

- 所有组件必须继承 `entitas.components.Component`（基于 Pydantic `BaseModel`）。
- 测试用的通用组件放在 `tests/ecs_testing.py`，**不属于发布包**。
