"""确定性战斗结算的纯计算测试。"""

from ai_srpg.systems.combat_resolution import compute_damage


def test_single_hit_subtracts_block() -> None:
    result = compute_damage(base_damage=5, hits=1, block=4, old_hp=20, max_hp=20)
    assert (result.hits, result.per_hit, result.total, result.new_hp) == (1, 1, 1, 19)
    assert result.expr == "5−4=每击1 ×1击=1"


def test_block_fully_absorbs() -> None:
    result = compute_damage(base_damage=2, hits=1, block=4, old_hp=20, max_hp=20)
    assert (result.per_hit, result.total, result.new_hp) == (0, 0, 20)


def test_multi_hit_sums_each_hit() -> None:
    result = compute_damage(base_damage=6, hits=2, block=4, old_hp=20, max_hp=20)
    assert (result.per_hit, result.total, result.new_hp) == (2, 4, 16)
    assert result.expr == "6−4=每击2 ×2击=4"


def test_hp_is_clamped_at_zero() -> None:
    result = compute_damage(base_damage=10, hits=3, block=0, old_hp=5, max_hp=10)
    assert result.total == 30
    assert result.new_hp == 0


def test_negative_values_are_treated_as_zero() -> None:
    result = compute_damage(base_damage=-5, hits=-1, block=-3, old_hp=10, max_hp=10)
    assert (result.hits, result.per_hit, result.total, result.new_hp) == (0, 0, 0, 10)
