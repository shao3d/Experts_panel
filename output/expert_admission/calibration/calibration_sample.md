# Expert Coverage Calibration Sample

Generated: `2026-05-09T09:32:15+00:00`
DB: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/data/experts.db`
Experts sampled: `5`
Posts sampled: `40`

## Review Guidance

- Mark each post as ok, partial, wrong, or blind_spot.
- Treat labels as grounded only when the excerpt supports the topic directly.
- Watch for broad terms such as product, model, agent, workflow, and news.
- Depth labels are advisory and should be reviewed separately from coverage labels.

## akimov

Display: `Akimov`
Channel: `ai_product`
Classified posts: `611`
Sampled posts: `8`

Sample coverage counts:
- `agent_ops`: 2
- `ai_engineering_infra`: 1
- `ai_product_pm`: 1
- `ai_ux_workflow`: 1
- `business_adoption`: 2
- `coding_agents`: 2
- `creative_multimodal`: 1
- `evals_quality`: 7
- `general_ai_news`: 1
- `model_landscape`: 6
- `rag_retrieval_knowledge`: 1
- `security_privacy_governance`: 1

Sample depth counts:
- `announcement_or_news`: 1
- `benchmark_or_eval`: 7

### Posts

#### `akimov:2154`

- Date: `2026-05-04`
- Coverage labels: `evals_quality`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `evals_quality=[бенчмарк]; model_landscape=[llm, openai, модель]; depth=[бенчмарк]`
- Review: `unreviewed`

Мне нравятся всякие сериалы про скорую помощь, но кажется скоро там будет сплошной ИИ. Прочитал про Гарвардское исследование, опубликованное в Science. Доказали, что LLM-системы точнее людей ставят диагнозы в условиях экстренной медицины – тех самых первых минут в приёмном покое, когда от решения зависит жизнь. Авторы пишут, что языковые модели "превзошли большинство бенчмарков клинического мышления". Причем это была не какая-нибудь супер-свежая модель, а просто o1 годовой давности! Тестировали на 76 пациентов реального бостонского госпиталя, дали одинаковые электронные карты для ИИ и пар врачей: жизненные показатели, демография, пара фраз от медсестры о причине обращения. ИИ дал точный и...

#### `akimov:2143`

- Date: `2026-04-24`
- Coverage labels: `agent_ops`, `evals_quality`, `ai_ux_workflow`, `security_privacy_governance`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `agent_ops=[skills]; evals_quality=[бенчмарк]; ai_ux_workflow=[workflow]; security_privacy_governance=[безопас, регулир]; model_landscape=[claude, gemini, gpt, openai]; depth=[бенчмарк]`
- Review: `unreviewed`

У врачей тоже скоро сплошной ИИ - OpenAI выпустил ChatGPT for Clinicians – отдельную конфигурацию для медиков с фокусом на клинические задачи: документацию, ресёрч и разбор кейсов. Доступ бесплатный, но только для верифицированных врачей, NP, PA и фармацевтов в США. Цифры по рынку, которые они приводят: 72% американских врачей уже используют AI в практике – год назад было 48%. Использование ChatGPT медиками за год удвоилось. И соответственно убили еще 10 стартапов :) Что внутри – Доступ к фронтирным моделям (GPT-5.4 и далее) без лимитов на типичные клинические задачи – Skills – переиспользуемые шаблоны для повторяющихся workflow: направления, описание диагноза, инструкции пациентам – Клин...

#### `akimov:2141`

- Date: `2026-04-24`
- Coverage labels: `coding_agents`, `agent_ops`, `evals_quality`, `business_adoption`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[кодинг]; agent_ops=[агентн, агент]; evals_quality=[бенчмарк]; business_adoption=[эконом]; model_landscape=[anthropic, claude, gemini, gpt, openai, модель]; depth=[бенчмарк]`
- Review: `unreviewed`

DeepSeek-V4! DeepSeek наконец выпустил превью новой модели – прямой конкурент Claude, GPT и Gemini, только в open-source. Посмотрел в общем бенчмарки и отчет. Ну-у... Если бы вышла в начале года, - это был бы просто нереальный прорыв. Сейчас просто лучший опенсорс :) Да и сейчас в общем-то базовые архитектурные вещи на основе всех самых последних инноваций, так что добивать его дообучением и обходить топ-США модели смогут без проблем. Выпустили 2 версии: – V4-Pro – флагман, 1.6T параметров. Для сложного ризонинга, кодинга, агентных задач – V4-Flash – младшая модель, 284B параметров. Быстрее, дешевле, но умнее многих старых гигантов Основная фишка - контекст 1 миллион токенов. Ну то есть у...

#### `akimov:2105`

- Date: `2026-04-15`
- Coverage labels: `evals_quality`, `ai_product_pm`, `ai_engineering_infra`
- Depth label: `benchmark_or_eval`
- Matched terms: `evals_quality=[бенчмарк]; ai_product_pm=[продукт]; ai_engineering_infra=[инфра]; depth=[бенчмарк]`
- Review: `unreviewed`

У меня сегодня день рождения, и конечно хочется подвести итоги 🙂 Последний год прошёл под знаком AI. Мы с командой сделали порядка 20 проектов для клиентов по всей Европе – от простых чат-ботов до полноценных ИИ-трансформаций целых компаний. Главный инсайт года (хотя это так легко понять): узкое место до сих пор – не технологии, а люди. С ИИ делать софт можно безумно быстро, можно получить просто нереально крутые результаты, но 4 месяца переговоров с банком через 20 разных человек, CTO, блокирующий инициативы после восторга генерального директора, разработчики, саботирующие процессы, которые сделают им жизнь проще – всё это реальность, с которой сталкивается каждый, кто внедряет ИИ. Это н...

#### `akimov:2077`

- Date: `2026-04-02`
- Coverage labels: `coding_agents`, `evals_quality`, `model_landscape`, `creative_multimodal`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[copilot]; evals_quality=[бенчмарк]; model_landscape=[gemini, gpt, openai, модель]; creative_multimodal=[voice]; depth=[бенчмарк]`
- Review: `unreviewed`

И Microsoft тоже жжет напалмом. Видимо забили на OpenAI и решили самим делать базовые модели для клиентов. Выкатила сразу 3 новых модели MAI – Transcribe-1, Voice-1 и Image-2. Всё доступно через Microsoft Foundry. MAI-Transcribe-1 – speech-to-text модель: Первое место по FLEURS бенчмарку в 11 из 25 топовых языков (на русском кстати gpt лучше) В остальных 14 бьёт Whisper-large-v3, а в 11 из них ещё и Gemini Flash Батч-транскрипция в 2.5x быстрее текущего Azure Fast Цена: $0.36/час – заявляют лучший price-performance среди крупных облаков. Ну у специализированных вендоров и подешевле. MAI-Voice-1 – генерация голоса: Создание кастомного голоса по нескольким секундам аудио 60 секунд аудио ген...

#### `akimov:1767`

- Date: `2025-12-10`
- Coverage labels: `evals_quality`, `rag_retrieval_knowledge`, `business_adoption`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `evals_quality=[benchmark, бенчмарк]; rag_retrieval_knowledge=[rag]; business_adoption=[бизнес]; model_landscape=[gpt]; depth=[benchmark, бенчмарк]`
- Review: `unreviewed`

Databricks тут выложил датасет и бенчмарк OfficeQA, типа "типичные офисные задачи". Я сначала порадовался, но потом посмотрел глубже. Пишут, что существующие бенчмарки (GDPval, ARC-AGI-2, Humanity's Last Exam) не отражают проблемы бизнеса. Они либо слишком абстрактные, либо требуют PhD-уровня знаний. OfficeQA фокусируется на том, что реально нужно корпорациям: извлечение и анализ данных из больших объемов документов. Поэтому сделали типа свой - 246 вопросов на основе 89,000 страниц. НО! Это US Treasury Bulletins (1939-1996), то есть всякие старые сканы кривых страниц статистики. Средний вопрос требует информации из ~2 документов Человек тратит в среднем 50 минут на вопрос Все вопросы реша...

#### `akimov:2108`

- Date: `2026-04-16`
- Coverage labels: `general_ai_news`
- Depth label: `announcement_or_news`
- Matched terms: `general_ai_news=[нейросет]`
- Review: `unreviewed`

Хах, принудительное обучение ИИ в Apple. https://vc.ru/apple/2870994-apple-otpravlyaet-razrabotchikov-siri-na-kurs-po-ii-programmirovaniyu The Information: Apple отправит часть разработчиков Siri на курс по «ИИ-программированию» — внутри компании отдел считают «отстающим» Его сотрудники используют нейросети меньше других команд.

#### `akimov:1319`

- Date: `2025-06-03`
- Coverage labels: `evals_quality`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `evals_quality=[бенчмарк]; model_landscape=[claude, gpt]; depth=[бенчмарк]`
- Review: `unreviewed`

При этом интересно, что после выхода Claude 4 как-то вообще мало было восторженных отзывов и писаний кипятком. И видимо неспроста. На арене и соннет, и опус где-то на 4-7 месте, но да, все еще сильны в веб-разработке и длинном контексте, и - что интересно - креативных текстах. По реальным бенчмаркам - на уровне DeepSeek, чуть лучше GPT-4.1. Ну-у... Такое. https://artificialanalysis.ai/models/claude-4-opus https://artificialanalysis.ai/models/claude-3-7-sonnet-thinking/providers


## kornish

Display: `Kornishev`
Channel: `NGI_ru`
Classified posts: `423`
Sampled posts: `8`

Sample coverage counts:
- `agent_ops`: 5
- `ai_engineering_infra`: 1
- `ai_product_pm`: 6
- `ai_ux_workflow`: 4
- `business_adoption`: 5
- `coding_agents`: 3
- `creative_multimodal`: 1
- `evals_quality`: 5
- `general_ai_news`: 1
- `model_landscape`: 6
- `rag_retrieval_knowledge`: 2
- `security_privacy_governance`: 3

Sample depth counts:
- `benchmark_or_eval`: 5
- `case_study`: 2
- `howto_or_checklist`: 1

### Posts

#### `kornish:612`

- Date: `2026-04-24`
- Coverage labels: `agent_ops`, `evals_quality`, `rag_retrieval_knowledge`, `ai_product_pm`, `business_adoption`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `agent_ops=[агент]; evals_quality=[бенчмарк]; rag_retrieval_knowledge=[вектор]; ai_product_pm=[продукт]; business_adoption=[arr, бизнес, внедрен]; model_landscape=[gpt, llm, модель]; depth=[бенчмарк]`
- Review: `unreviewed`

**Как пивот в AI‑агентов и смена бизнес‑модели вытащили Perplexity к $450M+ ARR. Разбор кейса** В прошлом посте я сравнивал функционал 3 агентских ИИ, которыми пользуюсь сейчас, отдельно выделяя Perplexity. Сегодня, как и обещал, разбираю что команда стартапа сделала на уровне стратегии и бизнес‑модели - и почему это один из самых сильных продуктовых и бизнес мувов в AI на сегодня. **(Не) убийца Google** Изначально Perplexity позиционировались как AI‑поиск: задаёшь вопрос - получаешь готовый ответ, ссылки, саммари. Умнее и удобнее, чем классический Google, но по сути это все один сегмент: ты конкурируешь с поиском, где у людей в голове уже встроен один доминирующий бренд (не берем локальн...

#### `kornish:535`

- Date: `2025-12-19`
- Coverage labels: `evals_quality`, `ai_product_pm`, `business_adoption`, `ai_ux_workflow`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `evals_quality=[метрик]; ai_product_pm=[ценность]; business_adoption=[бизнес]; ai_ux_workflow=[воркфлоу]; model_landscape=[gpt, модель]; depth=[метрик]`
- Review: `unreviewed`

**Про красивые цифры в маркетинге и реальный профит** На днях общались с Денисом Сметнёвым (тем самым кофаундером Skyeng) о наболевшем: как сейчас команды маркетинга умудряются виртуозно прожигать бюджеты. Ситуация стандартная: работаешь с подрядчиком по привлечению, в отчетах всё красиво - посевы сделаны, подписчики капают, лиды идут. Но когда дело доходит до целевых метрик и реальных оплат, оказывается, что это были просто упражнения в трате денег. Я и сам в своих проектах всё чаще перехожу на модель оплаты за конкретный результат, а не за процесс или почасовку. Потому что просто посевы, реклама и лиды - это всё чаще красивые цифры в отчетности, которые не преобразуются в платящих клиен...

#### `kornish:512`

- Date: `2025-11-13`
- Coverage labels: `agent_ops`, `evals_quality`, `ai_product_pm`, `business_adoption`, `ai_ux_workflow`, `ai_engineering_infra`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `agent_ops=[агент]; evals_quality=[бенчмарк]; ai_product_pm=[продукт]; business_adoption=[внедрен, эконом]; ai_ux_workflow=[воркфлоу]; ai_engineering_infra=[инфра]; model_landscape=[модель]; depth=[бенчмарк]`
- Review: `unreviewed`

**Что будет с AI в ближайшие 5 лет?** Помните, я как-то [разбирал](https://t.me/NGI_ru/219) нашумевшую статью AI 2027? Ту самую, где авторы предсказывают суперинтеллект и чуть ли не научную фантастику в реальной жизни уже к 2027 году. Их оппоненты из лагеря [AI as Normal Technology](https://knightcolumbia.org/content/ai-as-normal-technology) наоборот, утверждают, что развитие будет постепенным, как с интернетом - без резких взрывов. И вот, произошло нечто интересное. Авторы обеих статей - сели за один стол и выпустили совместный [текст](https://asteriskmag.substack.com/p/common-ground-between-ai-2027-and?utm_source=tldrai). И не про то, в чем они не согласны, а наоборот - о том, в чем их...

#### `kornish:437`

- Date: `2025-08-07`
- Coverage labels: `coding_agents`, `evals_quality`, `security_privacy_governance`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[windsurf]; evals_quality=[бенчмарк]; security_privacy_governance=[безопас]; model_landscape=[anthropic, claude, gemini, gpt, llm, openai]; depth=[бенчмарк]`
- Review: `unreviewed`

**Завышенные ожидания или OpenAI выдохлись?** OpenAI презентовали GPT-5, которую так долго мариновали и которую мы так долго ждали. Сэм Альтман активно продвигал модель в своем твитере и публичных выступлениях, но что на деле? **На деле мы получили самую скучную и невпечатляющую презентацию** Я отсмотрел эфир “от” и “до”. Вердикт: надо тестить, потому что верить на слово больше не получается. В начале нас покормили стандартной порцией бенчмарков: модель, конечно же, стала лучше в логике, рассуждениях и безопасности. Классика. **А потом начались демо, вызвавшие один вопрос: и это всё?** Нам показали ответы на вопросы по физике, на лету собрали приложение для изучения французского и сгенери...

#### `kornish:390`

- Date: `2025-06-30`
- Coverage labels: `agent_ops`, `evals_quality`, `ai_product_pm`, `ai_ux_workflow`, `model_landscape`, `creative_multimodal`
- Depth label: `benchmark_or_eval`
- Matched terms: `agent_ops=[агент]; evals_quality=[метрик]; ai_product_pm=[продукт]; ai_ux_workflow=[ux]; model_landscape=[anthropic, gemini, llm, openai, модель]; creative_multimodal=[voice]; depth=[метрик]`
- Review: `unreviewed`

**Умрет ли Perplexity?** В последнее время я все чаще вижу мнение о том, что время Perplexity прошло. Сторонники этой позиции аргументируют все тем, что функции AI-поисковика уже интегрированы в LLM, при этом качество поиска в Perplexity местами проигрывает LLM, а ссылки на первоисточники сервис выдает некорректные. Другой популярный аргумент, говорящий о том, что “компания нездорова” - это количество бесплатных подписок, раздаваемых на сервис в рамках разных кампаний, мол, у ребят настолько все плохо, что люди будут пользоваться их продуктом либо за дешево либо бесплатно. На другой чаше весов - продолжающиеся раунды инвестиций и куча восторженных отзывов от простых пользователей (посмотр...

#### `kornish:121`

- Date: `2025-01-17`
- Coverage labels: `general_ai_news`
- Depth label: `howto_or_checklist`
- Matched terms: `general_ai_news=[искусственный интеллект]; depth=[как]`
- Review: `unreviewed`

**Мои предсказания, что будет с ИИ в 2025 году** В последнее время мне часто попадаются на глаза различные прогнозы о том, что ждет искусственный интеллект в этом году. Как специалист, занимающийся разработкой ИИ-систем, я тоже решил поделиться своим видением ситуации и посмотреть, какие из моих предсказаний сбудутся к концу года. Как обычно, пост получился длинным, поэтому публикую его в виде [статьи](https://telegra.ph/Moi-predskazaniya-o-budushchem-II-v-2025-godu-01-17)! А какие у вас прогнозы, связанные с ИИ в 2025? #развитиеИИ

#### `kornish:586`

- Date: `2026-03-06`
- Coverage labels: `coding_agents`, `agent_ops`, `rag_retrieval_knowledge`, `ai_product_pm`, `business_adoption`, `ai_ux_workflow`, `security_privacy_governance`
- Depth label: `case_study`
- Matched terms: `coding_agents=[cursor, vibe coding, вайб, кодинг]; agent_ops=[агент]; rag_retrieval_knowledge=[rag, база знаний]; ai_product_pm=[продукт, продакт]; business_adoption=[бизнес, эконом]; ai_ux_workflow=[воркфлоу]; security_privacy_governance=[безопас]; depth=[кейс]`
- Review: `unreviewed`

**Vibe Coding: полезные материалы, лайфхаки и мои кейсы ** Вайбкодинг - далеко не самая главная тема моего канала. Однако, несмотря на то, что пишу я про него нечасто, на разработку с помощью ИИ я потратил уже несколько тысяч часов. Писать стараюсь по сути, и постарался сконцентрировать свой опыт в тех материалах, которые периодически здесь публиковал. В этой подборке я собрал всё самое важное по тематике вайбкодинга: от моих личных кейсов, которые помогают понять, на что вообще способен ИИ, до практических лайфхаков и обзоров инструментов. **🧠 База и Лайфхаки (С чего начать)** Прежде чем открывать редактор, нужно понять правила игры. Без этого вы просто сожжете токены и нервы. 1. **11 пр...

#### `kornish:419`

- Date: `2025-07-24`
- Coverage labels: `coding_agents`, `agent_ops`, `ai_product_pm`, `business_adoption`, `security_privacy_governance`, `model_landscape`
- Depth label: `case_study`
- Matched terms: `coding_agents=[вайб, кодинг]; agent_ops=[агент]; ai_product_pm=[продукт]; business_adoption=[бизнес]; security_privacy_governance=[регулир]; model_landscape=[llm]; depth=[кейс]`
- Review: `unreviewed`

**Каналы, которые я читаю по AI** В продолжение вчерашнего поста здесь будет подборка того, что я читаю сам. @ai_newz - пусть я получаю основные новости из рассылок и шарясь по HuggingFace, мне нравится канал Артема, т.к. часто тут не только новости, но и какие-то крутые мысли. @oestick - канал Коли, с которым мы вместе проводили эфир. Много технической информации, при этом довольно часто на языке бизнеса. Здесь практические фишки работы с LLM в доступном изложении. @ProductsAndStartups - канал Байрама Аннакова, здесь много про AI в бизнесе, этику, тренды и продукт. Следил за Байрамом задолго до увлечения AI - умнейший человек, у которого можно учиться всегда, насколько бы круты вы ни был...


## neuraldeep

Display: `Neuraldeep`
Channel: `neuraldeep`
Classified posts: `380`
Sampled posts: `8`

Sample coverage counts:
- `agent_ops`: 5
- `ai_engineering_infra`: 2
- `ai_product_pm`: 1
- `ai_ux_workflow`: 1
- `business_adoption`: 3
- `coding_agents`: 3
- `creative_multimodal`: 1
- `evals_quality`: 7
- `general_ai_news`: 1
- `model_landscape`: 5
- `rag_retrieval_knowledge`: 2
- `security_privacy_governance`: 3

Sample depth counts:
- `benchmark_or_eval`: 7
- `low_signal`: 1

### Posts

#### `neuraldeep:2088`

- Date: `2026-04-22`
- Coverage labels: `evals_quality`, `security_privacy_governance`
- Depth label: `benchmark_or_eval`
- Matched terms: `evals_quality=[метрик, бенчмарк]; security_privacy_governance=[безопас]; depth=[бенчмарк, метрик]`
- Review: `unreviewed`

⚡️ **Открываем NSFW-бенчмарк для систем модерации** В прошлых постах мы много говорили о фильтрации NSFW. А теперь выкатываем в открытый доступ наш [двуязычный бенчмарк](https://huggingface.co/datasets/redmadrobot-rnd/nsfw_benchmark) для систем модерации контента. Что внутри датасета: • контрастные пары — о которых мы уже [писали](https://t.me/rmr_rnd/330), • сложные пограничные примеры — hard negatives. Все данные собирались, отсеивались и валидировались полностью вручную. В карточке датасета рассказали, как [устроена](https://t.me/rmr_rnd/329) таксономия[ ](https://t.me/rmr_rnd/329)небезопасного контента. А ещё — добавили метрики популярных открытых моделей на этом датасете для удобного...

#### `neuraldeep:2082`

- Date: `2026-04-20`
- Coverage labels: `evals_quality`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `evals_quality=[бенчмарк]; model_landscape=[gpt, llm]; depth=[бенчмарк]`
- Review: `unreviewed`

**LLM hub by Kovalskii** Вчера анонсировал https://hub.neuraldeep.ru/, а сегодня с утра уже есть что анализировать (вы просто супер аудитория!) Что интересно из аналитики для меня: Много кто взял модели для прогона pac1 (бенчмарка от Рината) Кто-то взял для подключения к [opencode](https://t.me/neuraldeepchat/54442) И самое интересное что на таком объеме запросов и людей, некоторые высказались тем что очень радует скорость и доступность моделей (gpt oss 120b) Через неделю я планирую провести закрытий стрим для всех **активных** пользователей Важные условия для участия 1) Активно юзать хаб 2) Смотреть почту на предмет сообщений с домена @neuraldeep.ru Мы разберем как и зачем я использую та...

#### `neuraldeep:2058`

- Date: `2026-04-09`
- Coverage labels: `agent_ops`, `evals_quality`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `agent_ops=[skills, агент]; evals_quality=[бенчмарк]; model_landscape=[gpt, openai, модель]; depth=[бенчмарк]`
- Review: `unreviewed`

PAC1-DEV Почитать что это такое можно [тут](https://bitgn.com/challenge/PAC) ([Ринат](https://t.me/llm_under_hood) не перестает удивлять нас бенчмарками и соревнованиями) Решил пожечь подписку и реализовать свой подход, за старт спасибо (@multiagentsys) он выложил [репо](https://github.com/snow-ghost/sample-agent) от которого я начал) За ночь(в ленивом ральф лупе через СС + Opus) довел gpt oss 120b + openai agent sdk + skills search + skills classificator до 39 pass 4 failed 90%( не стабильно) в среднем 83-84% Из приятного сделал полноценный центр управления запуском Настройки Запуск Сравнение Дефрагментация диска =) Можно ранить парарельно до 30 агентов (столько держит мои 4090 48гб 2шту...

#### `neuraldeep:2052`

- Date: `2026-04-08`
- Coverage labels: `coding_agents`, `agent_ops`, `evals_quality`, `business_adoption`, `security_privacy_governance`, `ai_engineering_infra`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[codex, claude code]; agent_ops=[skills, агентн, агент, скил]; evals_quality=[eval]; business_adoption=[бизнес, внедрен]; security_privacy_governance=[безопас]; ai_engineering_infra=[backend, инфра]; model_landscape=[claude, llm, openai]; depth=[eval]`
- Review: `unreviewed`

**Вышел наш второй комьюнити-стрим!** Для вас отжигали, на фото: @nobilix, @superbereza, @ai_grably, @aostrikov_ai_agents и маэстро @neuraldeep 📹 https://youtu.be/nUT1YRvjG98 24 вопроса, 2**.5 часа стрим,** чуть не дожали до бейзлайна Лекса Фридмана. Поболтали про агентов, будущее, лобстеров, утекший claude code и вероятность продать свой опенкло за миллиард: 0[0:00 ](https://youtu.be/nUT1YRvjG98?t=0)— Приветствие! 0[6:06 ](https://youtu.be/nUT1YRvjG98?t=366)— Как системно строить общую базу знаний для агентов и как вести документацию? 1[1:57 ](https://youtu.be/nUT1YRvjG98?t=717)— Куда сдвинется бизнес-запрос в течение года: к агентным сценариям или к чему-то другому? 2[0:07 ](https://you...

#### `neuraldeep:2046`

- Date: `2026-04-06`
- Coverage labels: `agent_ops`, `evals_quality`, `rag_retrieval_knowledge`, `business_adoption`, `creative_multimodal`
- Depth label: `benchmark_or_eval`
- Matched terms: `agent_ops=[mcp, skills, агент, скил]; evals_quality=[метрик]; rag_retrieval_knowledge=[база знаний]; business_adoption=[enterprise]; creative_multimodal=[мультимод]; depth=[метрик]`
- Review: `unreviewed`

**NeuralDeep апдейт за две недели** (база знаний для агентов) Пара цифр для затравки: — 42 навыка и MCP сервера в каталоге (было 15 на старте) — 38 скиллов + 4 MCP сервера — 94 зарегистрированных пользователя — 426 установок через CLI — 16 авторов-контрибьюторов За последнюю неделю прилетело 10 новых поинтов от комьюнити: [DaData](https://neuraldeep.ru/skill/dadata-skills) (скилл + MCP) — проверка контрагентов, валидация адресов, 31 инструмент [Ozon Seller API](https://neuraldeep.ru/skill/ozon-seller-api-skill) — работа с маркетплейсом Ozon через агент [ZenMoney ](https://neuraldeep.ru/skill/zenmoney)— интеграция с финансовым трекером. [MPStats](https://neuraldeep.ru/skill/mpstats) — анал...

#### `neuraldeep:1902`

- Date: `2026-02-10`
- Coverage labels: `coding_agents`, `agent_ops`, `evals_quality`, `ai_product_pm`, `security_privacy_governance`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[claude code]; agent_ops=[mcp, агент]; evals_quality=[бенчмарк]; ai_product_pm=[продукт]; security_privacy_governance=[безопас]; model_landscape=[claude, llm, openai, модель]; depth=[бенчмарк]`
- Review: `unreviewed`

**Домашний ИИ-бот, который заказывает продукты из ВкусВилл** С нового года хотел попробовать [MCP-сервер ВкусВилл](https://t.me/neuraldeep/1833) и [OpenClaw](https://t.me/countwithsasha/443) — open-source фреймворк ([181k+ звёзд на GitHub](https://github.com/openclaw/openclaw)), который превращает LLM в Telegram-бота с навыками. Вчера Даша сказала: *нужен бот в чат с диетологом. Давай уже сделаем? * Быстро смотреть продукты, КБЖУ, собирать корзину. Основной поставщик у нашей семьи — ВкусВилл. Засел на вечер. 🧠 O**pus — дорого даже для домашнего бота ** Начал с Claude Opus 4.6. За 2 часа настройки и тестов с диетологом — $30. Для бота, который ищет творог — перебор. Подключать подписку Max...

#### `neuraldeep:1783`

- Date: `2025-12-07`
- Coverage labels: `coding_agents`, `agent_ops`, `evals_quality`, `rag_retrieval_knowledge`, `business_adoption`, `ai_ux_workflow`, `ai_engineering_infra`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[vibe coding]; agent_ops=[агент]; evals_quality=[бенчмарк]; rag_retrieval_knowledge=[rag]; business_adoption=[business, enterprise, эконом]; ai_ux_workflow=[workflow]; ai_engineering_infra=[инфра]; model_landscape=[anthropic, claude, llama, llm, openai, модель]; depth=[бенчмарк]`
- Review: `unreviewed`

**Я ставлю крест на RAG: почему поиск по базе — это теперь задача для джуна, а будущее — за Generic Agent** Байт засчитан =) Капля истории Мы с вами начали с фундамента AI-инфраструктуры тестировали [Llama](https://t.me/neuraldeep/984) на кластерах 4090, показывал вам тюн [Whisper](https://t.me/neuraldeep/978) и считали экономику on-premise [решений](https://t.me/neuraldeep/1366) Затем углубились в сложный RAG и Vibe Coding: заняли топ с малыми моделями в [Enterprise RAG Challenge](https://t.me/neuraldeep/1359) изучили [Circuit Tracing](https://t.me/neuraldeep/1637) для поиска галлюцинаций и научились собирать [MVP](https://t.me/neuraldeep/1510) за 7 дней В середине 2025 перешли к автоном...

#### `neuraldeep:1287`

- Date: `2025-01-24`
- Coverage labels: `general_ai_news`
- Depth label: `low_signal`
- Matched terms: `general_ai_news=[нейросет]`
- Review: `unreviewed`

⚡️ Благодаря Operator внутри ChatGPT наконец-то стало возможным использовать нейросети


## refat

Display: `Refat (Tech & AI)`
Channel: `nobilix`
Classified posts: `231`
Sampled posts: `8`

Sample coverage counts:
- `agent_ops`: 6
- `ai_engineering_infra`: 5
- `ai_product_pm`: 1
- `ai_ux_workflow`: 1
- `business_adoption`: 4
- `coding_agents`: 5
- `creative_multimodal`: 1
- `evals_quality`: 4
- `general_ai_news`: 1
- `model_landscape`: 7
- `rag_retrieval_knowledge`: 1
- `security_privacy_governance`: 4

Sample depth counts:
- `architecture_analysis`: 1
- `benchmark_or_eval`: 4
- `case_study`: 3

### Posts

#### `refat:253`

- Date: `2026-04-25`
- Coverage labels: `coding_agents`, `agent_ops`, `evals_quality`, `ai_product_pm`, `business_adoption`, `security_privacy_governance`, `ai_engineering_infra`, `model_landscape`, `creative_multimodal`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[codex, agentic coding, кодинг]; agent_ops=[tool calling, агент]; evals_quality=[бенчмарк]; ai_product_pm=[product, продукт]; business_adoption=[enterprise, эконом]; security_privacy_governance=[privacy, security]; ai_engineering_infra=[инфра]; model_landscape=[anthropic, claude, gemini, gpt, llm, openai]; creative_multimodal=[voice, мультимод]; depth=[бенчмарк]`
- Review: `unreviewed`

#ReDigest [Продолжаем](https://t.me/nobilix/250) субботнюю рубрику, тут я кратко рассказываю про новости из мира технологий и AI, которые привлекли мое внимание. **Дайджест недели:** - OpenAI [выпустила](https://openai.com/index/introducing-gpt-5-5/) GPT-5.5 - новый флагман для агентов. Цены $5/$30 за миллион токенов, контекст 1M. Заметно лучше токен-эффективность, высокие показатели terminal bench. - DeepSeek [показала](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf) V4 - Pro и Flash версии, контекст 1M токенов, расходует почти в 4 раза меньше вычислений и в 10 раз меньше памяти, чем V3.2 - сильный технический релиз, но нет мультимодальности и высокие галлюц...

#### `refat:246`

- Date: `2026-04-11`
- Coverage labels: `coding_agents`, `agent_ops`, `evals_quality`, `rag_retrieval_knowledge`, `business_adoption`, `security_privacy_governance`, `ai_engineering_infra`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[codex, claude code, вайб]; agent_ops=[агент]; evals_quality=[benchmark, бенчмарк]; rag_retrieval_knowledge=[embedding, knowledge base, эмбеддинг]; business_adoption=[arr, business, внедрен, эконом]; security_privacy_governance=[безопас]; ai_engineering_infra=[latency, инфра]; model_landscape=[anthropic, claude, gemini, gpt, model, openai]; depth=[benchmark, бенчмарк]`
- Review: `unreviewed`

#ReDigest [Продолжаем](https://t.me/nobilix/243) субботнюю рубрику, тут я кратко рассказываю про новости из мира технологий и AI, которые привлекли мое внимание. **Дайджест недели:** - Anthropic [представила](https://www-cdn.anthropic.com/08ab9158070959f88f296514c21b7facce6f52bc.pdf) Claude Mythos - модель, которую решили пока не раскатывать всем из-за опасений кибербезопасности. По бенчмаркам - большой апдейт. Вместо релиза *пока* [запустили](https://www.anthropic.com/glasswing) Project Glasswing - закрытый доступ для ~40 организаций для поиска уязвимостей в критическом софте. Скептики упрекают в хайпе, а минфин и ФРС США из-за этого релиза экстренно [предупредили](https://www.bloomberg....

#### `refat:225`

- Date: `2026-02-14`
- Coverage labels: `coding_agents`, `agent_ops`, `evals_quality`, `ai_ux_workflow`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[codex, cursor, кодинг]; agent_ops=[skills, агентн, агент, оркестрац]; evals_quality=[бенчмарк]; ai_ux_workflow=[воркфлоу]; model_landscape=[anthropic, claude, gemini, gpt, openai, модель]; depth=[бенчмарк]`
- Review: `unreviewed`

#ReDigest [Продолжаем](https://t.me/nobilix/220) субботнюю рубрику, тут я кратко рассказываю про новости из мира технологий и AI, которые привлекли мое внимание. **Дайджест недели:** - Bytedance [хайпят](https://x.com/levelsio/status/2021403820702552331) с Seedance 2.0 - новой SOTA видео-моделью с мощно подросшим качеством генерации и нативным аудио. - OpenAI [представила](https://openai.com/index/introducing-gpt-5-3-codex-spark/) GPT-5.3-Codex-Spark - компактную модель для кодинга в реальном времени, работающую на чипах Cerebras (>1000 t/s) - Google [выпустили](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-deep-think/) Gemini 3 Deep Think - обновленный...

#### `refat:59`

- Date: `2025-05-02`
- Coverage labels: `general_ai_news`
- Depth label: `architecture_analysis`
- Matched terms: `general_ai_news=[нейросет]; depth=[почему]`
- Review: `unreviewed`

Когда слышу фразы типа "наняли AI в команду" или "AI заменил мне продажника", хочется удариться лбом об стол. Антропоморфизм AI - не просто раздражающая маркетинговая хрень. Это вредно. Когда мы говорим "AI-продажник" или "AI-дизайнер", мы создаем ложные ожидания и сравнения. Представьте, что кто-то говорит: "Я нанял Excel в свою бухгалтерию". Абсурд? Именно. Но почему-то с нейросетями это стало нормой. Что на самом деле дал нам Gen AI: - Действительно крутое понимание человеческой речи и работа с ней - Генерация кода и структурированных данных: кмк, ключевая вещь вокруг которой крутится большинство инноваций в сфере AI - Генерация контента в других модальностях: картинки, аудио, видео И...

#### `refat:153`

- Date: `2025-09-03`
- Coverage labels: `agent_ops`, `evals_quality`, `business_adoption`, `security_privacy_governance`, `ai_engineering_infra`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `agent_ops=[агент]; evals_quality=[метрик]; business_adoption=[enterprise, внедрен]; security_privacy_governance=[безопас]; ai_engineering_infra=[observability, инфра]; model_landscape=[llm, openai, модель]; depth=[метрик]`
- Review: `unreviewed`

**Суть про Observability для AI-систем и ландшафт тулов на сегодня** Итак, обычный код работает предсказуемо - знаешь входные данные, понимаешь результат. С AI все иначе: появляется не детерминированный компонент, в agentic системах все еще сложнее. Поэтому Observability стал не роскошью, а базовой потребностью. Без трейсов ты не понимаешь, почему агент принял именно это решение, сколько это стоило и где система дала сбой, и какие вообще метрики - конкретные и в среднем. AI observability наследует ДНК от классических инструментов вроде Grafana и Sentry, но решает специфические задачи: - **Трейсинг вызовов**. В агентских системах одна задача может породить цепочку из десятков API-вызовов....

#### `refat:248`

- Date: `2026-04-17`
- Coverage labels: `agent_ops`, `ai_engineering_infra`, `model_landscape`
- Depth label: `case_study`
- Matched terms: `agent_ops=[skills, агентн, агент, скил]; ai_engineering_infra=[observability]; model_landscape=[claude, llm, model]; depth=[запустил]`
- Review: `unreviewed`

Что новенького в Mastra и чем это вам может быть полезно если вы пилите агентов + анонс стрима. В [июльском посте](https://t.me/nobilix/138) я писал про [Mastra](https://mastra.ai/) как недостающий слой в агентной разработке. Фреймворк активно развивался, в январе вышел и беты и получил стабильную версию и в целом адаптировал концепции, которые мне кажутся правильными: файловая система стала first-class примитивом (file-first подход!), подтянулись observability и evals, добавился контролируемый harness, студия стала помогать доменным экспертам котрибьютить. Пробежимся по главному. ◉ **Workspaces**s](https://mastra.ai/en/docs/workspace/overview)** **-** file-first примитив.** В [ноябрьском...

#### `refat:177`

- Date: `2025-11-01`
- Coverage labels: `coding_agents`, `agent_ops`, `business_adoption`, `security_privacy_governance`, `ai_engineering_infra`, `model_landscape`
- Depth label: `case_study`
- Matched terms: `coding_agents=[cursor, windsurf]; agent_ops=[multi-agent, агентн, агент]; business_adoption=[enterprise]; security_privacy_governance=[безопас]; ai_engineering_infra=[gpu]; model_landscape=[anthropic, claude, gemini, gpt, model, openai]; depth=[запустил]`
- Review: `unreviewed`

#ReDigest [Продолжаем](https://t.me/nobilix/174) субботнюю рубрику, тут я кратко рассказываю про новости из мира технологий и AI, которые привлекли мое внимание. **Дайджест недели:** - Вышла [MiniMax M2](https://huggingface.co/MiniMaxAI/MiniMax-M2) новая SOTA в опенсорсе с 230 млрд параметров (10 млрд активных). Вошла в топ-5 умнейших моделей по Artificial Analysis, обогнав Grok 4 Fast и показав паритет с Sonnet 4.5. Ограниченное время доступна бесплатно в API, потом будет стоить 8% от цены Sonnet. - Вышел [Cursor 2.0](https://cursor.com/blog/2-0) с собственной моделью Composer работает в 4 раза быстрее аналогов, завершает задачи меньше чем за 30 секунд. Интерфейс теперь multi-agent с воз...

#### `refat:79`

- Date: `2025-05-22`
- Coverage labels: `coding_agents`, `model_landscape`
- Depth label: `case_study`
- Matched terms: `coding_agents=[claude code]; model_landscape=[anthropic, claude, модель]; depth=[кейс]`
- Review: `unreviewed`

Сегодня вышло сразу две новых AI-модели от Anthropic: Claude Opus 4 и Claude Sonnet 4. Если вы любите кодить с помощью AI (как я), обновление вас явно порадует. Главная фишка - автономная работа. В тестах Opus 4 спокойно кодил 7 часов подряд без перерыва. Для сравнения: предыдущие версии выдыхались минут через 45. Теперь у Claude есть полноценная память через "memory files" - он сам сохраняет важную инфу и использует ее на протяжении всей сессии. Что еще крутого: - Гибридный подход: быстрые ответы для простых вопросов, глубокое размышление для сложных задач - Параллельное использование инструментов (веб-поиск, работа с файлами и тд) - На 65% меньше попыток срезать углы или использовать ко...


## silicbag

Display: `SilicBag`
Channel: `prompt_design`
Classified posts: `565`
Sampled posts: `8`

Sample coverage counts:
- `agent_ops`: 5
- `ai_engineering_infra`: 1
- `ai_product_pm`: 1
- `ai_ux_workflow`: 2
- `business_adoption`: 4
- `coding_agents`: 1
- `creative_multimodal`: 1
- `evals_quality`: 5
- `general_ai_news`: 1
- `model_landscape`: 4
- `rag_retrieval_knowledge`: 1
- `security_privacy_governance`: 1

Sample depth counts:
- `benchmark_or_eval`: 5
- `case_study`: 2
- `practitioner_experience`: 1

### Posts

#### `silicbag:2134`

- Date: `2026-04-29`
- Coverage labels: `evals_quality`, `business_adoption`
- Depth label: `benchmark_or_eval`
- Matched terms: `evals_quality=[метрик]; business_adoption=[roi, бизнес, внедрен]; depth=[метрик]`
- Review: `unreviewed`

У меня тут много тех, кто уже хорошо освоил искусственный интеллект в личных задачах и думает, как все это внедрить в процессы компании. Для вас ребята из AI Mindset запускают 3-недельный спринт AI-Native Organizations для фаундеров, CEOs, C-level и тимлидов, которым нужен не обзор инструментов, а рабочий ИИ-контур для команды и компании. Это про смыслы, архитектуру и новый организационный дизайн. Ближайший поток стартует 4 мая. Программа: **week 01 — PERSONAL OS + TEAM PROCESSES** от личных навыков к командным процессам артефакт: персональная OS, командные автоматизации, список 10 процессов **week 02 — INFRASTRUCTURE + ONTOLOGY** компания становится читаемой для AI артефакт: онтология ко...

#### `silicbag:2115`

- Date: `2026-04-24`
- Coverage labels: `evals_quality`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `evals_quality=[бенчмарк]; model_landscape=[модель]; depth=[бенчмарк]`
- Review: `unreviewed`

Вышла [новая модель](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/blob/main/DeepSeek_V4.pdf) - **DeepSeek V4. **Вот такой вот huídá (ответ) от китайцев!** **По** **бенчмаркам все довольно красиво. Пойду тестировать.

#### `silicbag:2075`

- Date: `2026-04-12`
- Coverage labels: `coding_agents`, `agent_ops`, `evals_quality`, `business_adoption`, `security_privacy_governance`, `model_landscape`, `creative_multimodal`
- Depth label: `benchmark_or_eval`
- Matched terms: `coding_agents=[codex, claude code]; agent_ops=[агентн, агент]; evals_quality=[метрик]; business_adoption=[бизнес]; security_privacy_governance=[безопас]; model_landscape=[claude, openai]; creative_multimodal=[voice]; depth=[метрик]`
- Review: `unreviewed`

Недавно Андрей Карпатый [отреагировал на комментарий](https://x.com/karpathy/status/2042334451611693415), и его публикация меня зацепила. Андрей описал то, что я давно пытался сформулировать. Он говорит, что видит растущий разрыв в понимании возможностей ИИ, и выделяет две группы пользователей: **Первая - **- те, кто попробовал бесплатный ChatGPT, допустим, в прошлом году и сразу составил мнение об ИИ. Это те, кто смеется над галлюцинациями моделей. Например, когда Advanced Voice Mode от OpenAI тупит над простейшими вопросами вроде «мне лучше ехать или идти пешком до автомойки». Проблема в том, что эти бесплатные и устаревшие чатботы вообще не отражают того, на что способны современные аг...

#### `silicbag:2068`

- Date: `2026-04-09`
- Coverage labels: `agent_ops`, `evals_quality`, `rag_retrieval_knowledge`, `ai_product_pm`, `ai_engineering_infra`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `agent_ops=[агент]; evals_quality=[eval, бенчмарк]; rag_retrieval_knowledge=[эмбеддинг]; ai_product_pm=[продукт]; ai_engineering_infra=[деплой]; model_landscape=[claude, llm, openai]; depth=[eval, бенчмарк]`
- Review: `unreviewed`

А давайте все же поговорим про Миллу Йовович и ее нашумевший продукт [MemPalace](https://github.com/milla-jovovich/mempalace)? А то из-за этой насыщенной на стримы и конференции недели не было времени поизучать GitHub-движуху. А там было жарко, 30к звезд и миллионы просмотров в Твиттере, это не шутки. Начнем с проблемы, которую решает этот продукт. Каждый раз, когда вы открываете новый чат с ChatGPT или Claude, вы разговариваете с собеседником, у которого полная амнезия. Помните, как в фильме Кристофера Нолана «Memento» (2000 г), где герой из-за травмы не может запоминать новое и ищет убийцу жены с помощью записок и татуировок? Так и Claude не помнит, что вчера вы два часа обсуждали архит...

#### `silicbag:1720`

- Date: `2025-11-11`
- Coverage labels: `agent_ops`, `evals_quality`, `business_adoption`, `ai_ux_workflow`, `model_landscape`
- Depth label: `benchmark_or_eval`
- Matched terms: `agent_ops=[агент]; evals_quality=[бенчмарк]; business_adoption=[эконом]; ai_ux_workflow=[воркфлоу]; model_landscape=[claude, llm, модель]; depth=[бенчмарк]`
- Review: `unreviewed`

Давно мы не говорили про автоматизацию и ИИ-агентов, но у меня немного подгорело, поэтому прошу слова. Недавно попросили сделать аудит одного воркфлоу на N8N по причине «зверского аппетита» на токены. В общем, как это часто бывает, подрядчик реализовал довольно скромный функционал автоматизации на самой жирной LLM’ке, до которой смог дотянуться. Понимаю, что чаще это делается не назло клиенту, а из-за того, что тестировать модели и изучать бенчмарки - скучно и долго. Ну, значит, этим придется заниматься заказчику, когда через несколько месяцев он поймет, что тратит на токены больше, чем платил бы сотрудникам. Поэтому давайте начнем с определения: «лучшая» модель - это та, что дает вам нуж...

#### `silicbag:2059`

- Date: `2026-04-03`
- Coverage labels: `general_ai_news`
- Depth label: `case_study`
- Matched terms: `general_ai_news=[искусственный интеллект]; depth=[кейс]`
- Review: `unreviewed`

В последнее время обожаю смотреть на рабочий календарь. Среди белых клеточек и синих черточек ищу тонкие полоски двадцатиминутных слотов с названием «ʞошэМ между Artem и …». Вместо точек там, конечно, имя стоит. Вот смотрю я на это имя и думаю: а кто этот человек, что его волнует, какая у него история, что он хочет запустить на рынке искусственного интеллекта или чего он боится? В назначенное время захожу в Гуглмит и первые секунды, пока идёт смолтолк, пытаюсь понять, кто передо мной: предприниматель, сотрудник крупной компании или студент... А дальше у нас начинается увлекательный разговор про жизнь, искусственный интеллект и что, блин, делать в этом безумном мире. Такой тет-а-тет созвон...

#### `silicbag:1835`

- Date: `2025-12-29`
- Coverage labels: `agent_ops`
- Depth label: `case_study`
- Matched terms: `agent_ops=[агентн, агент]; depth=[кейс]`
- Review: `unreviewed`

Антонио Гулли, техдир из Google, писал свою книгу, а точнее - практическое руководство по созданию ИИ-агентов «Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems», в формате опенсорса, выкладывая готовые главы в Google Docs. Получилось больше 400 страниц, рассказывающих про эволюцию агентных систем и паттерны, которые сейчас используются в ИИ-агентах; всё это снабжено кодом и реальными кейсами. Если вы занимаетесь ИИ-автоматизацией или агентами - советую почитать или хотя бы закинуть в блокнот на NotebookLM. [В PDF ](https://github.com/sarwarbeing-ai/Agentic_Design_Patterns/blob/main/Agentic_Design_Patterns.pdf) [В Google Docs](https://drive.google.com/file/d/1-5ho2...

#### `silicbag:1831`

- Date: `2025-12-25`
- Coverage labels: `agent_ops`, `business_adoption`, `ai_ux_workflow`
- Depth label: `practitioner_experience`
- Matched terms: `agent_ops=[агент]; business_adoption=[бизнес]; ai_ux_workflow=[human-in-the-loop]; depth=[опыт]`
- Review: `unreviewed`

Самый частый вопрос, который я слышу в эти дни: «Че там в 2026?» - тут и страх, и надежды, и попытки понять, как заработать. И я обязательно напишу свои мысли по трендам в ИИ на 2026 год, но сейчас хочу рассказать про один, только зарождающийся. Не будем отрицать тот факт, что самыми распиаренными услугами в этом году стали ИИ-агенты и ИИ-автоматизация. И программисты с опытом в ML, и вчерашние школьники, освоившие N8N, ломились в двери заводов, магазинов и булочных с уникальным предложением переложить всю рутину на плечи искусственного интеллекта. А заказчики это покупали: кто-то в надежде запрыгнуть в последний вагон уходящего ИИ-поезда, кто-то из желания увидеть ИИ-магию, ну а кто-то -...
