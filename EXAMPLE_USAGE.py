"""
Примеры использования гибридного поискового движка
"""

# ============================================
# ПРИМЕР 1: REST API (Python)
# ============================================

import requests

def search_via_api(query: str, limit: int = 10):
    """Поиск через REST API"""
    response = requests.post(
        "http://localhost:8005/search",
        json={"query": query, "limit": limit},
        timeout=30
    )
    response.raise_for_status()
    return response.json()

# Использование
results = search_via_api("покажи входящие диалоги", limit=5)
for item in results["results"]:
    print(f"{item['call_id']} - {item['operator_name']}")
    print(f"Релевантность: {item['relevance_score']:.2f}")


# ============================================
# ПРИМЕР 2: Прямое использование Python
# ============================================

from app.hybrid_search import HybridSearchEngine

# Инициализация
engine = HybridSearchEngine(
    elasticsearch_url="http://localhost:9200",
    llm_url="http://localhost:1234",  # Опционально
    embedding_model=None  # Опционально, можно загрузить E5-large
)

# Поиск
results = engine.search("недовольный клиент", limit=10)

# Обработка результатов
for item in results["results"]:
    print(f"Call ID: {item['call_id']}")
    print(f"Оператор: {item['operator_name']}")
    print(f"Релевантность: {item['semantic_score']:.2f}")
    print(f"Причина: {item['relevance_reason']}")
    print(f"Score breakdown: {item['score_breakdown']}")


# ============================================
# ПРИМЕР 3: Настройка весов
# ============================================

# Изменить веса под ваши задачи
engine.update_weights({
    'bm25': 0.40,           # Увеличить BM25 для точных запросов
    'semantic': 0.20,
    'keyword_density': 0.25,
    'exact_match': 0.10,
    'context_boost': 0.05
})


# ============================================
# ПРИМЕР 4: Пакетная обработка
# ============================================

queries = [
    "покажи входящие диалоги",
    "недовольный клиент",
    "проблемы с оператором"
]

results_batch = []
for query in queries:
    result = engine.search(query, limit=5)
    results_batch.append({
        "query": query,
        "results": result["results"],
        "total": result["total"]
    })


# ============================================
# ПРИМЕР 5: Использование отдельных компонентов
# ============================================

from app.hybrid_search import QueryAnalyzer, KeywordDensityScorer

# Анализ запроса
analyzer = QueryAnalyzer("http://localhost:1234")
analysis = analyzer.analyze("покажи входящие диалоги")
print(f"Intent: {analysis['intent']}")
print(f"Keywords: {analysis['keywords']}")
print(f"Expanded: {analysis['expanded_query']}")

# Подсчет плотности ключевых слов
scorer = KeywordDensityScorer()
score = scorer.score(
    ["входящие", "диалоги"],
    "Полный текст диалога с ключевыми словами..."
)
print(f"Density Score: {score['density_score']}")
print(f"Proximity Bonus: {score['proximity_bonus']}")
print(f"Position Bonus: {score['position_bonus']}")

