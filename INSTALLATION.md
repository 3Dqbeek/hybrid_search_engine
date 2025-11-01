# 📦 Руководство по установке и интеграции

## 📋 Содержание

1. [Требования](#требования)
2. [Установка из Docker](#установка-из-docker)
3. [Установка из исходников](#установка-из-исходников)
4. [Интеграция с существующей системой](#интеграция-с-существующей-системой)
5. [Конфигурация](#конфигурация)
6. [Загрузка данных](#загрузка-данных)
7. [Настройка весов](#настройка-весов)
8. [Оптимизация производительности](#оптимизация-производительности)

## Требования

### Обязательные

- **Docker** 20.10+
- **Docker Compose** 2.0+
- **Минимум 4GB RAM** (рекомендуется 8GB)

### Опциональные (для расширенных возможностей)

- **Python 3.11+** (для разработки)
- **LLM сервер** (LMStudio/Ollama) - для расширения запросов
- **E5-large модель** - для семантического поиска
- **PostgreSQL** - для хранения исходных данных

## Установка из Docker

### Шаг 1: Клонирование репозитория

```bash
git clone <repository-url>
cd hybrid_search_engine
```

### Шаг 2: Настройка переменных окружения

Создайте файл `.env`:

```bash
# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200
ELASTICSEARCH_INDEX=call_dialogues

# LLM (опционально, для расширения запросов)
LLM_URL=http://host.docker.internal:1234

# Embedding модель (опционально)
EMBEDDING_MODEL_PATH=/models/embeddings/intfloat_multilingual-e5-large

# API
API_BASE_URL=http://api:8000
DATABASE_URL=postgresql://user:password@postgres:5432/dbname
```

### Шаг 3: Запуск системы

```bash
# Запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f api
```

### Шаг 4: Проверка работы

```bash
# Проверка API
curl http://localhost:8005/health

# Тест поиска
curl -X POST "http://localhost:8005/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "тест", "limit": 5}'

# Открыть UI
# http://localhost:8503
```

## Установка из исходников

### Шаг 1: Установка зависимостей

```bash
# Создайте виртуальное окружение
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установите зависимости
pip install -r requirements.txt
```

### Шаг 2: Установка Elasticsearch

```bash
# Используя Docker
docker run -d \
  --name elasticsearch \
  -p 9200:9200 \
  -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  elasticsearch:8.11.0

# Или установите локально
# Следуйте инструкциям: https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html
```

### Шаг 3: Настройка окружения

```bash
export ELASTICSEARCH_URL="http://localhost:9200"
export LLM_URL="http://localhost:1234"  # Если используется
```

### Шаг 4: Запуск API

```bash
cd app
uvicorn api:app --host 0.0.0.0 --port 8005
```

### Шаг 5: Запуск UI

```bash
cd ui
streamlit run simple_search_ui.py --server.port 8503
```

## Интеграция с существующей системой

### Вариант 1: REST API интеграция

Простой способ - использовать REST API:

```python
import requests

def search_dialogues(query: str, limit: int = 10):
    response = requests.post(
        "http://localhost:8005/search",
        json={"query": query, "limit": limit}
    )
    return response.json()

# Использование
results = search_dialogues("покажи входящие диалоги")
for item in results["results"]:
    print(f"{item['call_id']} - {item['operator_name']}")
```

### Вариант 2: Python библиотека

Импортируйте напрямую:

```python
from hybrid_search import HybridSearchEngine

# Инициализация
engine = HybridSearchEngine(
    elasticsearch_url="http://localhost:9200",
    llm_url="http://localhost:1234",  # Опционально
    embedding_model=None  # Можете загрузить E5-large
)

# Поиск
results = engine.search("недовольный клиент", limit=10)
```

### Вариант 3: Docker Compose интеграция

Добавьте в ваш `docker-compose.yml`:

```yaml
services:
  hybrid_search:
    build: ./hybrid_search_engine
    ports:
      - "8005:8000"
    environment:
      - ELASTICSEARCH_URL=http://your_elasticsearch:9200
      - LLM_URL=http://your_llm:1234
    depends_on:
      - your_elasticsearch
```

## Конфигурация

### Структура индекса Elasticsearch

Система ожидает следующие поля в документах:

```json
{
  "mappings": {
    "properties": {
      "call_id": {"type": "keyword"},
      "call_type": {"type": "keyword"},
      "operator_name": {"type": "text", "analyzer": "russian"},
      "text_full": {"type": "text", "analyzer": "russian"},
      "text_summary": {"type": "text", "analyzer": "russian"},
      "tags": {"type": "keyword"},
      "qa_total_score": {"type": "integer"},
      "qa_critical_violation": {"type": "boolean"},
      "problem_call_has": {"type": "boolean"},
      "empathy_count": {"type": "integer"},
      "no_go_count": {"type": "integer"}
    }
  }
}
```

### Создание индекса

```python
from elasticsearch import Elasticsearch

es = Elasticsearch([ELASTICSEARCH_URL])

# Удалить существующий индекс (если нужно)
if es.indices.exists(index="call_dialogues"):
    es.indices.delete(index="call_dialogues")

# Создать новый
index_body = {
    "settings": {
        "analysis": {
            "analyzer": {
                "russian": {
                    "type": "standard"  # Или используйте русский анализатор
                }
            }
        }
    },
    "mappings": {
        "properties": {
            # ... поля как выше
        }
    }
}

es.indices.create(index="call_dialogues", body=index_body)
```

## Загрузка данных

### Из PostgreSQL

```python
import asyncpg
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

async def load_from_postgresql():
    # Подключение к PostgreSQL
    conn = await asyncpg.connect(DATABASE_URL)
    rows = await conn.fetch("SELECT * FROM dialogues")
    
    # Индексация в Elasticsearch
    es = Elasticsearch([ELASTICSEARCH_URL])
    actions = []
    
    for row in rows:
        doc = {
            "call_id": row['call_id'],
            "call_type": row['call_type'],
            "operator_name": row['operator_name'],
            "text_full": row['text_full'],
            "text_summary": row['text_summary'],
            # ... остальные поля
        }
        actions.append({
            "_index": "call_dialogues",
            "_id": row['id'],
            "_source": doc
        })
    
    bulk(es, actions)
    await conn.close()
```

### Из JSON файлов

```python
import json
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

def load_from_json(json_file):
    es = Elasticsearch([ELASTICSEARCH_URL])
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    actions = []
    for item in data:
        actions.append({
            "_index": "call_dialogues",
            "_id": item['call_id'],
            "_source": item
        })
    
    bulk(es, actions)
```

### Использование API

```bash
# Если есть эндпоинт загрузки
curl -X POST "http://localhost:8005/load-data" \
  -H "Content-Type: application/json" \
  -d @data.json
```

## Настройка весов

Веса определяют важность каждого компонента в финальном скоре:

```python
from hybrid_search import HybridSearchEngine

engine = HybridSearchEngine(...)

# Настройка весов
engine.update_weights({
    'bm25': 0.30,           # Для точных запросов
    'semantic': 0.25,       # Для косвенных запросов
    'keyword_density': 0.25, # Для частоты слов
    'exact_match': 0.15,     # Для точных совпадений
    'context_boost': 0.08,   # Для контекста
    'proximity_bonus': 0.05, # Для близости слов
    'position_bonus': 0.02   # Для позиции
})
```

### Рекомендации по настройке

- **Для точных запросов**: Увеличьте `bm25` и `exact_match`
- **Для косвенных запросов**: Увеличьте `semantic` и `context_boost`
- **Для частотных запросов**: Увеличьте `keyword_density`

## Оптимизация производительности

### 1. Кэширование запросов

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(query: str, limit: int):
    return engine.search(query, limit)
```

### 2. Оптимизация Elasticsearch

```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "30s"
  }
}
```

### 3. Batch обработка

```python
# Обработка множественных запросов
queries = ["запрос 1", "запрос 2", "запрос 3"]
results = [engine.search(q, limit=10) for q in queries]
```

### 4. Индексация embeddings (для больших объемов)

```python
# Предварительно индексируйте embeddings для документов
# Это ускорит semantic search
```

## Отладка

### Проверка логов

```bash
# Логи API
docker-compose logs -f api

# Логи Elasticsearch
docker-compose logs -f elasticsearch
```

### Тестирование компонентов

```python
# Тест QueryAnalyzer
from hybrid_search import QueryAnalyzer
analyzer = QueryAnalyzer("http://localhost:1234")
analysis = analyzer.analyze("покажи входящие диалоги")
print(analysis)

# Тест Keyword Density
from hybrid_search import KeywordDensityScorer
scorer = KeywordDensityScorer()
score = scorer.score(["входящие", "диалоги"], "текст диалога...")
print(score)
```

## Поддержка

При возникновении проблем:

1. Проверьте логи: `docker-compose logs`
2. Проверьте статус: `curl http://localhost:8005/health`
3. Проверьте подключение к Elasticsearch: `curl http://localhost:9200`
4. Откройте issue в репозитории

## Следующие шаги

1. Загрузите свои данные в Elasticsearch
2. Настройте веса под ваши задачи
3. Протестируйте на ваших запросах
4. Оптимизируйте под вашу нагрузку

