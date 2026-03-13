# SQLAlchemy Load 架构文档

## 整体架构

```
用户调用: generator.generate(User, "{ id name posts { title } }")
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    LoadGenerator                            │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │
│  │ _metadata_  │  │ _options_   │  │ generate()        │   │
│  │ cache       │  │ cache       │  │  ↓                │   │
│  │ (init时预热)│  │ (运行时缓存)│  │ 1. 查缓存         │   │
│  └─────────────┘  └─────────────┘  │ 2. 解析 query     │   │
│                                     │ 3. 构建 options   │   │
│                                     │ 4. 存缓存         │   │
│                                     └───────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────────┐
   │ parser  │ │ cache   │ │ errors      │
   │ 语法解析│ │ 元数据  │ │ 异常定义    │
   └─────────┘ └─────────┘ └─────────────┘
```

---

## 核心模块

### 文件结构

```
src/sqlalchemy_load/
├── __init__.py      # 公开 API 导出
├── generator.py     # 核心生成器
├── parser.py        # 语法解析器
├── cache.py         # 元数据数据类
└── errors.py        # 自定义异常
```

---

## 1. 初始化阶段 - `LoadGenerator.__init__()`

**文件**: `generator.py`

```python
def __init__(self, base_class: type[DeclarativeBase]):
    self._base_class = base_class
    self._metadata_cache: dict[type, ModelMetadata] = {}  # 模型元数据缓存
    self._options_cache: dict[str, list[Any]] = {}        # 生成结果缓存
    self._preload_all_metadata()  # 预热所有模型元数据
```

**`_preload_all_metadata()` - 预加载所有模型信息**:

```python
def _preload_all_metadata(self) -> None:
    # 遍历 registry 中所有 mapper（所有注册的模型）
    for mapper in self._base_class.registry.mappers:
        model_class = mapper.class_
        self._metadata_cache[model_class] = ModelMetadata(
            columns={col.key for col in mapper.columns},           # 所有列名
            relationships={rel.key for rel in mapper.relationships}, # 所有关联名
            primary_keys={pk.key for pk in mapper.primary_key},     # 主键名
            relationship_targets={
                rel.key: rel.mapper.class_  # relationship -> 目标模型类
                for rel in mapper.relationships
            }
        )
```

**结果**: 初始化后，所有模型的元数据都已缓存，后续无需再访问 SQLAlchemy 的 mapper。

---

## 2. 解析阶段 - `parse_query_string_cached()`

**文件**: `parser.py`

```python
@lru_cache(maxsize=256)
def parse_query_string_cached(query_string: str) -> FieldSelection:
    return parse_query_string(query_string)
```

**解析流程**:

```
"{ id name posts { title } }"
         │
         ▼ _tokenize()
['{', 'id', 'name', 'posts', '{', 'title', '}', '}']
         │
         ▼ _parse_selection()
FieldSelection(
    fields={'id', 'name'},
    relationships={
        'posts': FieldSelection(
            fields={'title'},
            relationships={}
        )
    }
)
```

**核心数据结构**:

```python
@dataclass
class FieldSelection:
    fields: set[str]                         # 标量字段
    relationships: dict[str, FieldSelection] # 嵌套关系（递归）
```

---

## 3. 生成阶段 - `generate()`

**文件**: `generator.py`

```python
def generate(self, model_class: type, query_string: str) -> list[Any]:
    # 1. 检查生成缓存
    cache_key = self._make_cache_key(model_class, query_string)
    # cache_key = "app.models.User:{ id name posts { title } }"
    if cache_key in self._options_cache:
        return self._options_cache[cache_key]

    # 2. 解析 query string（使用带缓存的解析器）
    selection = parse_query_string_cached(query_string)

    # 3. 递归构建 options
    options = self._build_options(model_class, selection)

    # 4. 存入缓存并返回
    self._options_cache[cache_key] = options
    return options
```

---

## 4. 核心构建逻辑 - `_build_options()`

**文件**: `generator.py`

```python
def _build_options(self, model_class: type, selection: FieldSelection) -> list[Any]:
    options = []
    metadata = self._get_metadata(model_class)  # 从缓存获取元数据

    # ═══════════════════════════════════════════════
    # 步骤 1: 验证并分离字段和关系
    # ═══════════════════════════════════════════════
    valid_fields = set()
    for field_name in selection.fields:
        # 用户写了 relationship 但忘记加 {}
        if field_name in metadata.relationships:
            raise RelationshipNotFoundError(
                f"'{field_name}' is a relationship, use '{field_name} {{ ... }}' syntax"
            )
        # 字段不存在
        if field_name not in metadata.columns:
            raise FieldNotFoundError(
                f"Field '{field_name}' does not exist on {model_class.__name__}"
            )
        valid_fields.add(field_name)

    # 验证 relationships
    for rel_name in selection.relationships:
        if rel_name not in metadata.relationships:
            # 用户把普通字段当 relationship 用
            if rel_name in metadata.columns:
                raise FieldNotFoundError(f"'{rel_name}' is a column, not a relationship")
            raise RelationshipNotFoundError(
                f"Relationship '{rel_name}' does not exist on {model_class.__name__}"
            )

    # ═══════════════════════════════════════════════
    # 步骤 2: 构建 load_only（如果有标量字段）
    # ═══════════════════════════════════════════════
    if valid_fields:
        columns = self._ensure_primary_key(model_class, valid_fields, metadata)
        # columns = [User.id, User.name]  (id 是自动加入的主键)
        options.append(load_only(*columns))

    # ═══════════════════════════════════════════════
    # 步骤 3: 递归构建 selectinload
    # ═══════════════════════════════════════════════
    for rel_name, nested_selection in selection.relationships.items():
        target_model = metadata.relationship_targets[rel_name]  # Post
        rel_attr = getattr(model_class, rel_name)              # User.posts

        # 递归！对嵌套的模型构建 options
        nested_options = self._build_options(target_model, nested_selection)

        # 组装: selectinload(User.posts).options(load_only(Post.title))
        loader = selectinload(rel_attr).options(*nested_options)
        options.append(loader)

    return options
```

---

## 5. 主键自动包含 - `_ensure_primary_key()`

```python
def _ensure_primary_key(self, model_class, field_names, metadata) -> list[Any]:
    columns = []

    # 主键始终加入（SQLAlchemy 需要主键来构造对象）
    for pk_name in sorted(metadata.primary_keys):
        columns.append(getattr(model_class, pk_name))

    # 其他请求的字段
    for field_name in sorted(field_names):
        if field_name not in metadata.primary_keys:
            columns.append(getattr(model_class, field_name))

    return columns
```

---

## 6. 完整执行示例

```python
# 输入
generator.generate(User, "{ name posts { title } }")

# ══════════════════════════════════════════════════════════
# Step 1: 解析
# ══════════════════════════════════════════════════════════
FieldSelection(
    fields={'name'},
    relationships={
        'posts': FieldSelection(fields={'title'}, relationships={})
    }
)

# ══════════════════════════════════════════════════════════
# Step 2: 对 User 构建（递归第一层）
# ══════════════════════════════════════════════════════════
# valid_fields = {'name'}
# relationships = {'posts': ...}
#
# → load_only(User.id, User.name)  # id 自动加入
# → 递归处理 posts...

# ══════════════════════════════════════════════════════════
# Step 3: 对 Post 构建（递归第二层）
# ══════════════════════════════════════════════════════════
# valid_fields = {'title'}
# relationships = {}
#
# → load_only(Post.id, Post.title)

# ══════════════════════════════════════════════════════════
# Step 4: 组装最终结果
# ══════════════════════════════════════════════════════════
[
    load_only(User.id, User.name),
    selectinload(User.posts).options(
        load_only(Post.id, Post.title)
    )
]

# ══════════════════════════════════════════════════════════
# 最终使用
# ══════════════════════════════════════════════════════════
stmt = select(User).options(*options)
# 等价于:
# select(User).options(
#     load_only(User.id, User.name),
#     selectinload(User.posts).options(
#         load_only(Post.id, Post.title)
#     )
# )
```

---

## 缓存策略

| 缓存 | 键 | 作用域 | 目的 |
|------|-----|--------|------|
| `_metadata_cache` | `model_class` | 实例级 | 避免重复访问 SQLAlchemy mapper |
| `parse_query_string_cached` | `query_string` | 全局 (`@lru_cache`) | 相同语法只解析一次 |
| `_options_cache` | `{module}.{Class}:{query}` | 实例级 | 相同 (模型, 查询) 直接返回 |

### 缓存设计优势

1. **初始化时**：一次性预热所有模型元数据
2. **解析时**：相同 query string 跨实例共享解析结果
3. **生成时**：相同请求直接返回，无需重复构建

---

## 异常处理

| 异常 | 触发场景 |
|------|----------|
| `ParseError` | 语法错误（缺括号、空选择等） |
| `FieldNotFoundError` | 字段不存在 / 把普通字段当 relationship 用 |
| `RelationshipNotFoundError` | 关系不存在 / 忘记加 `{}` |

---

## 设计决策

### 为什么用 `selectinload` 而不是 `joinedload`？

- `selectinload` 使用 IN 查询，避免 JOIN 产生的笛卡尔积
- 对于一对多、多对多关系更高效
- 生成的 SQL 更易读和调试

### 为什么自动包含主键？

- SQLAlchemy 需要主键来正确构造对象实例
- 避免因缺少主键导致的会话管理问题

### 为什么 Parser 与 Generator 分离？

- Parser 是纯语法解析，不依赖 SQLAlchemy
- 可以独立测试和复用
- 解析缓存可以跨不同模型共享
