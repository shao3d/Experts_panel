# Expert Passport: llm_under_hood

Display name: `Rinat`
Channel: `llm_under_hood`

## Counts

| Metric | Count |
|---|---:|
| Posts | 321 |
| Text posts | 321 |
| Valid post_metadata | 266 |
| Embeddings | 321 |
| FTS rows | 321 |

## Coverage

| Area | Count | Strength |
|---|---:|---|
| `model_landscape` | 218 | strong |
| `agent_ops` | 143 | strong |
| `business_adoption` | 129 | strong |
| `evals_quality` | 79 | strong |
| `coding_agents` | 73 | strong |
| `ai_product_pm` | 69 | strong |
| `rag_retrieval_knowledge` | 57 | strong |
| `ai_engineering_infra` | 39 | medium |
| `security_privacy_governance` | 34 | medium |
| `ai_ux_workflow` | 14 | medium |
| `creative_multimodal` | 4 | thin |

## Depth Profile

| Depth | Count |
|---|---:|
| `practitioner_experience` | 39 |
| `case_study` | 60 |
| `architecture_analysis` | 46 |
| `benchmark_or_eval` | 78 |
| `howto_or_checklist` | 53 |
| `tool_release` | 7 |
| `announcement_or_news` | 28 |
| `low_signal` | 10 |

## Top Metadata Signals

### Primary topics

- `AI Agents`: 35
- `LLM Benchmarking`: 27
- `AI Coding`: 14
- `Enterprise RAG`: 14
- `Prompt Engineering`: 6
- `Schema-Guided Reasoning`: 6
- `RAG`: 6
- `LLM Engineering`: 6
- `Autonomous Agents`: 5
- `LLM Reasoning`: 5

### Concepts

- `Prompt Engineering`: 25
- `Benchmarking`: 21
- `Reasoning`: 21
- `LLM`: 18
- `Software Development`: 15
- `AI Agents`: 15
- `RAG`: 14
- `Chain of Thought`: 13
- `Structured Output`: 12
- `Structured Outputs`: 12

### Keywords

- `llm`: 148
- `rag`: 71
- `reasoning`: 71
- `агенты`: 69
- `agents`: 69
- `models`: 50
- `разработка`: 49
- `бенчмарк`: 45
- `language`: 42
- `sgr`: 42


## Representative Posts

- `llm_under_hood:825` (2026-04-29, benchmark_or_eval; `agent_ops`, `evals_quality`, `business_adoption`, `security_privacy_governance`) - **У меня есть гипотеза:** **cамый нудный и денежный слой AI-автоматизации на агентах в бизнесе сейчас не в чатботах, а в Excel/Google Sheets** Не в смысле "сделайте мне красивую табличку", а в смысле: - один отдел выгружает кривую таблицу - второй отдел руками приводит ее к другому формату - где-то рядом лежат прави...
- `llm_under_hood:812` (2026-04-17, benchmark_or_eval; `coding_agents`, `agent_ops`, `evals_quality`, `ai_product_pm`, `business_adoption`, `model_landscape`) - **AI Ops или еще одна история про то, как AI выручает lean команды** В команде BitGN за платформу и техническое составляющую отвечаю пока только я. И, как выяснилось, интерес к открытой среде для тестирования и разработки надежных AI агентов сильно выше того, что ожидали. Во время соревнования в среднем запускали по...
- `llm_under_hood:826` (2026-04-30, practitioner_experience; `coding_agents`, `agent_ops`, `ai_product_pm`, `business_adoption`, `ai_engineering_infra`) - **У YCombinator заметно поменялось видение AI-стартапов** Весной их [Request For Startups](https://www.ycombinator.com/rfs) звучал как “AI-native компании могут быстрее делать дорогую работу”. > RFS == “*Мы видим индустрию изнутри, и вот в такие компании мы бы с радостью вложили много денег*” Отсюда был приоритет на...
- `llm_under_hood:792` (2026-04-05, howto_or_checklist; `coding_agents`, `agent_ops`, `rag_retrieval_knowledge`, `model_landscape`) - **Karpathy написал классный gist про использование LLM для ведения баз знаний**: [LLM wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) Это отчасти совпадает с тем, как я использую OpenAI Codex для персонального ассистента ([Personal OS v2](https://t.me/llm_under_hood/750)), но есть и различия...
- `llm_under_hood:806` (2026-04-11, benchmark_or_eval; `agent_ops`, `evals_quality`) - **Основная часть конкурса BitGN PAC1 завершена**! Всем спасибо за участие! 20 хабам и больше 800 инженеров в 80 городов. Громче всех выступили Москва, Уфа и Вена. А суммарная нагрузка на сервера превысила в пике ERC3 раз в 20. Я был готов ко всему - что упремся в CPU, оперативку или диск. Но вы с таким энтузиазмом в...
- `llm_under_hood:803` (2026-04-11, benchmark_or_eval; `evals_quality`) - Bitgn/Pac1-PROD - соревнование закрыто! Результаты в стриме через полчаса. **Оценки ваших ранов появятся примерно тогда же ** **Бенчмарк теперь в открытом режиме**, должен показывать ошибки и оценки на новых ранах. Ваш, @llm_under_hood 🤗
- `llm_under_hood:798` (2026-04-11, benchmark_or_eval; `evals_quality`, `security_privacy_governance`) - **Утечка данных про BitGN/PAC1-PROD ** Спасибо Daniel за подсказку, что названия задач продовского бенчмарка торчали наружу (runtimes были закрыты). Я это дело прикрыл. Вряд ли много людей это видели. Но, чтобы было честнее - вот всем список типов задач, которые будут в проде: *• Knowledge ops: keep working knowledg...
- `llm_under_hood:829` (2026-05-03, case_study; `coding_agents`, `agent_ops`, `ai_product_pm`, `business_adoption`, `model_landscape`) - **OpenCode + GPT 5.5 - ну не используйте вы субагентов!** В комментариях к [посту про эксперимент с рефакторингом](https://t.me/llm_under_hood/828) кода разными агентами, чаще всего просили запустить OpenCode + GPT 5.5. Запустил в режиме High на том же коммите с тем же промптом: > Scan through the repository on a hi...
