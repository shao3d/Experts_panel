# Starter: admission эксперта @neyr0graph (Visual / видеогенерация)

Status: Active handoff starter
Created: 2026-09-15
Origin: сессия 2026-09-14/15 (admission cgevent, taxonomy `cg_craft_to_ai`, matrix 25/64)
How to use: это paste-ready промт для нового чата. Агент читает `docs/DOCUMENTATION_MAP.md`,
находит этот файл в «Быстрые Маршруты» и выполняет содержимое от онбординга до DoD.

---

# Онбординг + задача: admission нового эксперта (Visual/видеогенерация) — @neyr0graph

## 0. Правила
- Рабочая директория только /home/ubuntu/apps/experts-panel/dev (VM). Язык ответов/коммитов — RU или EN.
- Не читать/печатать/копировать секреты, .env, токены, БД. Единственное исключение — read-only Expert Scout по dev-корпусу (см. AGENTS.md).
- Commit только по команде «зафиксируй»; push/deploy/data release — только по «выкатывай» / «обнови базу».
- Перед работой проверь git status и не трогай чужие незакоммиченные правки (сейчас есть untracked
  backend/scripts/benchmark_reddit_synthesis_models.py — не мой, не трогать).

## 1. Онбординг (сделай в этом порядке, не по памяти)
1. AGENTS.md (правила Git/VM/release/safety).
2. docs/DOCUMENTATION_MAP.md — навигация.
3. docs/architecture/pipeline.md — 10-фазный pipeline.
4. docs/architecture/current-expert-roster.md — актуальный roster.
5. docs/architecture/expert-admission-control.md — admission-first доктрина (passport, matrix, verdicts,
   artifacts, alias/taxonomy; там же snapshot 2026-09-14 и dogfood-заметка про digest).
6. docs/guides/add-expert.md — операционный импорт (начинается ПОСЛЕ verdict).
7. docs/guides/expert-scout.md и docs/guides/panex-usage.md — каналы поиска.
8. docs/operations.md — code release / data release / rollback.
Статус проверяй по коду и командам, а не по памяти.

## 2. Текущее состояние (2026-09-15)
- Roster: 26 экспертов. Visual: strangedalle (Molodca), acidcrunch (AcidCrunch), cgevent (Tsyptsyn).
- cgevent admitted 2026-09-14 (commit 406b343): passports/arbitration/admission в
  output/expert_admission/candidates/cgevent/; data release прошёл (792 поста, 8972 коммента,
  drift 663/663, embeddings). Матрица: output/expert_admission/admission_manifest.json (25 паспортов)
  + knowledge_matrix/ (64 клетки). Таксономия `creative_multimodal/cg_craft_to_ai` — core (extensions=0).
  Если артефактов нет — скопируй с Мака /Users/andreysazonov/Documents/Projects/Experts_panel/output/expert_admission
  через обратный туннель (ssh -p 2222 -i ~/.ssh/mac_remote andreysazonov@localhost, tar, не scp).
- Последний commit: 7a7469e (таксономия + доки). Прод DB обновлена 2026-09-14.
- Паспортный раннер: backend/scripts/run_semantic_passport_opencode.py, модель по умолчанию
  opencode-go/deepseek-v4.1-flash через headless `opencode serve` (:4096). Если serve не знает модель
  (500) → `sudo systemctl restart opencode-serve`.
- Panex по умолчанию expert_digest, редукцию делает Gemini (MODEL_SYNTHESIS=google/gemini-3-flash-preview).
  Наблюдение догфуда: на how-to digest даёт mention-level сигналы без stance — учитывай, не переоценивай digest.
- Reddit V2 на VM технически недоступен (нет токена; owner action). Не выдавай это за «нет результатов».

## 3. Задача
Провести admission нового визуального эксперта @neyr0graph (NeuroGraph, Сергей Нейрограф, ~34.5K).
Профиль по публичному превью: AI-режиссура и virtual production — мизансцена/блокинг, движения камеры,
свет и цвет для генеративного кино, монтаж в DaVinci, воркфлоу Blender + GPT-Astra + Seedance 2.5,
Weavy AI, разборы видеомоделей (Kling/Veo/Seedance/FLUX Video) и цена генерации.
Только последние 4 месяца данных. Ожидаемый вердикт — limited_scope (Visual).
Ожидаемый уникальный угол vs cgevent/molodca/acidcrunch: постановка сцены и AI-режиссура.
Особый риск: заметная доля промо своих курсов Boosty (3550–5850 ₽/мес) → много announcement/tool_release шума;
в arbitration честно разделяй практику и промо.
Fallback, если 4-месячный корпус окажется тонким или почти целиком промо: @aifilmmaker
(Дмитрий Алексеев, режиссёр; аналитика AI-кино + свои короткометражки; ~6.3K) — предложи владельцу.

## 4. План (точные команды; из корня dev)
4.1. Получи у владельца Telegram Desktop JSON канала @neyr0graph (Channel → ⋮ → Export chat history → JSON),
     путь на Маке. Скопируй на VM через туннель (пути с пробелами → tar, не scp; не забудь распаковать):
       mkdir -p backend/data/exports/neyrograph
       ssh -p 2222 -i ~/.ssh/mac_remote -o IdentitiesOnly=yes andreysazonov@localhost \
         'COPYFILE_DISABLE=1 tar -C "<Mac export dir>" -cf - result.json' > /tmp/neyro.tar
       tar -xf /tmp/neyro.tar -C backend/data/exports/neyrograph/ && rm /tmp/neyro.tar
4.2. Packet только за 4 месяца (cutoff = сегодня минус 4 месяца, YYYY-MM-DD):
       backend/.venv/bin/python backend/scripts/export_semantic_passport_packet_from_telegram_json.py \
         --json backend/data/exports/neyrograph/result.json \
         --expert-id neyrograph --display-name "Neyrograph" --channel-username neyr0graph \
         --min-date <CUTOFF>
     Учти: username с нулём — `neyr0graph`; экспорт канала НЕ содержит комментариев (linked discussion group);
     comments_synced=false — штатно.
4.3. Semantic passport + normalize, проверь valid_basic_contract: true:
       backend/.venv/bin/python backend/scripts/run_semantic_passport_opencode.py \
         --packet-dir output/expert_admission/semantic_passports/neyrograph/input
       backend/.venv/bin/python backend/scripts/run_semantic_passport_opencode.py \
         --packet-dir output/expert_admission/semantic_passports/neyrograph/input --normalize-existing
4.4. Preflight против текущей матрицы:
       backend/.venv/bin/python backend/scripts/evaluate_expert_candidate.py \
         --candidate-passport output/expert_admission/semantic_passports/neyrograph/output/neyrograph_semantic_passport.normalized.json
     Прочитай output/expert_admission/candidates/neyrograph/candidate_impact_report.md.
4.5. Arbitration по первоисточникам (читай корпус packet'а), затем admission_report.md/json в
     output/expert_admission/candidates/neyrograph/. Вердикт: accept/reject/watchlist/limited_scope.
     Покажи вердикт владельцу и дождись подтверждения.
4.6. После подтверждения: добавь в admission_manifest.json (verdict, include_in_knowledge_matrix,
     passport_path, admission_report, decision_basis, routing_caveat), пересобери:
       backend/.venv/bin/python backend/scripts/build_knowledge_matrix.py
     Taxonomy extension — только через явное решение владельца (alias-механизм в build_knowledge_matrix.py).
4.7. Импорт ТОЛЬКО 4 месяца: собери отфильтрованный JSON (messages с date >= CUTOFF, сохрани name/type/id),
     сделай backup dev DB, затем:
       DATABASE_URL="sqlite:////home/ubuntu/apps/experts-panel/dev/backend/data/experts.db" \
       PYTHONPATH=/home/ubuntu/apps/experts-panel/dev/backend \
       backend/.venv/bin/python backend/tools/add_expert.py neyrograph "Neyrograph" neyr0graph <filtered.json>
     НЕ используй scripts/add_new_expert.sh (он интерактивный и запускает sync сам).
4.8. Комменты через Telegram API (сессия в env TELEGRAM_SESSION_NAME, абсолютный путь; не печатай токены):
       set -a; source backend/.env; set +a
       TELEGRAM_CHANNEL=neyr0graph DATABASE_URL="sqlite:////home/ubuntu/apps/experts-panel/dev/backend/data/experts.db" \
       PYTHONPATH=/home/ubuntu/apps/experts-panel/dev/backend \
       backend/.venv/bin/python backend/sync_channel.py --expert-id neyrograph --depth 2000
     Запускай в tmux (долго; ~2–20 с/пост), по завершении проверь counts и pending drift.
4.9. UI/группы/доки: frontend/src/config/expertConfig.ts (Visual + displayNames + order),
     backend/src/expert_groups.py (visual), docs/architecture/current-expert-roster.md.
     Если менял состав visual-группы — обнови фикстуру/ассерты в backend/tests/test_expert_scout.py.
4.10. Проверки:
       backend/.venv/bin/python -m pytest backend/tests/test_expert_scout.py backend/tests/test_agent_context_api.py -q -o addopts=''
       cd frontend && npm run type-check && npm run test:run
4.11. Прод — только по команде владельца: «выкатывай» (код) и «обнови базу» (данные: sync,
     embeddings, drift, prod DB). commit — только по «зафиксируй».

## 5. Гочи, уже проверенные на опыте
- Окно 4 месяца обязательно и для passport, и для импорта (канал большой, историю не тянем).
- Пути на Маке с пробелами ломают scp → ssh+tar и обязательно распакуй архив.
- add_expert.py импортирует ВЕСЬ JSON → сначала отфильтруй по дате.
- Комменты канала живут в linked discussion group и в экспорт не попадают — только API-синк.
- comment sync идёт по постам до 2000; темп ~2–20 с/пост; ставь tmux.
- drift после синка = pending; анализ (opencode/Muse) и embeddings — на data release.
- output/ в .gitignore; артефакты admission живут только на VM (и на Маке).
- Course-promo каналы (как NeuroGraph) дают много announcement-шума: в passport/arbitration опирайся
  на посты с конкретикой (воркфлоу, приёмы, цены), а промо помечай как noise.
- Если постов за 4 месяца мало (<~50 текстовых) или это в основном промо — доложи и предложи @aifilmmaker.

## 6. Definition of done
Паспорт (valid) + preflight + arbitration/admission verdict + manifest/matrix обновлены +
dev DB с 4-месячным корпусом и комментами + pending drift + UI-конфиг/группы/ростер + тесты зелёные +
короткий отчёт владельцу: что сделано, что проверено, что не проверено и какие команды нужны (выкатывай/обнови базу).
