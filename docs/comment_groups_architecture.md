# Comment Groups Architecture

**Last Updated:** 2025-10-05
**Status:** Design Complete, Implementation Pending

## Overview

Система поиска релевантных групп комментариев работает параллельно с основным поиском по постам. Позволяет находить ценные обсуждения в комментариях, даже если сам пост нерелевантен запросу.

## Core Concept

### Проблема
Комментарии под постами в Telegram часто переходят на другие темы (off-topic). Эти обсуждения могут содержать ценную информацию, которую невозможно найти через поиск по постам.

### Решение
**Двойной параллельный поиск:**
1. **Pipeline A (Posts)**: Map → Resolve → Reduce → Answer
2. **Pipeline B (Comment Groups)**: Map по группам комментариев → Релевантные группы

### Ключевое Отличие от Других Подходов
- ❌ Комментарии **НЕ участвуют** в генерации финального ответа
- ✅ Показываются как **отдельный результат** для ручного изучения
- ✅ Важный кейс: **нерелевантный пост + релевантные комментарии**

## Architecture Diagram

```
User Query: "Что автор думает про AI агентов?"
           ↓
┌──────────────────────────────────────────────────────┐
│ ПАРАЛЛЕЛЬНЫЕ PIPELINE                                │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Pipeline A (Posts):                                 │
│  ┌──────┐   ┌─────────┐   ┌────────┐               │
│  │ Map  │ → │ Resolve │ → │ Reduce │               │
│  └──────┘   └─────────┘   └────────┘               │
│  Result:                                             │
│  - Answer: "Я тестировал CrewAI..."                 │
│  - main_sources: [5, 12, 18]                        │
│  - relevant_post_ids: [5, 7, 12, 18] (HIGH+MEDIUM)  │
│                                                      │
│  Pipeline B (Comment Groups):                        │
│  ┌──────┐                                            │
│  │ Map  │ (по группам комментариев)                 │
│  └──────┘                                            │
│  Input: exclude_post_ids = [5, 7, 12, 18]           │
│  Result:                                             │
│  - Group(post=3): 15 комментариев HIGH              │
│  - Group(post=9): 8 комментариев MEDIUM             │
│                                                      │
└──────────────────────────────────────────────────────┘
           ↓
    Frontend Display:

    ┌─────────────────────────────────────────────┐
    │ ANSWER (из постов 5, 12, 18)                │
    └─────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────┐
    │ RELEVANT POSTS: [5] [7] [12] [18]           │
    │  ↳ Клик → Telegram → читать комментарии     │
    └─────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────┐
    │ RELEVANT COMMENT GROUPS (уникальные)        │
    │                                             │
    │  📌 Post #3 (нерелевантный, но якорь)      │
    │     └─ 💬 15 комментариев про AI агентов   │
    │        Клик → Telegram comments             │
    │                                             │
    │  📌 Post #9 (нерелевантный, но якорь)      │
    │     └─ 💬 8 комментариев релевантны        │
    │        Клик → Telegram comments             │
    └─────────────────────────────────────────────┘
```

## Deduplication Logic

### Проблема Дублирования
- Pipeline A находит посты [5, 7, 12, 18] (релевантные)
- Pipeline B может найти группы комментариев к [3, 5, 7, 9, 12]
- Посты 5, 7, 12 дублируются → пользователь видит их дважды
- Комментарии к 5, 7, 12 уже доступны через клик на пост!

### Решение: Exclude Before Processing

**Исключаем `relevant_post_ids` (не `main_sources`):**

```python
# Pipeline A
relevant_post_ids = [5, 7, 12, 18]  # HIGH + MEDIUM из Map
main_sources = [5, 12, 18]          # Финальные источники из Reduce

# Pipeline B: исключаем relevant_post_ids
comment_groups = process_comment_groups(
    exclude_post_ids=relevant_post_ids  # Исключить ВСЕ релевантные
)
# Результат: только группы к постам [3, 9]
```

**Почему `relevant_post_ids`, а не `main_sources`:**
- Пользователь может кликнуть на **любой** релевантный пост (даже MEDIUM)
- Даже если пост не попал в `main_sources`, комментарии к нему доступны
- `relevant_post_ids` = полный список постов, к которым комментарии доступны

### Example Flow

```
Map Phase Results:
  Post 3: LOW      → не релевантен
  Post 5: HIGH     → релевантен
  Post 7: MEDIUM   → релевантен
  Post 9: LOW      → не релевантен
  Post 12: HIGH    → релевантен
  Post 18: HIGH    → релевантен

relevant_post_ids = [5, 7, 12, 18]

Reduce Phase:
  main_sources = [5, 12, 18]  # Post 7 не попал в финальный ответ

Comment Groups Processing:
  Group(post=3):  ✅ Обрабатываем (3 не в relevant_post_ids)
  Group(post=5):  ❌ SKIP (5 в relevant_post_ids)
  Group(post=7):  ❌ SKIP (7 в relevant_post_ids - комментарии доступны!)
  Group(post=9):  ✅ Обрабатываем (9 не в relevant_post_ids)
  Group(post=12): ❌ SKIP (12 в relevant_post_ids)

Map Results:
  Group(post=3): HIGH  → релевантные комментарии про AI
  Group(post=9): LOW   → не релевантно

Final Comment Groups: [Group(post=3)]
```

## Database Schema

### New Table: telegram_comments

```python
class TelegramComment(Base):
    """Комментарии из Telegram Discussion Group или replies."""

    __tablename__ = "telegram_comments"

    # Primary key
    telegram_comment_id = Column(Integer, primary_key=True)

    # Якорь к посту
    parent_post_id = Column(Integer, ForeignKey("posts.post_id"), nullable=False, index=True)
    parent_telegram_message_id = Column(Integer, nullable=False)

    # Содержимое
    content = Column(Text, nullable=False)
    author = Column(String(255))
    author_id = Column(String(255))

    # Timestamps
    created_at = Column(DateTime)

    # Relationship
    parent_post = relationship("Post", backref="telegram_comments")

    # Indexes
    __table_args__ = (
        Index('idx_parent_post', 'parent_post_id'),
        Index('idx_parent_telegram', 'parent_telegram_message_id'),
    )
```

## Backend Implementation

### 1. Comment Group Map Service

```python
# backend/src/services/comment_group_map_service.py

class CommentGroupMapService:
    """Map service для поиска релевантных ГРУПП комментариев."""

    DEFAULT_CHUNK_SIZE = 20  # Групп комментариев

    def _group_comments_by_post(
        self,
        db: Session,
        exclude_post_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Группирует комментарии, исключая указанные посты."""

        query = db.query(
            TelegramComment,
            Post.telegram_message_id,
            Post.content
        ).join(
            Post,
            TelegramComment.parent_post_id == Post.post_id
        )

        # Исключить релевантные посты из Pipeline A
        if exclude_post_ids:
            query = query.filter(
                Post.telegram_message_id.notin_(exclude_post_ids)
            )

        # ... группировка ...
```

### 2. Query Endpoint Update

```python
# backend/src/api/simplified_query_endpoint.py

async def process_query_streaming(...):
    # Pipeline A: Posts
    post_results = await map_service.process_posts(...)

    # Собрать relevant_post_ids (HIGH + MEDIUM)
    relevant_post_ids = [
        r["telegram_message_id"]
        for r in post_results
        if r["relevance"] in ["HIGH", "MEDIUM"]
    ]

    # Reduce
    answer_data = await reduce_service.synthesize_answer(...)

    # Pipeline B: Comment Groups (с исключениями)
    if request.include_comment_search:
        comment_groups = await comment_map_service.process_comment_groups(
            query=request.query,
            db=db,
            exclude_post_ids=relevant_post_ids,  # Дедупликация
            progress_callback=progress_callback
        )
    else:
        comment_groups = []

    return {
        "answer": answer_data["answer"],
        "main_sources": answer_data["main_sources"],
        "relevant_comment_groups": comment_groups,
        "comment_groups_count": len(comment_groups)
    }
```

### 3. Prompt Template

```
# backend/prompts/comment_group_map_prompt.txt

You are analyzing GROUPS OF COMMENTS from a Telegram channel.
Each group contains all comments under one post (the "anchor post").

CRITICAL: The anchor post itself may be IRRELEVANT to the query.
Your task is to score the COMMENTS in each group, NOT the post.

USER QUERY: $query

COMMENT GROUPS:
$groups

For each group, evaluate:
1. Do the COMMENTS discuss topics related to the query?
2. Ignore the anchor post content - focus ONLY on comments
3. Score: HIGH (directly answers), MEDIUM (related), LOW (unrelated)

Return JSON array:
[
  {
    "parent_telegram_message_id": <post_id>,
    "relevance": "HIGH|MEDIUM|LOW",
    "reason": "<why comments are relevant>",
    "comments_count": <number>
  }
]
```

## Frontend Implementation

### New Component: CommentGroupsList

```tsx
// frontend/src/components/CommentGroupsList.tsx

interface CommentGroupsListProps {
  commentGroups: CommentGroupResponse[];
}

export const CommentGroupsList: React.FC<CommentGroupsListProps> = ({
  commentGroups
}) => {
  if (commentGroups.length === 0) {
    return null;
  }

  return (
    <div>
      <h3>💬 Релевантные группы комментариев ({commentGroups.length})</h3>

      {commentGroups.map((group) => (
        <div key={group.parent_telegram_message_id}>
          {/* Пост-якорь */}
          <div>
            📌 Пост #{group.parent_telegram_message_id}
            <p>{group.anchor_post.content}</p>
          </div>

          {/* Комментарии */}
          <div>
            💬 {group.comments_count} релевантных комментариев
            <a href={`https://t.me/channel/${group.parent_telegram_message_id}?comment=1`}>
              Открыть в Telegram →
            </a>
          </div>

          <div>{group.reason}</div>
        </div>
      ))}
    </div>
  );
};
```

## Implementation Checklist

### Phase 1: Database & Import (2-3 hours)
- [ ] Create `telegram_comments` table
- [ ] Implement `TelegramComment` model
- [ ] Export Telegram Discussion Group
- [ ] Write `TelegramCommentsParser`
- [ ] Import comments to DB

### Phase 2: Backend Service (3-4 hours)
- [ ] Create `CommentGroupMapService`
- [ ] Write `comment_group_map_prompt.txt`
- [ ] Implement deduplication logic
- [ ] Add tests

### Phase 3: API Integration (2-3 hours)
- [ ] Update `QueryRequest` (add `include_comment_search`)
- [ ] Update `QueryResponse` models
- [ ] Integrate Pipeline B in endpoint
- [ ] Test parallel execution

### Phase 4: Frontend (3-4 hours)
- [ ] Create `CommentGroupsList` component
- [ ] Update TypeScript types
- [ ] Integrate in `App.tsx`
- [ ] Add Telegram links

### Phase 5: Testing (2-3 hours)
- [ ] Test with real queries
- [ ] Validate deduplication
- [ ] Update documentation

**Total:** 12-17 hours

## Key Design Decisions

### ✅ What We Decided

1. **Parallel Pipelines** - Comment groups separate from answer
2. **Exclude Before Processing** - Filter `relevant_post_ids` early
3. **Show Anchor Post** - Context even if irrelevant
4. **Optional Feature** - `include_comment_search` parameter

### ❌ What We Rejected

1. **Comments in Reduce** - Would pollute answer
2. **Comments as Mini-Posts** - Too much noise
3. **Post-filtering** - Wastes tokens

## Example Use Case

**Query:** "AI агенты"

**Scenario:**
- Post #50: "Запустил подкаст" (LOW)
- Comments: обсуждение AI агентов (15 комментариев)

**Result:**
```
Pipeline A: Posts [12, 18, 25] → Answer
Pipeline B: Group(post=50) → 15 комментариев (HIGH)

Frontend:
  Answer + Sources [12, 18, 25]
  Comment Groups: Post #50 → 15 комментариев
```

## Future Enhancements

1. Embeddings for semantic search
2. Comment threading visualization
3. Sentiment analysis
4. Auto-summarization

## References

- Main docs: `/CLAUDE.md`
- Services: `/backend/src/services/`
- Components: `/frontend/src/components/`
