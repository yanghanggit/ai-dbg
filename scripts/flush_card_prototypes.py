#!/usr/bin/env python3
"""卡牌原型快刷脚本（开发 / 测试用）。

把 `demo/card_prototypes.py` 的原型刷进 PostgreSQL，供怪物牌库重建与调测检索使用。
**不** drop 数据库、**不**重刷蓝图 / 副本 / 用户，因此比 `scripts/setup_demo.py` 快得多，
适合改完原型或词缀规范后反复刷新。

用法：
  uv run python -m scripts.flush_card_prototypes
      全量 upsert，并打印每个原型的状态（新增 / 更新 / 未变）。

  uv run python -m scripts.flush_card_prototypes --list
      只列出当前库中的原型后退出。

  uv run python -m scripts.flush_card_prototypes --only proto.pierce
      只刷指定原型（可重复：--only proto.pierce --only proto.dot）。

  uv run python -m scripts.flush_card_prototypes --card-type 装备
      只刷某个 card_type（手牌 / 装备）。

  uv run python -m scripts.flush_card_prototypes --only proto.pierce --prune
      库中只留这些，其余删除，适合定点测试单个原型。

  uv run python -m scripts.flush_card_prototypes --only proto.pierce --dry-run
      只显示将发生的变化，不写库。

注意：`--prune` 会删除库中不在本次集合里的**所有**原型（含 手牌 / 装备 两类）。
      要恢复全部，重跑一次不带 `--only/--prune` 的全量刷即可。
"""

import json
from typing import List, Tuple

import click

from ai_dbg.models import Card
from ai_dbg.pgsql import (
    delete_card_prototypes,
    get_card_prototype,
    list_card_prototype_index,
    save_card_prototype,
)
from demo import CARD_PROTOTYPES, CardPrototype


#######################################################################################################
def _print_db_index() -> None:
    index = list_card_prototype_index(include_basic=True)
    print(f"库中卡牌原型：{len(index)} 个")
    for row in index:
        print(
            f"  {row['prototype_id']:<18} [{row['card_type']}/{row['archetype']}] {row['name']}"
        )


#######################################################################################################
def _save(proto: CardPrototype) -> None:
    meta = proto.meta
    save_card_prototype(
        prototype_id=meta.prototype_id,
        card_type=meta.card_type,
        archetype=meta.archetype,
        archetype_subtype=meta.archetype_subtype,
        name=meta.name,
        summary=meta.summary,
        design=meta.design,
        card_json=proto.skeleton.model_dump_json(),
        keywords=list(meta.keywords),
        tier=meta.tier,
    )


#######################################################################################################
def _card_field_diff(old_card_json: str, new_card: Card) -> List[str]:
    """比较库中 card_json 与源码 Card，返回发生变化的字段名。

    忽略 `uuid` / `source`：它们是每个实例自己的值，不反映原型内容变化。
    """
    ignored = {"uuid", "source"}
    try:
        old = json.loads(old_card_json)
    except Exception:
        return ["card(旧值无法解析)"]
    new = json.loads(new_card.model_dump_json())
    return [key for key in new if key not in ignored and old.get(key) != new.get(key)]


#######################################################################################################
def _flush_one(proto: CardPrototype, dry_run: bool) -> Tuple[str, List[str]]:
    """刷单个原型，返回 (状态, 变化字段)。状态 ∈ {新增, 更新, 未变}。"""
    meta = proto.meta
    try:
        existing = get_card_prototype(meta.prototype_id)
    except ValueError:
        existing = None

    if existing is None:
        if not dry_run:
            _save(proto)
        return "新增", ["*"]

    changed: List[str] = []
    for attr, new_value in (
        ("card_type", meta.card_type),
        ("archetype", meta.archetype),
        ("archetype_subtype", meta.archetype_subtype),
        ("name", meta.name),
        ("summary", meta.summary),
        ("design", meta.design),
        ("keywords", list(meta.keywords)),
    ):
        old_value = (
            json.loads(existing.keywords_json)
            if attr == "keywords"
            else getattr(existing, attr)
        )
        if old_value != new_value:
            changed.append(attr)
    changed += _card_field_diff(existing.card_json, proto.skeleton)

    if not changed:
        return "未变", []
    if not dry_run:
        _save(proto)
    return "更新", changed


#######################################################################################################
@click.command()
@click.option(
    "--only",
    "only_ids",
    multiple=True,
    help="只刷这些 prototype_id（可重复：--only proto.pierce --only proto.dot）",
)
@click.option("--card-type", default="", help="按 card_type 过滤（手牌 / 装备）")
@click.option(
    "--prune",
    is_flag=True,
    help="删除库中不在本次集合里的原型（清场，便于定点测试）",
)
@click.option("--list", "list_only", is_flag=True, help="只列出当前库中的原型后退出")
@click.option("--dry-run", is_flag=True, help="只显示将发生的变化，不写库")
def main(
    only_ids: Tuple[str, ...],
    card_type: str,
    prune: bool,
    list_only: bool,
    dry_run: bool,
) -> None:
    """快刷卡牌原型到 PostgreSQL（不 drop 库、不刷蓝图 / 副本）。"""

    if list_only:
        _print_db_index()
        return

    all_protos = {proto.meta.prototype_id: proto for proto in CARD_PROTOTYPES}

    # 解析目标集合
    if only_ids:
        unknown = [pid for pid in only_ids if pid not in all_protos]
        if unknown:
            raise click.BadParameter(
                f"未知 prototype_id: {unknown}（可用 --list 或查看 demo/card_prototypes.py）",
                param_hint="--only",
            )
        targets = [all_protos[pid] for pid in only_ids]
    elif card_type:
        targets = [p for p in CARD_PROTOTYPES if p.meta.card_type == card_type]
        if not targets:
            raise click.BadParameter(
                f"没有 card_type == {card_type!r} 的原型", param_hint="--card-type"
            )
    else:
        targets = list(CARD_PROTOTYPES)

    target_ids = {p.meta.prototype_id for p in targets}

    # 清场
    pruned = 0
    planned_prune = 0
    if prune:
        current = {
            row["prototype_id"] for row in list_card_prototype_index(include_basic=True)
        }
        to_delete = sorted(current - target_ids)
        planned_prune = len(to_delete)
        if to_delete:
            if dry_run:
                print(f"[dry-run] 将删除 {len(to_delete)} 个原型: {to_delete}")
            else:
                pruned = delete_card_prototypes(to_delete)
                print(f"已删除 {pruned} 个不在集合中的原型: {to_delete}")
        else:
            print("无需删除（库中已无多余原型）")

    # 刷写
    counts = {"新增": 0, "更新": 0, "未变": 0}
    for proto in targets:
        status, changed = _flush_one(proto, dry_run)
        counts[status] += 1
        if status != "未变":
            prefix = "[dry-run] " if dry_run else ""
            detail = f" ← {', '.join(changed)}" if changed and changed != ["*"] else ""
            print(f"{prefix}{status}: {proto.meta.prototype_id}{detail}")

    prune_note = planned_prune if dry_run else pruned
    prune_label = "将删除" if dry_run else "删除"
    print(
        f"\n完成：新增 {counts['新增']} / 更新 {counts['更新']} / 未变 {counts['未变']} / {prune_label} {prune_note}"
    )
    _print_db_index()


#######################################################################################################
if __name__ == "__main__":
    main()
