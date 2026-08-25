# Reddit Search: полная ревизия сайдкара и план апгрейда синтеза

> **Дата:** 25.08.2026 · **Статус:** план выполнен. Шаг 1 — age/channel в
> контексте + обязательная таблица / «Куда идти» / маркировка достоверности.
> Шаг 2 — бюджет комментариев (топ-K корней по score, кап на источник,
> стоп между корнями). Шаг 3 — телеметрия finish_reason/chars/sources +
> автоэскалация: length-truncation → один перезапрос с 2x max_tokens.
> Дальнейшее (поднятие базового REDDIT_SYNTH_MAX_TOKENS) — только по данным
> телеметрии
> **Назначение:** хэндофф-документ. Прочитать целиком перед любой работой над
> Reddit-поиском в панели. Содержит полную историю ревизии, текущую архитектуру,
> живые эксперименты с выводами и детальный план улучшения качества синтеза.

---

## 0. TL;DR

Сайдкар поиска по Reddit (`services/reddit-proxy`, Fastify/TS на VM) полностью
переписан: MCP-слой удалён → прямой OAuth к Reddit API; добавлены каналы
дискавери Arctic Shift и Serper.dev (Google); снят proxy-level score-гейт;
внедрены рейтлимит-гигиена и честное обогащение; легаси вычищено (~2400 строк).
Каналы работают, e2e подтверждён.

**Следующая ступенька** — качество СИНТЕЗА ответа (`reddit_synthesis_service.py`):
найдены конкретные перекосы (нет возраста тредов и происхождения в контексте,
комментарии без бюджета, max_tokens вслепую) и пробелы промпта (нет обязательной
сравнительной таблицы с числами, нет action-block «Куда идти», нет маркировки
достоверности). Детальный план — раздел 7.

---

## 1. Хронология ревизии (что было → что стало)

| Было | Стало | Коммит |
|---|---|---|
| Поиск через stdio-MCP `reddit-mcp-buddy` | Прямой OAuth `oauth.reddit.com/search` | серия |
| Глобальные top/new каналы (шумовая пушка) | top/new только внутри таргетных сабов | `5aaab8a` |
| Мёртвый Fly.io URL в бэкенде | `REDDIT_PROXY_URL` в config.py (`http://reddit-proxy:3000`) | до `58ca25d` |
| UI-тумблер Reddit скрыт | `REDDIT_SEARCH_VISIBLE = true` | до `58ca25d` |
| Abstain помечался ошибкой | `skipped` / «no relevant threads» | до `58ca25d` |
| Креды Reddit хардкодом в `reddit_client.py` | env-based; файл удалён entirely | `58ca25d` |
| Обогащение топ-12 при реранке 18 | 18 + форс внешних snippet-only кандидатов | `1cccdce` |
| Нет рейтлимит-логики | чтение X-Ratelimit-*, гейт, бэкофф 429, jitter, single-flight токен | `709d70e` |
| Google CSE канал | удалён (API закрыт для новых проектов); вместо него **Serper.dev** | `ac32251` |
| Нет Arctic Shift | канал исчерпывающего архива по таргет-сабам | `476bef1` |
| Легаси V1-ветка (~320 строк), TECH_SUBREDDITS, флаг V2 | удалены; только V2 | `ad54e40` |
| Sidecar score≥5 гейт | убран (recall@retrieval, precision@rerank) | `a1f1b70` |

Плюс вне Reddit: удалены мёртвые Fly-workflows, `fly.toml`, FLY_* из `.env.panel`;
доки синхронизированы; в гайдах fly.dev → `expa.beyondhorizon.dev`.

## 2. Текущая архитектура

```
Scout (MODEL_SCOUT=gemini-3.1-flash-lite, temp=0)
  └─ intent/subreddits/queries/keywords/time_filter
Каналы кандидатов (все параллельно):
  ├─ нативные relevance ×5 (literal/expanded/scout global + targeted literal/scout)
  ├─ native top/new — ТОЛЬКО внутри таргетных сабов
  ├─ arctic_targeted_archive — title+selftext в топ-2 сабах (Arctic Shift, бесплатно)
  └─ serp_google_discovery — Serper.dev, site:reddit.com через настоящий Google
       ↓ дедуп по id → recent_only пост-фильтр (90д; serper-кандидаты без даты exempt)
       ↓ эвристика _score_post_v2 (+антиспам: SPAM_TITLE_PATTERNS, саб-репутация,
         engagement-starved combo)
       ↓ честное обогащение: топ-18 (=RERANK_CANDIDATES) + форс undated-discovery,
         cap 36 вызовов /details (100 комм., depth 5)
       ↓ AI-rerank (18): MODEL_ANALYSIS (lite); comparison-intent → MODEL_SYNTHESIS.
         В контексте каждой строки: Engagement score/comments + правила SEO-bait
       ↓ confidence gates 0.52/0.44 (+anchor gates для comparison)
       ↓ abstain = graceful skip («no relevant threads»), НЕ ошибка
Синтез (RedditSynthesisService, MODEL_SYNTHESIS, temp=0.3, max_tokens=REDDIT_SYNTH_MAX_TOKENS=4096
с одним автоперезапросом на 2x при finish_reason=length):
  контекст = топ-10 источников × (selftext ≤8000 симв + дерево комментов depth≤3,
  body≤2000 симв/коммент, теги [OP]/[MOD]/flair)
```

**Ключевые файлы:**
- Сайдкар: `services/reddit-proxy/src/index.ts` (~660 строк после чистки)
- Оркестратор: `backend/src/services/reddit_enhanced_service.py`
- Синтез: `backend/src/services/reddit_synthesis_service.py`
- Пайплайн-вход: `backend/src/api/simplified_query_endpoint.py`
  → `process_reddit_pipeline()` (строка ~825), fallback-markdown `_build_reddit_markdown()`
- Конфиг: `backend/src/config.py` (блоки Reddit Search / Arctic / Serper)
- UI-флаги: `frontend/src/config/expertConfig.ts` → `REDDIT_SEARCH_VISIBLE = true`

## 3. Инфраструктура (без секретов)

- **VM:** Oracle ARM `oracle-marseille-arm-dev`, прод = docker compose
  `~/apps/experts-panel/docker-compose.vm.yml` (файл ВНЕ git-репо!)
  - сервисы: `panel` (:8000), `reddit-proxy` (:3000, localhost-only), `caddy`
- **Секреты:** `~/apps/experts-panel/.env.panel` (ADMIN_SECRET, OPENROUTER_API_KEY,
  SERPER_API_KEY, TELEGRAM_*, VERTEX_AI_SERVICE_ACCOUNT_JSON — ⚠️ SA мёртв,
  `account not found`, эмбеддинги Vertex могут не работать — отдельный долг);
  `~/apps/experts-panel/.env.proxy` (REDDIT_CLIENT_ID/SECRET/USERNAME/PASSWORD,
  USER_AGENT — формат без кавычек, `source` ломается, парсить grep'ом)
- **Репо:** github.com/shao3d/Experts_panel — ПУБЛИЧНЫЙ. Старый пароль Reddit-акка
  остался в git-истории (ротация отложена юзером; риск принят). Не коммитить секреты!
- **CI:** push в main → deploy-oracle.yml пересобирает всё через compose; ci.yml гоняет тесты
- **Arctic Shift API:** `https://arctic-shift.photon-reddit.com/api/posts/search`
  (title/selftext требуют subreddit|author; after принимает `90d`; был случай
  422 «Timeout» — канал молча деградирует)

## 4. Живые эксперименты и выводы (не повторять открытие!)

1. **Нативный Reddit ищет нормально ТОЛЬКО sort=relevance.** top/new игнорируют
   запрос → глобальные top/new каналы были источником «качелей» качества. A/B
   доказано прямым OAuth.
2. **Мультисаб OAuth-путь `/r/a+b/search` требует `%2B`**: сырой `+` даёт 301 на
   главную. До фикса таргетинг молча возвращал пустоту.
3. **Google CSE закрыт для новых проектов** (наша ошибка 403 воспроизводится у
   всех новых аккаунтов; закат сервиса 01.2027). Никакие роли/ключи не помогают.
   Рекомендованная замена — Vertex AI Search (тяжело) или Serper (сделано).
4. **PullPush мёртв для свежего:** инжест встал ~май 2025 (замерено: «свежие»
   записи = 15 мес). Не использовать.
5. **Arctic Shift жив и свеж** (посты 6-мин давности), но полнотекст только
   внутри саба. Реальный пик VRAM H3 ≈ 31.8GB независимо от размера файла —
   замер сообщества на RTX 5090.
6. **Serper.dev работает отлично:** стабильные 7–8 кандидатов/запрос, 1 кредит
   за ≤10 результатов, free tier 2500. Ключ уже в `.env.panel`.
7. **Оценка качества реранка зависит от модели:** на adversarial-кверчах
   (comparison) lite-модель ведётся на vs-bait; escalation до SYNTHESIS решил.
8. **Standalone-скрипты глотают INFO-логи** — `logging.basicConfig(level=INFO)`
   обязателен в eval-скриптах, иначе кажется, что обогащение не работает.

## 5. АНАЛИЗ СИНТЕЗА (главное для следующего шага)

Цель: довести ответы панели по полноте/анализу/таблицам/выводам до уровня
хороших агентских ответов (эталон — ответы ассистента в сессии 25.08: таблицы
с числами и источниками строк, action-block «Куда идти», маркировка достоверности).

### 5.1 Разумно — НЕ трогать
- Скелет RU/EN Staff Engineer: ExecSummary / Deep Dive / Minority Report /
  Battle-tested Edge Cases + style rules
- Правила достоверности: [✅ OP VERIFIED], доверие flair, скепсис к скорам,
  LINK PRIORITY, PIVOT ALERT, relevance gate
- Билингвальность: query_language → RU-промпт («отвечай только на русском»)
  / EN-промпт; перевод запроса RU→EN перед поиском (flash-lite)
- Дерево комментариев: вложенность до depth 3, [OP]/[MOD]/flair/distinguished,
  body ≤2000 символов
- Капы: max_sources_in_context=10, 8000 символов selftext/источник

### 5.2 Перекошено — конкретика из кода
1. **В контексте НЕТ возраста тредов.** Stats-строка источника =
   `Score | Comments` только (`_build_context`). Для вопросов «что сейчас
   доступно» модель не видит свежесть. created_utc есть в постах — прокинуть
   как «возраст: N дней».
2. **Нет происхождения (strategy provenance).** Синтезатор не знает, что тред
   с Serper (гугл-валидирован) vs Arctic vs натив. Потерян градиент доверия.
3. **Комментарии без бюджета и сортировки.** `_format_comments_recursive`
   идёт в порядке Reddit (confidence), body ≤2000 симв., но нет топ-K по скору
   и общего капа на дерево → непредсказуемое разбухание, жирный коммент #17
   вытесняет полезный #2.
4. **max_tokens=4096 вслепую.** finish_reason не логируется — тихая обрезка
   таблиц невозможна к диагностике.

### 5.3 Не хватает до ёмкости (gap vs эталонные ответы)
| Эталон (ассистент в сессии) | Сейчас |
|---|---|
| Сравнительная таблица с ЧИСЛАМИ (цена/час, VRAM, дни) + источник каждой строки | «используйте таблицы» без задания атрибутов → vague |
| Финальный action-block «Куда идти: 1→2→3 с условиями» | Executive Summary есть, action-block не требуется |
| Маркеры достоверности: замерено / со слов сообщества / допущение | бинарный [OP VERIFIED] |
| Перекрёстная проверка тредов друг другом | каждый тред в вакууме |

### 5.4 Избыточно
- 8000×10 символов тела: решают первые ~1500 и комментарии. Ужать до 4000–5000.
- `_build_reddit_markdown` дублирует source-cards UI. Перед удалением проверить
  потребителя поля `markdown` (CommunityInsightsSection?).

## 6. ПЛАН (KISS, по возрастанию усилий)

### Шаг 1 — prompt-engineering + 3 строки кода (ДЕЛАТЬ ПЕРВЫМ)
В `_build_context` добавить в блок источника:
```
   - Возраст: N дней назад | Канал: {found_by_strategy}
```
(created_utc есть на RedditPost; для serp/cse — «возраст неизвестен».)

В оба промпта (RU/EN) добавить обязательную структуру:
1. Сравнительная таблица по атрибутам, релевантным вопросу (цены/лимиты/VRAM/
   сроки — что спросили), каждая строка со ссылкой на № источника `[S3]`
2. Финальный блок **«Куда идти»**: ранжированные действия с условиями
   («если есть X → путь Y»)
3. Маркировка достоверности: [подтверждено сообществом] / [единичный отчёт] /
   [вывод автора анализа]
4. Требование извлекать конкретные числа из тредов, а не общие слова

### Шаг 2 — бюджет комментариев
В `_format_comments_recursive`: сортировать верхний уровень по score desc,
топ-K (например 12) на дерево, общий кап ~12–15k символов на источник суммарно
с телом.

### Шаг 3 — телеметрия ДО повышения max_tokens
Логировать `finish_reason`, длину синтеза, число источников. Только если
truncation частый → поднимать max_tokens (4096 → 6000+) или жать контекст.

### Анти-цель (не делать)
Двухпроходный extract-then-compose, второй judge-вызов, семантический индекс
тредов — YAGNI до появления измерений (см. Шаг 3 и раздел 4 п.8).

## 7. Принципы, кристаллизованные в сессии

1. **Recall на retrieval, precision на rerank.** Не фильтровать агрессивно
   до того, как умный этап увидел данные (кейс MIN_SCORE=5).
2. **Паттерны убивают очевидное, сигналы информируют, LLM судит.** Эвристика
   — только для неоспоримых паттернов (кредит-механика); спорное (starved
   engagement на vs-треде) передавать судье сигналами, не предвзято гейтить.
3. **Мери, потом крути.** Каждый канал/порог — с замером до/после на фиксированном
   наборе. Standalone-скрипты должны логировать INFO.
4. **Graceful degradation everywhere:** упавший канал = пропуск, не падение.
5. **Свежая документация > память модели.** CSE-закрытие, H3-открытие — всё
   изменилось за месяц; проверять первоисточники перед утверждениями.
6. **KISS/YAGNI в конце ревизии:** удалять то, чем не пользуются (V1, CSE,
   reddit_client, markdown-building), даже если «когда-нибудь пригодится».

## 8. Известные компромиссы и хвосты (осознанные, не баги)

- Serper/CSE кандидаты без created_utc exempt от recent_only (старые треды
  могут проскочить) — принято ради Google-ранжирования
- Arctic Shift нестабилен (422 наблюдались) — graceful degradation покрывает
- Лицензия MiniMax H3: территориальные и коммерческие ограничения; локально
  открывается только Base (2K Regenerate — только их облако)
- FLUX 3 Dev open-weight обещан «later this year», требований железа нет
- Мёртвый Vertex SA в `.env.panel` (см. §3) — влияет на embed_posts/update_production_db
- Старый пароль Reddit в git-истории публичного репо — риск принят юзером;
  ротация client_id/secret на prefs/apps остаётся лучшим mitigационным шагом
- 48h-deletion правило Reddit vs TTL артефактов 7 дней — формальное несоответствие
- Синтез binary RU/EN; third-language запросы уходят в EN-ветку
- Один раз наблюдался Arctic 422 «slow down» при параллельных title+selftext —
  если участится, добавить задержку между парами

## 9. Чеклист для новой сессии

1. Прочитать этот файл целиком
2. `git log --oneline -20` в `~/apps/experts-panel/app` — убедиться, что ничего
   не откатилось; `docker ps` — все три контейнера healthy
3. Если работаешь над синтезом → начать с Шага 1 (§6), тестировать через
   `process_reddit_pipeline(QUERY, recent_only=True)` внутри panel-контейнера
   (обязательно `logging.basicConfig(level=INFO)` в скрипте!)
4. Эталонные запросы для регрессии: «What are the best Claude Code tips and
   workflows?» (serp≈8, arctic>0), «Is uv faster than pip» (serp=8, arctic=0),
   видео-генераторы с free credits (проверка антиспама: r/AISEOInsider не в топе)
5. Не печатать секреты в чат; ключи живут в `.env.panel`/`.env.proxy` вне репо
6. После изменений кода: rebuild через
   `sudo bash -c 'set -a; source ~/apps/experts-panel/.env.panel; set +a;
   cd ~/apps/experts-panel && docker compose -f docker-compose.vm.yml up -d --build panel'`
7. Коммиты: conventional style, автор Andrii Sazonov <literavision@gmail.com>,
   push в main триггерит автодеплой
