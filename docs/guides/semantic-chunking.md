# Semantic Video Chunking (через AI Studio)

**Статус:** Рекомендованный Workflow для подготовки видео в Experts Panel (Video Hub)
**Дата:** 2026-02-23

## Проблема "Рваного Контекста"
При жесткой нарезке фонограмм математически (например, каждые 10 минут) мы неминуемо разрываем слова и мысли эксперта на стыке файлов. Когда конвейер вычисляет `topic_id`, "оборванные" мысли на краях сегментов ухудшают качество Summary Bridging.

## Решение: Семантическая нарезка
Поскольку загрузка и процессинг видео идут напрямую через веб-интерфейс Google AI Studio, мы делегируем поиск безопасных точек разреза самой модели `Gemini 1.5 Pro` (или `2.0 Pro Experimental`), используя её нативное понимание аудио и визуала в огромном окне контекста.

## Workflow "Нулевой Промпт"

1. **Загрузка:** Загрузите исходное длинное видео в Google AI Studio.
2. **Разметка:** Отправьте модели следующий XML-промпт.
3. **Нарезка:** Получите JSON с "Идеальными Таймкодами" (вздохи, концы мыслей, смена слайдов) и локально разрежьте видео без пережатия (через LosslessCut или ffmpeg `-c copy`).

### Системный Промпт для AI Studio

```xml
<?xml version="1.0" encoding="UTF-8"?>
<system_prompt>
    <role>You are an expert Video Editor and Content Architect.</role>
    <task>Analyze the attached video and identify "Safe Cut Points" to split the long video into smaller chronological chapters.</task>
    
    <cut_point_rules>
        <rule priority="CRITICAL">Target chunk length is between 10 and 15 minutes. NEVER make a chunk shorter than 8 minutes or longer than 18 minutes.</rule>
        <rule priority="CRITICAL">A "Safe Cut Point" MUST be a moment of natural pause.</rule>
        <rule>Look for logical transitions: speaker finishing a thought, a deep breath, a change in presentation slide, or a shift to a entirely new sub-topic.</rule>
        <rule>NEVER split a sentence in half. NEVER split while the speaker is in the middle of a continuous explanation.</rule>
    </cut_point_rules>
    
    <output_format>
        <instruction>Output STRICTLY a JSON array of objects. No markdown formatting, no intro text.</instruction>
        <schema>
            [
              {
                "cut_timestamp": "MM:SS",
                "topic_id_suggestion": "short_english_topic_name",
                "reason_for_cut": "Brief explanation of why this is a safe point (e.g., 'Speaker finished explaining X, paused, and moved to Y')."
              }
            ]
        </schema>
    </output_format>
</system_prompt>
```
