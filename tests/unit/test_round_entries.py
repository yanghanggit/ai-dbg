"""回合记录队列单元测试：验证跨种类操作的全局先后顺序。"""

from typing import Any

from ai_dbg.game.combat.state import record_round_entry
from ai_dbg.models import CombatRoundComponent, RoundEntry, RoundEntryKind
from dungeon_support import current_round_entity, install_combat


def _round_entity(game: Any) -> Any:
    install_combat(game)
    return current_round_entity(game)


def test_record_preserves_global_order_across_kinds(sample_game: Any) -> None:
    round_entity = _round_entity(sample_game)
    record_round_entry(round_entity, RoundEntryKind.CARDS, "出牌1", "叙事1")
    record_round_entry(round_entity, RoundEntryKind.GEAR, "装备", "装备叙事")
    record_round_entry(round_entity, RoundEntryKind.CARDS, "出牌2", "叙事2")
    record_round_entry(round_entity, RoundEntryKind.CONSUMABLE, "消耗品", "消耗品叙事")
    record_round_entry(round_entity, RoundEntryKind.ARTIFACT, "神器", "神器叙事")

    entries = round_entity.get(CombatRoundComponent).entries
    assert [e.kind for e in entries] == [
        RoundEntryKind.CARDS,
        RoundEntryKind.GEAR,
        RoundEntryKind.CARDS,
        RoundEntryKind.CONSUMABLE,
        RoundEntryKind.ARTIFACT,
    ]
    # log/narrative 成对绑定在同一条目上
    assert entries[0].log == "出牌1"
    assert entries[0].narrative == "叙事1"


def test_round_component_serialization_round_trip(sample_game: Any) -> None:
    round_entity = _round_entity(sample_game)
    record_round_entry(round_entity, RoundEntryKind.CARDS, "log", "narrative")
    component = round_entity.get(CombatRoundComponent)
    restored = CombatRoundComponent.model_validate_json(component.model_dump_json())
    assert restored == component
    assert restored.entries[0] == RoundEntry(
        kind=RoundEntryKind.CARDS, log="log", narrative="narrative"
    )


def test_kind_is_str_enum() -> None:
    assert RoundEntryKind.CARDS.value == "cards"
    assert RoundEntryKind("artifact") is RoundEntryKind.ARTIFACT
