"""游戏服务器 HTTP 客户端封装（API Agent 专用）。

供 `ai_dbg/cli/dbg_agent_api.py` 等代理入口调用，只依赖 httpx 与 ai_dbg.models，
不含任何界面代码。
"""

import json
from typing import Any, Dict, List, Union, cast

import httpx
from procrastinate.jobs import Status as ProcrastinateJobStatus

from ..models import (
    BlueprintListResponse,
    CompactContextRequest,
    CompactContextResponse,
    DungeonAdvanceStageRequest,
    DungeonAdvanceStageResponse,
    DungeonCombatCollectLootRequest,
    DungeonCombatCollectLootResponse,
    DungeonCombatDrawCardsRequest,
    DungeonCombatDrawCardsResponse,
    DungeonCombatEquipGearItemRequest,
    DungeonCombatEquipGearItemResponse,
    DungeonCombatInitRequest,
    DungeonCombatInitResponse,
    DungeonCombatPassTurnRequest,
    DungeonCombatPassTurnResponse,
    DungeonCombatPlayCardsRequest,
    DungeonCombatPlayCardsResponse,
    DungeonCombatRetreatRequest,
    DungeonCombatRetreatResponse,
    DungeonCombatUseConsumableItemRequest,
    DungeonCombatUseConsumableItemResponse,
    DungeonExitRequest,
    DungeonExitResponse,
    DungeonListResponse,
    DungeonOpeningInitRequest,
    DungeonOpeningInitResponse,
    DungeonRoomResponse,
    DungeonStartRequest,
    DungeonStartResponse,
    DungeonStateResponse,
    EntitiesDetailsResponse,
    JobDetail,
    JobEventsResponse,
    JobSnapshot,
    JobStatusListResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    NewGameRequest,
    NewGameResponse,
    SessionMessageResponse,
    StagesStateResponse,
)
from .config import server_config


class JobFailedError(Exception):
    """job 执行失败时抛出。"""

    pass


def build_client(timeout: Union[float, httpx.Timeout] = 10.0) -> httpx.AsyncClient:
    """构造统一的 httpx 客户端。

    连接层配置集中在此，便于将来引入 HTTPS / JWT：
    - base_url: 由 server_config.scheme/host/port 决定（http 或 https）；
    - headers: 由 server_config.auth_token 决定是否注入 ``Authorization: Bearer``；
    - verify: TLS 证书校验开关，或 CA bundle 路径。

    Args:
        timeout: 请求超时；既可为秒数，也可为 ``httpx.Timeout`` 实例。
    """
    return httpx.AsyncClient(
        base_url=server_config.base_url,
        headers=server_config.headers,
        verify=server_config.verify,
        timeout=timeout,
    )


async def fetch_server_info() -> Dict[str, Any]:
    """请求游戏服务器根路由，返回服务信息 JSON。"""
    async with build_client(5) as client:
        response = await client.get("/")
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())


async def login(user_name: str, game_name: str) -> str:
    """登录游戏服务器，返回服务器响应消息。"""
    async with build_client(5) as client:
        response = await client.post(
            "/api/login/v1/",
            json=LoginRequest(user_name=user_name, game_name=game_name).model_dump(),
        )
        response.raise_for_status()
        return LoginResponse.model_validate(response.json()).message


async def new_game(
    user_name: str, game_name: str, dungeon_name: str
) -> NewGameResponse:
    """创建新游戏并直接进入副本，返回服务器响应。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/game/new/v1/",
            json=NewGameRequest(
                user_name=user_name,
                game_name=game_name,
                dungeon_name=dungeon_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return NewGameResponse.model_validate(response.json())


async def fetch_stages_state(user_name: str, game_name: str) -> StagesStateResponse:
    """查询场景状态，返回场景与角色的分布映射。"""
    async with build_client(10) as client:
        response = await client.get(
            f"/api/stages/v1/{user_name}/{game_name}/state",
        )
        response.raise_for_status()
        return StagesStateResponse.model_validate(response.json())


async def logout(user_name: str, game_name: str) -> str:
    """登出游戏服务器，返回服务器响应消息。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/logout/v1/",
            json=LogoutRequest(user_name=user_name, game_name=game_name).model_dump(),
        )
        response.raise_for_status()
        return LogoutResponse.model_validate(response.json()).message


async def fetch_blueprint_list() -> BlueprintListResponse:
    """获取可用蓝图列表。"""
    async with build_client(10) as client:
        response = await client.get(
            "/api/game/blueprint-list/v1/",
        )
        response.raise_for_status()
        return BlueprintListResponse.model_validate(response.json())


async def fetch_session_messages(
    user_name: str, last_sequence_id: int
) -> SessionMessageResponse:
    """增量获取用户会话消息（用户级历史，不依赖当前 game）。"""
    async with build_client(10) as client:
        response = await client.get(
            f"/api/session_messages/v1/{user_name}/since",
            params={"last_sequence_id": last_sequence_id},
        )
        response.raise_for_status()
        return SessionMessageResponse.model_validate(response.json())


async def fetch_entities_details(
    user_name: str, game_name: str, entity_names: List[str]
) -> EntitiesDetailsResponse:
    """批量查询实体详情。"""
    async with build_client(10) as client:
        response = await client.get(
            f"/api/entities/v1/{user_name}/{game_name}/details",
            params={"entities": entity_names},
        )
        response.raise_for_status()
        return EntitiesDetailsResponse.model_validate(response.json())


async def fetch_entities_group(
    user_name: str,
    game_name: str,
    all_of: List[str],
    any_of: List[str],
    none_of: List[str],
) -> EntitiesDetailsResponse:
    """按组件条件分组查询实体，返回匹配实体的序列化数据。"""
    async with build_client(10) as client:
        response = await client.get(
            f"/api/entities/v1/{user_name}/{game_name}/group",
            params={
                "all_of": all_of,
                "any_of": any_of,
                "none_of": none_of,
            },
        )
        response.raise_for_status()
        return EntitiesDetailsResponse.model_validate(response.json())


async def fetch_dungeon_list() -> DungeonListResponse:
    """获取可用副本列表。"""
    async with build_client(10) as client:
        response = await client.get(
            "/api/dungeon/list/v1/",
        )
        response.raise_for_status()
        return DungeonListResponse.model_validate(response.json())


async def fetch_jobs_status(job_ids: List[int]) -> JobStatusListResponse:
    """批量查询 job 状态。"""
    async with build_client(10) as client:
        response = await client.get(
            "/api/jobs/v1/status",
            params={"job_ids": job_ids},
        )
        response.raise_for_status()
        return JobStatusListResponse.model_validate(response.json())


async def watch_job_until_done(job_id: int, timeout_seconds: int = 120) -> JobSnapshot:
    """通过 SSE 等待 job 完成，返回终态 JobSnapshot。

    Args:
        job_id: 要监听的 job id
        timeout_seconds: 最大等待秒数（同时透传给服务端 SSE 生成器）

    Returns:
        JobSnapshot: 状态为 SUCCEEDED 的 job 快照

    Raises:
        JobFailedError: job 不存在或失败（status=FAILED）
        TimeoutError: 等待超时
    """
    url = f"/api/jobs/v1/watch/{job_id}"
    params = {"timeout_seconds": timeout_seconds}
    timeout = httpx.Timeout(
        connect=10.0,
        read=float(timeout_seconds + 15),
        write=10.0,
        pool=10.0,
    )
    async with build_client(timeout) as client:
        async with client.stream("GET", url, params=params) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                data = json.loads(payload)
                # 错误封套（job 不存在 / 超时）不带 status 字段；job 快照必带 status。
                # 注意：JobSnapshot 即使成功也会序列化出 "error": null，故不能用
                # `"error" in data` 判定失败。
                if "status" not in data:
                    if data.get("error") == "timeout":
                        raise TimeoutError(f"job {job_id} 等待超时")
                    raise JobFailedError(f"{data.get('error')}: job_id={job_id}")
                record = JobSnapshot.model_validate(data)
                if record.status == ProcrastinateJobStatus.FAILED:
                    raise JobFailedError(record.error or "未知错误")
                if record.status == ProcrastinateJobStatus.SUCCEEDED:
                    return record
                if record.status in (
                    ProcrastinateJobStatus.CANCELLED,
                    ProcrastinateJobStatus.ABORTED,
                ):
                    raise JobFailedError(
                        record.error or f"job 状态: {record.status.value}"
                    )
    raise TimeoutError(f"job {job_id} 等待超时")


async def fetch_job_detail(job_id: int) -> JobDetail:
    """查询单个 job 的状态与完整执行事件。"""
    async with build_client(10) as client:
        response = await client.get(f"/api/jobs/v1/{job_id}")
        response.raise_for_status()
        return JobDetail.model_validate(response.json())


async def fetch_job_events(
    job_id: int, *, after_id: int = 0, limit: int = 500
) -> JobEventsResponse:
    """增量查询 job 执行事件。"""
    async with build_client(10) as client:
        response = await client.get(
            f"/api/jobs/v1/{job_id}/events",
            params={"after_id": after_id, "limit": limit},
        )
        response.raise_for_status()
        return JobEventsResponse.model_validate(response.json())


async def fetch_dungeon_state(user_name: str, game_name: str) -> DungeonStateResponse:
    """查询当前副本完整状态。"""
    async with build_client(10) as client:
        response = await client.get(
            f"/api/dungeons/v1/{user_name}/{game_name}/state",
        )
        response.raise_for_status()
        return DungeonStateResponse.model_validate(response.json())


async def fetch_dungeon_room(user_name: str, game_name: str) -> DungeonRoomResponse:
    """查询当前副本房间（含 stage + combat）。"""
    async with build_client(10) as client:
        response = await client.get(
            f"/api/dungeons/v1/{user_name}/{game_name}/room",
        )
        response.raise_for_status()
        return DungeonRoomResponse.model_validate(response.json())


async def start_dungeon(
    user_name: str, game_name: str, dungeon_name: str
) -> DungeonStartResponse:
    """从大厅进入指定副本（仅传送到首间，不初始化房间）。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/start/v1/",
            json=DungeonStartRequest(
                user_name=user_name,
                game_name=game_name,
                dungeon_name=dungeon_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonStartResponse.model_validate(response.json())


async def dungeon_exit(user_name: str, game_name: str) -> DungeonExitResponse:
    """触发退出副本 job，返回 job id。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/exit/v1/",
            json=DungeonExitRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonExitResponse.model_validate(response.json())


async def dungeon_advance_stage(
    user_name: str, game_name: str
) -> DungeonAdvanceStageResponse:
    """推进副本到下一关卡（关卡内战斗结束进入 post_combat 后调用）。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/progress/advance_stage/v1/",
            json=DungeonAdvanceStageRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonAdvanceStageResponse.model_validate(response.json())


async def dungeon_opening_init(
    user_name: str, game_name: str
) -> DungeonOpeningInitResponse:
    """触发开场房间初始化（叙事 + 牌库初始化），返回 job id。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/opening/init/v1/",
            json=DungeonOpeningInitRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonOpeningInitResponse.model_validate(response.json())


async def dungeon_combat_collect_loot(
    user_name: str, game_name: str
) -> DungeonCombatCollectLootResponse:
    """收取战斗战利品，将掉落物转入背包。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/combat/collect_loot/v1/",
            json=DungeonCombatCollectLootRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatCollectLootResponse.model_validate(response.json())


async def dungeon_combat_init(
    user_name: str, game_name: str
) -> DungeonCombatInitResponse:
    """触发战斗初始化，返回 job id。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/combat/init/v1/",
            json=DungeonCombatInitRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatInitResponse.model_validate(response.json())


async def dungeon_combat_retreat(
    user_name: str, game_name: str
) -> DungeonCombatRetreatResponse:
    """触发战斗撤退，返回 job id。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/combat/retreat/v1/",
            json=DungeonCombatRetreatRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatRetreatResponse.model_validate(response.json())


async def dungeon_combat_draw_cards(
    user_name: str, game_name: str
) -> DungeonCombatDrawCardsResponse:
    """为全体战斗角色激活抽牌动作，返回 job id。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/combat/draw_cards/v1/",
            json=DungeonCombatDrawCardsRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatDrawCardsResponse.model_validate(response.json())


async def dungeon_combat_play_cards(
    user_name: str,
    game_name: str,
    actor_name: str,
    card_name: str,
    targets: List[str],
) -> DungeonCombatPlayCardsResponse:
    """让指定角色打出指定卡牌，返回 job id。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/combat/play_cards/v1/",
            json=DungeonCombatPlayCardsRequest(
                user_name=user_name,
                game_name=game_name,
                actor_name=actor_name,
                card_name=card_name,
                targets=targets,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatPlayCardsResponse.model_validate(response.json())


async def dungeon_combat_pass_turn(
    user_name: str,
    game_name: str,
    actor_name: str,
) -> DungeonCombatPassTurnResponse:
    """让指定角色过牌，返回 job id。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/combat/pass_turn/v1/",
            json=DungeonCombatPassTurnRequest(
                user_name=user_name,
                game_name=game_name,
                actor_name=actor_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatPassTurnResponse.model_validate(response.json())


async def dungeon_combat_use_consumable(
    user_name: str,
    game_name: str,
    item_name: str,
) -> DungeonCombatUseConsumableItemResponse:
    """使用玩家背包内消耗品，返回 job id。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/combat/use_consumable/v1/",
            json=DungeonCombatUseConsumableItemRequest(
                user_name=user_name,
                game_name=game_name,
                item_name=item_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatUseConsumableItemResponse.model_validate(response.json())


async def dungeon_combat_equip_gear(
    user_name: str,
    game_name: str,
    item_name: str,
) -> DungeonCombatEquipGearItemResponse:
    """使用玩家背包内装备，返回 job 信息。"""
    async with build_client(10) as client:
        response = await client.post(
            "/api/dungeon/combat/equip_gear/v1/",
            json=DungeonCombatEquipGearItemRequest(
                user_name=user_name,
                game_name=game_name,
                item_name=item_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatEquipGearItemResponse.model_validate(response.json())


async def compact_context(
    user_name: str, game_name: str, target_name: str
) -> CompactContextResponse:
    """手动压缩指定实体的 LLM 记忆，返回 job id。"""
    async with build_client(30) as client:
        response = await client.post(
            "/api/compact_context/v1/",
            json=CompactContextRequest(
                user_name=user_name,
                game_name=game_name,
                target_name=target_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return CompactContextResponse.model_validate(response.json())
