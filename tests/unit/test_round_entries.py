"""回合记录实体单元测试：验证跨种类操作的全局先后顺序。"""

from typing import Any

from ai_dbg.game.combat.state import (
    combat_round_entries,
    combat_round_view,
    record_round_entry,
)
from ai_dbg.models import CombatRoundEntryComponent, RoundEntryKind
from dungeon_support import current_round_entity, install_combat


def _round_entity(game: Any) -> Any:
    install_combat(game)
    return current_round_entity(game)


def test_record_preserves_global_order_across_kinds(sample_game: Any) -> None:
    round_entity = _round_entity(sample_game)
    record_round_entry(
        sample_game, round_entity, RoundEntryKind.CARDS, "出牌1", "叙事1"
    )
    record_round_entry(
        sample_game, round_entity, RoundEntryKind.GEAR, "装备", "装备叙事"
    )
    record_round_entry(
        sample_game, round_entity, RoundEntryKind.CARDS, "出牌2", "叙事2"
    )
    record_round_entry(
        sample_game, round_entity, RoundEntryKind.CONSUMABLE, "消耗品", "消耗品叙事"
    )
    record_round_entry(
        sample_game, round_entity, RoundEntryKind.ARTIFACT, "神器", "神器叙事"
    )

    entries = combat_round_entries(sample_game, round_entity)
    assert [e.get(CombatRoundEntryComponent).kind for e in entries] == [
        RoundEntryKind.CARDS,
        RoundEntryKind.GEAR,
        RoundEntryKind.CARDS,
        RoundEntryKind.CONSUMABLE,
        RoundEntryKind.ARTIFACT,
    ]
    # log/narrative 成对绑定在同一条目上
    first = entries[0].get(CombatRoundEntryComponent)
    assert first.log == "出牌1"
    assert first.narrative == "叙事1"
    # 视图按实体序号投影，顺序与实体查询一致
    round_view = combat_round_view(sample_game, round_entity)
    assert [entry.kind for entry in round_view.entries] == [
        RoundEntryKind.CARDS,
        RoundEntryKind.GEAR,
        RoundEntryKind.CARDS,
        RoundEntryKind.CONSUMABLE,
        RoundEntryKind.ARTIFACT,
    ]


def test_round_entry_component_serialization_round_trip(sample_game: Any) -> None:
    round_entity = _round_entity(sample_game)
    entry_entity = record_round_entry(
        sample_game, round_entity, RoundEntryKind.CARDS, "log", "narrative"
    )
    component = entry_entity.get(CombatRoundEntryComponent)
    restored = CombatRoundEntryComponent.model_validate_json(
        component.model_dump_json()
    )
    assert restored == component
    assert restored.kind == RoundEntryKind.CARDS
    assert restored.log == "log"
    assert restored.narrative == "narrative"


def test_kind_is_str_enum() -> None:
    assert RoundEntryKind.CARDS.value == "cards"
    assert RoundEntryKind("artifact") is RoundEntryKind.ARTIFACT
