"""
API модуль для интеграции гибридного поискового движка
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from app.hybrid_search import HybridSearchEngine
from elasticsearch import Elasticsearch

app = FastAPI(title="Hybrid Search Engine API", version="1.0.0")

# Конфигурация
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
LLM_URL = os.getenv("LLM_URL", "http://localhost:1234")
INDEX_NAME = os.getenv("ELASTICSEARCH_INDEX", "call_dialogues")

# Глобальный экземпляр поискового движка
hybrid_search_engine: Optional[HybridSearchEngine] = None

# Модели данных
class SearchRequest(BaseModel):
    query: str
    limit: int = 10

class SearchResult(BaseModel):
    call_id: str
    call_type: str
    operator_name: str
    qa_total_score: int
    qa_critical_violation: bool
    tags: List[str]
    text_summary: str
    relevance_score: float
    score_breakdown: Optional[Dict[str, float]] = None
    relevance_reason: Optional[str] = None

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    query: str

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    global hybrid_search_engine
    
    import time
    max_retries = 30
    
    # Ждем готовности Elasticsearch
    es = Elasticsearch([ELASTICSEARCH_URL])
    for i in range(max_retries):
        try:
            if es.ping():
                print(f"✅ Elasticsearch подключен")
                break
        except Exception as e:
            print(f"⏳ Ожидание Elasticsearch... ({i+1}/{max_retries})")
        
        if i < max_retries - 1:
            time.sleep(2)
    else:
        print("❌ Не удалось подключиться к Elasticsearch")
        return
    
    # Инициализируем гибридный поисковый движок
    try:
        # Пытаемся загрузить embedding модель (опционально)
        embedding_model = None
        try:
            from sentence_transformers import SentenceTransformer
            local_model_path = os.getenv("EMBEDDING_MODEL_PATH", "/models/embeddings/intfloat_multilingual-e5-large")
            if os.path.exists(local_model_path):
                embedding_model = SentenceTransformer(local_model_path, device='cpu')
                print(f"✅ Embedding модель загружена")
        except Exception as e:
            print(f"⚠️ Embedding модель недоступна: {e}")
        
        hybrid_search_engine = HybridSearchEngine(ELASTICSEARCH_URL, LLM_URL, embedding_model)
        print("✅ Гибридный поисковый движок инициализирован")
    except Exception as e:
        print(f"❌ Ошибка инициализации: {e}")

@app.get("/")
async def root():
    return {
        "message": "Hybrid Search Engine API",
        "version": "1.0.0",
        "status": "running"
    }

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """Гибридный поиск с многоуровневым ранжированием"""
    if not hybrid_search_engine:
        raise HTTPException(status_code=503, detail="Поисковый движок не инициализирован")
    
    try:
        result = hybrid_search_engine.search(request.query, request.limit)
        
        # Преобразуем в формат API
        search_results = []
        for item in result.get("results", []):
            search_results.append(SearchResult(
                call_id=item.get("call_id", ""),
                call_type=item.get("call_type", ""),
                operator_name=item.get("operator_name", ""),
                qa_total_score=item.get("qa_total_score", 0),
                qa_critical_violation=item.get("qa_critical_violation", False),
                tags=item.get("tags", []),
                text_summary=item.get("text_summary", ""),
                relevance_score=item.get("semantic_score", 0),
                score_breakdown=item.get("score_breakdown"),
                relevance_reason=item.get("relevance_reason")
            ))
        
        return SearchResponse(
            results=search_results,
            total=result.get("total", 0),
            query=request.query
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/health")
async def health():
    """Проверка состояния системы"""
    es = Elasticsearch([ELASTICSEARCH_URL])
    es_status = "connected" if es.ping() else "disconnected"
    
    return {
        "status": "healthy" if hybrid_search_engine else "degraded",
        "elasticsearch": es_status,
        "search_engine": "initialized" if hybrid_search_engine else "not_initialized"
    }

