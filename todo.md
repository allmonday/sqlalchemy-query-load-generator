# TODO

## 自动选择 load 策略

根据关系类型自动选择 `joinedload` 或 `selectinload`：

```python
for rel in mapper.relationships:
    if rel.uselist:
        # 一对多/多对多，避免笛卡尔积
        use selectinload
    else:
        # 一对一，单次 JOIN 更高效
        use joinedload
```

**收益：**
- 一对一关系减少数据库往返
- 一对多关系避免笛卡尔积
- 用户无需关心底层实现
