# Task 1 Plan: Call an LLM from Code

## LLM Provider

- **Provider**: Qwen Code API
- **Model**: `qwen3-coder-plus`
- **API Base**: `http://10.93.24.238:42005/v1` (OpenAI-compatible endpoint)
- **Authentication**: API key from `.env.agent.secret` (`LLM_API_KEY`)

## Architecture

```
CLI input → agent.py → HTTP request → Qwen API → JSON response → stdout
```

## Implementation Steps

### 1. Environment Setup
- Read configuration from `.env.agent.secret`:
  - `LLM_API_KEY` — API ключ
  - `LLM_API_BASE` — базовый URL API
  - `LLM_MODEL` — имя модели
- Использовать `pydantic-settings` для загрузки переменных окружения

### 2. Agent Structure
- **Input**: вопрос как первый аргумент командной строки
- **Output**: JSON с полями:
  - `answer` (string) — ответ от LLM
  - `tool_calls` (array) — пустой массив (будет заполнен в Task 2)

### 3. LLM API Call
- Использовать `httpx` для HTTP-запросов (уже есть в зависимостях)
- Формат запроса — OpenAI-compatible chat completions API:
  ```json
  POST /chat/completions
  {
    "model": "qwen3-coder-plus",
    "messages": [{"role": "user", "content": "<question>"}]
  }
  ```
- Timeout: 60 секунд

### 4. Output Formatting
- В stdout: только валидный JSON одной строкой
- В stderr: все отладочные сообщения (использовать `print(..., file=sys.stderr)`)
- Exit code 0 при успехе

### 5. Error Handling
- Обработка ошибок сети (timeout, connection error)
- Обработка ошибок API (неверный ключ, 4xx/5xx ответы)
- Валидация JSON-ответа перед выводом

## Dependencies

Используем существующие зависимости из `pyproject.toml`:
- `httpx` — для HTTP-запросов
- `pydantic-settings` — для загрузки конфигурации

## Testing Strategy

Один регрессионный тест:
1. Запустить `agent.py` с тестовым вопросом как subprocess
2. Распарсить stdout как JSON
3. Проверить наличие полей `answer` (string) и `tool_calls` (array)
