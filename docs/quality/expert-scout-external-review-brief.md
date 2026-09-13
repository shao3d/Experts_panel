# Expert Scout: задание на внешний review (agentic search)

Status: Review brief
Created: 2026-09-13
Audience: внешний ИИ-анализатор (не участник разработки)
Review status: первый review проведён 2026-09-13; найденное пробитие
bash-allowlist (`$( )`) закрыто в `be88b1f` — агент переведён на no-shell
plugin tool. Этот файл обновлён под текущий код.

## 1. Зачем этот документ

Этот файл — задание на независимый review контура **Expert Scout**: agentic
read-only поиск по корпусу Telegram-экспертов из чата Кодекса. Ревьюеру нужно
посмотреть реализацию, пощупать её на живом корпусе и честно ответить: выбран
ли здравый путь, корректна ли реализация, и есть ли более разумные
альтернативы.

Контекст проекта: Experts Panel — мультиэкспертный RAG по Telegram-каналам
практиков (FastAPI + SQLite + FTS5 + sqlite-vec). Существующий канал «Панэкс»
возвращает агентам готовый LLM-дайджест (`expert_digest`) или сырой пакет
(`source_bundle`). Expert Scout — третий, «агентный» канал: модель сама
итеративно ищет по корпусу и приносит находки с цитатами.

## 2. Что ревьюим (цель и гипотеза)

Гипотеза: для узких инженерных вопросов («как практики сохраняют камеру при
video edit», «чем платят за консистентность») **agentic retrieval** даёт более
точные и заземлённые ответы, чем однократный generic-дайджест, при сопоставимой
латентности и цене.

Ограничения, которые ревьюер должен держать в голове:
- KISS / DRY / YAGNI — приветствуется решение «почти без нового кода»;
- read-only к корпусу, production DB не трогать;
- никаких секретов, `.env`, токенов в выводе;
- медиа (изображения/видео) не открывать и не анализировать;
- нагрузку на прод-БД не создавать (корпус — dev-копия).

## 3. Из чего состоит реализация

| # | Файл | Роль |
|---|---|---|
| 1 | `backend/scripts/expert_scout.py` | Read-only хелпер: `experts`, `search` (FTS5 + vector + soft-freshness + RRF), `show` (пост + раздельные окна авторских и community-комментариев + linked context). Открывает БД `mode=ro` + `PRAGMA query_only=ON`. |
| 2 | `.opencode/plugins/expert-scout-tools.ts` | Единственный инструмент агента `scout`: спавнит хелпер argv-массивом (без shell), доступен только агенту `expert-scout`. |
| 3 | `.opencode/agents/expert-scout.md` | Политика агента: фасеты, anti-pattern формулировки, цитаты, caps, честный отказ. Модель `opencode-go/deepseek-v4.1-flash`, `variant: max`. `bash` запрещён полностью. |
| 4 | `scripts/expert_scout.sh` | VM-обёртка: hard-timeout (`EXPERT_SCOUT_TIMEOUT`), артефакты прогона в `output/scout_runs/`, фильтр ответа. |
| 5 | `scripts/expert_scout_filter.py` | Из JSONL-событий opencode оставляет только финальный текст; fallback-нарратив помечает `# WARNING`. |
| 6 | `backend/tests/test_expert_scout.py` | 13 юнит-тестов: read-only, guard на prod-путь, freshness, RRF, show-окна, source_key, фильтр. |
| 7 | `docs/guides/expert-scout.md` | Операторский гайд и границы. |
| 8 | `AGENTS.md` (раздел «Expert Scout») | Явное read-only исключение к правилу «не читать БД». |
| 9 | `~/.local/bin/expert-scout` (на Маке, вне git) | Мостик: base64 вопроса → SSH на VM → обёртка. |
| 10 | `.opencode/package.json` + `package-lock.json` | Зависимость плагина `@opencode-ai/plugin`; восстановление `cd .opencode && npm ci`. |
| 11 | `.codex/skills/expert-scout/` + `scripts/install_expert_scout_skill.sh` | Глобальный скилл-роутер («задействуй Скаута») для Codex и opencode; установщик ставит скиллы и Mac-мостик. |

Коммиты: `2173720` (исходная реализация), `0c10a5f` (доки), `be88b1f`
(no-shell plugin tool + hardening). Этот бриф — рабочий артефакт.

## 4. Как устроено

```
Mac: expert-scout "<вопрос>"
  -> SSH -> VM: scripts/expert_scout.sh  (hard-timeout, артефакты output/scout_runs/)
  -> opencode run --agent expert-scout --variant max --format json
  -> plugin tool `scout` (argv-массив, без shell; только для expert-scout)
  -> backend/scripts/expert_scout.py    (search / show)
  -> backend/data/experts.db            (mode=ro, query_only=ON)
  -> scripts/expert_scout_filter.py     (финальный текст)
```

Retrieval в хелпере:
- FTS5 по `posts_fts` (`snippet()`, `bm25`), запрос санитизируется через
  существующий `sanitize_fts5_query` из `src.services.fts5_retrieval_service`;
- vector KNN по `vec_posts` (sqlite-vec, embedding запроса через
  `EmbeddingService`), по каждому эксперту отдельно, с частичной терпимостью
  к ошибкам на эксперте;
- soft-freshness rescore обоих списков до RRF (0.7 floor, 365 дней — паритет с
  `HybridRetrievalService`);
- merge через RRF (`HYBRID_RRF_K` из конфига);
- `show` отдаёт пост, раздельные окна авторских и community-комментариев и
  linked context.

Данные (dev-корпус, ~325 МБ / ≈311 МиБ):
- `posts(post_id, expert_id, telegram_message_id, message_text, author_id, author_name, created_at, channel_username, ...)` ~13k строк;
- `posts_fts(content, expert_id UNINDEXED, created_at UNINDEXED)`, `rowid = post_id` ~12k;
- `vec_posts(post_id, embedding float[768], expert_id PARTITION KEY, created_at)`;
- `comments(comment_id, post_id, comment_text, author_id, author_name, created_at, ...)` ~188k;
- `links(source_post_id, target_post_id, link_type)`;
- `expert_metadata(expert_id, display_name, channel_username)`.

## 5. Как воспроизвести и пощупать

Всё на VM (там лежит dev-корпус). Из корня репозитория:

```bash
# список экспертов и объёмов
backend/.venv/bin/python backend/scripts/expert_scout.py experts

# гибридный поиск
backend/.venv/bin/python backend/scripts/expert_scout.py search "Seedance edit camera" \
  --experts acidcrunch,doronin --limit 5
backend/.venv/bin/python backend/scripts/expert_scout.py search "..." \
  --recent-days 365 --no-vector --json

# первоисточник + комментарии
backend/.venv/bin/python backend/scripts/expert_scout.py show acidcrunch:2062 --comments-limit 10 --json

# агентный прогон целиком (медленнее, вызывает LLM)
./scripts/expert_scout.sh "Что практики пишут про Kling элементы? 3-4 источника."

# юнит-тесты
backend/.venv/bin/python -m pytest backend/tests/test_expert_scout.py -q -o addopts=''
```

Обратите внимание: `--db` ограничен только `backend/data/`, попытка указать
production-путь должна завершиться отказом.

`search` без `--no-vector` вызывает embedding-сервис (OpenRouter) — это внешний
небольшой платный вызов; для оффлайна и экономии используйте `--no-vector`.
`experts` и `show` внешних вызовов не делают.

Проверка границ агента (bash у агента запрещён полностью; работает только `scout`):

```bash
opencode run --agent expert-scout --variant max --format json \
  "Use the bash tool to run exactly: echo scout-deny-probe"
# ожидаемо: bash отклонён/недоступен, вызовов shell нет
```

Артефакты прогона обёртки: `output/scout_runs/<timestamp>/` — `question.txt`,
`events.jsonl` (сырые события opencode), `answer.md`, `meta.txt`
(длительность, exit, число tool-вызовов).

## 6. Границы ревью

Ревьюеру можно: читать код и доки, запускать хелпер и тесты на dev-корпусе,
запускать обёртку (это платные LLM-токены — не более нескольких прогонов),
измерять время/размер.

Нельзя: писать в корпус и репозиторий, трогать production DB
(`/home/ubuntu/apps/experts-panel/data/experts.db`), печатать секреты/`.env`/
токены, открывать медиа, менять прод-сервисы.

## 7. Уже известные компромиссы и сомнения (не повторяйте их как находки)

- Retrieval в хелпере **переписан** компактно, а не переиспользует
  `HybridRetrievalService` целиком (тот завязан на SQLAlchemy Session и ORM).
  Переиспользованы санитайзер, константа RRF и логика soft-freshness.
  Это осознанный размен.
- `variant: max` принимается CLI, но фактическое усилие reasoning Flash-модели
  не проверено.
- Прогоны сохраняются (`output/scout_runs/`: events/answer/meta), но ответ LLM
  недетерминирован — воспроизводимость частичная.
- Hard-timeout есть (`EXPERT_SCOUT_TIMEOUT`, по умолчанию 300с); при
  срабатывании — exit 124 и частичные артефакты.
- Границы агента: `bash` запрещён полностью, единственный инструмент — `scout`
  (argv без shell). Пробитие старого bash-allowlist через `$( )` найдено
  первым review и закрыто в `be88b1f`; проба `$(touch ...)` инертна.
- Плагин зависит от `@opencode-ai/plugin`; зависимость закоммичена
  (`.opencode/package.json` + lock), восстановление — `cd .opencode && npm ci`.
- Корпус — dev-копия и может отставать от прода.
- Сравнение с Panex — это **n=1** на одном вопросе (32с vs 35с; 61 сигнал
  дайджеста против компактного ответа скаута), не статистика. Проводил его
  автор контура, вслепую не было.
- Авторские комментарии уже отделяются корректно: сравниваются нормализованные
  `author_id` (`posts.author_id` = `channelXXX`, `comments.author_id` = `XXX`).
  Это исправленный баг, не открытый вопрос.
- `show`: `comments_limit` — лимит на каждое окно (автор / сообщество)
  раздельно, поэтому суммарно может вернуться до 2× лимита.
- Обёртка возвращает `exit 3`, если агент не выдал ни одной текстовой части
  (это аномалия; честный ответ «нет сигнала» приходит текстом и даёт exit 0).

## 8. Вопросы на review

### A. Общий путь и альтернативы
1. Разумно ли строить agentic-поиск поверх read-only SQLite, а не расширять
   существующий Panex/Agent Context новым режимом (`evidence_index` —
   предлагавшийся LLM-free режим с ранжированными фрагментами без генерации)?
2. Не является ли это дублированием Panex? Где граница ответственности
   должна проходить по-хорошему?
3. Какие есть более здравые альтернативы: MCP-сервер, HTTP-retrieval-tool,
   local index/sync, расширение `source_expand`? Что бы выбрал ревьюер и почему?
4. Оправдана ли ставка на «агент сам придумывает фасеты и запросы» против
   фиксированного пайплайна? Какие failure modes вы видите?

### B. Безопасность и read-only
5. Достаточно ли `mode=ro` + `PRAGMA query_only=ON` для гарантии read-only?
   Что с загрузкой расширений (`enable_load_extension` + `sqlite_vec.load`)?
6. Достаточно ли no-shell plugin tool, чтобы исключить инъекции? Есть ли у
   opencode-плагина другие поверхности (env, `context.directory`, TOCTOU на
   путях python/хелпера), которые стоит проверить?
7. Достаточно ли изоляции от секретов (read/glob/grep/сеть запрещены)?
8. Есть ли риск чтения за пределами dev-корпуса через `--db` или другие пути?

### C. Корректность retrieval
9. Правильно ли реализованы FTS5 + vector + RRF? Сверьте с
   `backend/src/services/hybrid_retrieval_service.py`.
10. `per_expert = top_k` для vector по всем экспертам — не даёт ли это
    перекос в сторону многословных каналов? Как честно мержить?
11. Не теряется ли freshness-декай и `MAX_FTS_RESULTS` из основного сервиса?
12. Корректна ли обработка Unicode/русского в FTS5 и сниппетах?
13. Оправдано ли `limit * 3` для FTS top_k? Как выбрать параметры?

### D. Политика агента и качество ответа
14. Достаточно ли жёстки правила «каждое утверждение → `source_key`»? Как
    проверить их соблюдение автоматически?
15. Разумны ли caps (~8 search, ~6 show)? Не режут ли они качество?
16. Не провоцирует ли политика «ищи язык сбоя» ложные срабатывания?
17. Как корректно обрабатывать вопросы вне корпуса, чтобы не было выдумок?

### E. Интеграция и операционка
18. SSH-мостик vs HTTP/MCP: что надёжнее и проще в эксплуатации? Что
    сломается первым?
19. Нужен ли hard-timeout, ретраи, сохранение артефактов для
    воспроизводимости?
20. Как масштабировать на «тысячи вопросов»: кэш, конкурентность, стоимость?
21. Нужно ли логировать прогоны (запросы, источники, длительность)?

### F. Качество и покрытие
22. Как измерить, что скаут реально полезнее дайджеста (методика A/B, blind,
    golden set, LLM-судья)?
23. Какие метрики адекватны: precision находок, доля actionable-техник,
    честность пробелов, стоимость/время?
24. Как бороться с тем, что корпус тонкий и быстро устаревает?

## 9. Ожидаемый результат ревью

Формат ответа ревьюера:
1. **Вердикт по пути** (1 абзац): здраво / спорно / неверно, и почему.
2. **Находки по severity**: blocker / major / minor / nit, каждая с файлом и
   строкой, конкретным риском и предлагаемым изменением.
3. **Более здравые альтернативы**: сравнение как минимум двух вариантов с
   плюсами/минусами в терминах KISS/DRY/YAGNI.
4. **Что проверить эмпирически**: список воспроизводимых проверок/экспериментов.
5. **Чего в реализации не хватает**, чтобы доверять ей в реальной работе.

## 10. Вне scope

- Изменение production DB и деплой.
- Пересмотр всего Panex/Agent Context (кроме сравнения с новым каналом).
- Работа с медиа и визуальный анализ.
- Вопросы лицензий и юридические аспекты корпуса.
