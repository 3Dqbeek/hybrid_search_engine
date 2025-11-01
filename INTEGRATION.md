# 🔌 Руководство по интеграции

## 📋 Содержание

1. [Варианты интеграции](#варианты-интеграции)
2. [REST API интеграция](#rest-api-интеграция)
3. [Python библиотека](#python-библиотека)
4. [Docker интеграция](#docker-интеграция)
5. [Elasticsearch интеграция](#elasticsearch-интеграция)
6. [Примеры использования](#примеры-использования)

## Варианты интеграции

### 1. REST API (Рекомендуется)

Самый простой способ - использовать REST API через HTTP запросы.

**Преимущества:**
- ✅ Независимость от языка программирования
- ✅ Легко масштабировать
- ✅ Простая отладка

**Недостатки:**
- ⚠️ Сетевая задержка
- ⚠️ Требует HTTP сервер

### 2. Python библиотека

Прямое использование Python классов.

**Преимущества:**
- ✅ Нет сетевых задержек
- ✅ Полный контроль
- ✅ Можно кастомизировать

**Недостатки:**
- ⚠️ Только Python
- ⚠️ Требует установки зависимостей

### 3. Docker Compose

Интеграция как Docker сервис.

**Преимущества:**
- ✅ Изоляция
- ✅ Легко развернуть
- ✅ Управление зависимостями

## REST API интеграция

### Базовый пример

```python
import requests

class HybridSearchClient:
    def __init__(self, api_url="http://localhost:8005"):
        self.api_url = api_url
    
    def search(self, query: str, limit: int = 10):
        """Выполнить поиск"""
        response = requests.post(
            f"{self.api_url}/search",
            json={"query": query, "limit": limit},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    
    def health_check(self):
        """Проверить состояние API"""
        response = requests.get(f"{self.api_url}/health")
        return response.json()

# Использование
client = HybridSearchClient()

# Поиск
results = client.search("покажи входящие диалоги", limit=10)
for item in results["results"]:
    print(f"{item['call_id']} - {item['operator_name']}")
    print(f"Релевантность: {item['relevance_score']:.2f}")
```

### Интеграция в Flask приложение

```python
from flask import Flask, request, jsonify
from hybrid_search_client import HybridSearchClient

app = Flask(__name__)
search_client = HybridSearchClient("http://hybrid-search-api:8005")

@app.route("/api/search", methods=["POST"])
def search():
    data = request.json
    query = data.get("query", "")
    limit = data.get("limit", 10)
    
    results = search_client.search(query, limit)
    return jsonify(results)
```

### Интеграция в Django приложение

```python
# views.py
from django.http import JsonResponse
from hybrid_search_client import HybridSearchClient

search_client = HybridSearchClient()

def search_view(request):
    query = request.GET.get('q', '')
    limit = int(request.GET.get('limit', 10))
    
    results = search_client.search(query, limit)
    return JsonResponse(results)
```

## Python библиотека

### Прямое использование

```python
from hybrid_search import HybridSearchEngine
from elasticsearch import Elasticsearch

# Инициализация
engine = HybridSearchEngine(
    elasticsearch_url="http://localhost:9200",
    llm_url="http://localhost:1234",  # Опционально
    embedding_model=None  # Опционально
)

# Поиск
results = engine.search("недовольный клиент", limit=10)

# Обработка результатов
for item in results["results"]:
    print(f"Call ID: {item['call_id']}")
    print(f"Оператор: {item['operator_name']}")
    print(f"Релевантность: {item['semantic_score']:.2f}")
    print(f"Причина: {item['relevance_reason']}")
    print(f"Breakdown: {item['score_breakdown']}")
```

### Кастомизация весов

```python
# Изменить веса под ваши задачи
engine.update_weights({
    'bm25': 0.40,           # Больше веса на BM25
    'semantic': 0.20,
    'keyword_density': 0.25,
    'exact_match': 0.10,
    'context_boost': 0.05
})
```

### Использование отдельных компонентов

```python
from hybrid_search import QueryAnalyzer, KeywordDensityScorer

# Анализ запроса
analyzer = QueryAnalyzer("http://localhost:1234")
analysis = analyzer.analyze("покажи входящие диалоги")
print(f"Intent: {analysis['intent']}")
print(f"Keywords: {analysis['keywords']}")

# Подсчет плотности ключевых слов
scorer = KeywordDensityScorer()
score = scorer.score(
    ["входящие", "диалоги"],
    "Полный текст диалога..."
)
print(f"Density: {score['density_score']}")
```

## Docker интеграция

### Добавление в существующий docker-compose.yml

```yaml
version: '3.8'

services:
  # Ваши существующие сервисы
  your_app:
    # ...
  
  # Гибридный поисковый движок
  hybrid_search:
    build: ./hybrid_search_engine
    container_name: hybrid_search_api
    ports:
      - "8005:8000"
    environment:
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - LLM_URL=http://host.docker.internal:1234
      - EMBEDDING_MODEL_PATH=/models/embeddings/intfloat_multilingual-e5-large
    volumes:
      - ./models:/models
    depends_on:
      - elasticsearch
    networks:
      - your_network
  
  # Используйте существующий Elasticsearch или создайте новый
  elasticsearch:
    image: elasticsearch:8.11.0
    # ... конфигурация

networks:
  your_network:
    driver: bridge
```

### Использование в коде через Docker сеть

```python
import requests

# Внутри Docker сети
api_url = "http://hybrid_search:8000"

# С хоста
api_url = "http://localhost:8005"
```

## Elasticsearch интеграция

### Существующий индекс

Если у вас уже есть Elasticsearch с данными:

```python
from hybrid_search import HybridSearchEngine

# Просто укажите URL вашего Elasticsearch
engine = HybridSearchEngine(
    elasticsearch_url="http://your-elasticsearch:9200",
    llm_url=None,  # Если не используете LLM
    embedding_model=None  # Если не используете embeddings
)

# Система автоматически найдет индекс и будет работать
results = engine.search("ваш запрос")
```

### Миграция данных

```python
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

# Подключение к старому Elasticsearch
old_es = Elasticsearch(["http://old-es:9200"])

# Подключение к новому
new_es = Elasticsearch(["http://new-es:9200"])

# Скопировать документы
old_index = "old_dialogues"
new_index = "call_dialogues"

# Получить все документы
query = {"query": {"match_all": {}}}
scroll = old_es.search(index=old_index, scroll="2m", size=1000, body=query)
sid = scroll['_scroll_id']
scroll_size = len(scroll['hits']['hits'])

actions = []
while scroll_size > 0:
    for doc in scroll['hits']['hits']:
        actions.append({
            "_index": new_index,
            "_id": doc['_id'],
            "_source": doc['_source']
        })
    
    scroll = old_es.scroll(scroll_id=sid, scroll="2m")
    sid = scroll['_scroll_id']
    scroll_size = len(scroll['hits']['hits'])

# Bulk индексация
bulk(new_es, actions)
```

## Примеры использования

### Пример 1: Поиск в веб-приложении

```python
# app.py (Flask)
from flask import Flask, render_template, request, jsonify
from hybrid_search_client import HybridSearchClient

app = Flask(__name__)
client = HybridSearchClient("http://localhost:8005")

@app.route("/")
def index():
    return render_template("search.html")

@app.route("/api/search", methods=["POST"])
def api_search():
    query = request.json.get("query", "")
    limit = request.json.get("limit", 10)
    
    results = client.search(query, limit)
    return jsonify(results)
```

```html
<!-- templates/search.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Поиск</title>
</head>
<body>
    <input type="text" id="searchInput" placeholder="Введите запрос...">
    <button onclick="search()">Поиск</button>
    
    <div id="results"></div>
    
    <script>
    async function search() {
        const query = document.getElementById('searchInput').value;
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({query: query, limit: 10})
        });
        const data = await response.json();
        
        // Отображение результатов
        const resultsDiv = document.getElementById('results');
        resultsDiv.innerHTML = data.results.map(r => `
            <div>
                <h3>${r.call_id} - ${r.operator_name}</h3>
                <p>Релевантность: ${r.relevance_score.toFixed(2)}</p>
                <p>${r.text_summary}</p>
            </div>
        `).join('');
    }
    </script>
</body>
</html>
```

### Пример 2: Пакетная обработка запросов

```python
from hybrid_search import HybridSearchEngine

engine = HybridSearchEngine(...)

queries = [
    "покажи входящие диалоги",
    "недовольный клиент",
    "проблемы с оператором",
    "где клиент ничего не купил"
]

# Обработка всех запросов
results_batch = []
for query in queries:
    result = engine.search(query, limit=5)
    results_batch.append({
        "query": query,
        "results": result["results"],
        "total": result["total"]
    })

# Анализ результатов
for batch in results_batch:
    print(f"Запрос: {batch['query']}")
    print(f"Найдено: {batch['total']}")
    for r in batch['results'][:3]:
        print(f"  - {r['call_id']} (релевантность: {r['semantic_score']:.2f})")
```

### Пример 3: Мониторинг качества поиска

```python
from hybrid_search import HybridSearchEngine
import json

engine = HybridSearchEngine(...)

# Тестовые запросы с ожидаемыми результатами
test_cases = [
    {
        "query": "покажи входящие диалоги",
        "expected_call_type": "Входящий звонок",
        "min_relevance": 50
    },
    {
        "query": "недовольный клиент",
        "expected_problem": True,
        "min_relevance": 40
    }
]

# Запуск тестов
for test in test_cases:
    results = engine.search(test["query"], limit=10)
    
    # Проверка релевантности
    first_result = results["results"][0] if results["results"] else None
    
    if first_result:
        relevance_ok = first_result['semantic_score'] >= test.get('min_relevance', 0)
        
        # Проверка типа звонка
        call_type_ok = True
        if 'expected_call_type' in test:
            call_type_ok = first_result['call_type'] == test['expected_call_type']
        
        print(f"Запрос: {test['query']}")
        print(f"  Релевантность: {'✅' if relevance_ok else '❌'}")
        print(f"  Тип звонка: {'✅' if call_type_ok else '❌'}")
```

## Обработка ошибок

```python
from hybrid_search_client import HybridSearchClient
import requests

client = HybridSearchClient()

def safe_search(query: str, limit: int = 10):
    """Безопасный поиск с обработкой ошибок"""
    try:
        results = client.search(query, limit)
        return results
    except requests.exceptions.ConnectionError:
        return {"error": "Не удалось подключиться к API"}
    except requests.exceptions.Timeout:
        return {"error": "Таймаут запроса"}
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP ошибка: {e}"}
    except Exception as e:
        return {"error": f"Неизвестная ошибка: {e}"}
```

## Оптимизация для продакшена

### 1. Кэширование

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=1000)
def cached_search(query_hash: str):
    # Используйте Redis для распределенного кэша
    pass

def search_with_cache(query: str, limit: int = 10):
    query_hash = hashlib.md5(f"{query}:{limit}".encode()).hexdigest()
    return cached_search(query_hash)
```

### 2. Rate Limiting

```python
from time import time

class RateLimitedClient:
    def __init__(self, max_requests=10, time_window=60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
    
    def search(self, query: str, limit: int = 10):
        now = time()
        # Удалить старые запросы
        self.requests = [r for r in self.requests if now - r < self.time_window]
        
        if len(self.requests) >= self.max_requests:
            raise Exception("Rate limit exceeded")
        
        self.requests.append(now)
        return client.search(query, limit)
```

### 3. Асинхронная обработка

```python
import asyncio
import aiohttp

async def async_search(query: str, limit: int = 10):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8005/search",
            json={"query": query, "limit": limit}
        ) as response:
            return await response.json()

# Обработка множественных запросов параллельно
async def batch_search(queries):
    tasks = [async_search(q) for q in queries]
    return await asyncio.gather(*tasks)
```

## Заключение

Гибридный поисковый движок может быть интегрирован различными способами:

1. **REST API** - для микросервисной архитектуры
2. **Python библиотека** - для Python приложений
3. **Docker сервис** - для контейнеризованных систем

Выберите подход, который лучше всего подходит для вашей архитектуры!

