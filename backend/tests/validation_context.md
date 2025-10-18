# Validation Context for Experts Panel Testing
Date: 2025-09-30

## Testing Strategy
We test DIRECTLY from Claude (not subagents) because:
- Full project context for deep analysis
- Compare system vs independent analysis
- Interactive refinement

## Current System
- Model: Gemini 2.5 Flash
- Chunk: 40 posts
- Database: 153 posts (Refat, Mar-Sep 2025)

## 12 Test Queries

1. "Какие AI инструменты для кодинга обсуждает автор?"
2. "Как получать ресурсы от Big Tech компаний?"
3. "Главные новости из #ReDigest дайджестов?"
4. "AI в юридической сфере и Legal Tech?"
5. "Митинги vs асинхронная работа?"
6. "Что такое vibe coding и pet-проекты?"
7. "Эволюция отношения к AI агентам?"
8. "OSINT+AI для бизнес-задач?"
9. "История Джона без опыта кодинга?"
10. "Блокчейн и криптовалюты?" (negative)
11. "Что такое AX (Agent Experience)?"
12. "Платформы для отслеживания трендов?"

## Previous Results
- Score: 8.7/10
- Precision: 87%, Recall: 72%

## Next Session
Start by discussing these queries!