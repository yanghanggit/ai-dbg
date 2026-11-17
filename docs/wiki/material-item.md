# 材料系统（MaterialItem）

`MaterialItem` 是原料类道具的数据模型：不可在战斗中直接使用，不携带卡牌或词缀。当前版本没有工坊、合成或战斗掉落入口，材料只保留数据形状，供后续生产系统接入。

材料以名称为堆叠身份：同名材料可并为一堆，库存中不保留重复条目。它与消耗品、装备同属 `AnyItem` 联合类型，但只有后两者能在战斗中物化为卡牌。

→ 参见：[装备系统（GearItem）](gear-item.md)、[消耗品系统（ConsumableItem）](consumable-item.md)
