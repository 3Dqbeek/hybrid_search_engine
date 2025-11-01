import os
import json
import requests
import logging
from typing import List, Dict, Any, Optional
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
import numpy as np

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QualitySemanticSearch:
    """Качественный семантический поиск с Russian embeddings и продвинутыми промптами"""
    
    def __init__(self, elasticsearch_url: str, llm_url: str):
        self.es = Elasticsearch([elasticsearch_url])
        self.llm_url = llm_url
        self.index_name = "call_dialogues"
        
        # Загружаем модель E5-large из локальной директории
        local_model_path = "/models/embeddings/intfloat_multilingual-e5-large"
        
        try:
            import os
            if os.path.exists(local_model_path):
                logger.info(f"🔄 Загружаем E5-large из локальной директории: {local_model_path}")
                try:
                    self.embedding_model = SentenceTransformer(local_model_path, device='cpu', trust_remote_code=True)
                    logger.info("✅ E5-large модель embeddings загружена из локальной директории")
                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки E5-large: {e}")
                    # Пробуем загрузить без trust_remote_code
                    try:
                        import warnings
                        warnings.filterwarnings('ignore')
                        self.embedding_model = SentenceTransformer(local_model_path, device='cpu')
                        logger.info("✅ E5-large загружена с игнорированием предупреждений")
                    except Exception as e2:
                        logger.error(f"❌ Не удалось загрузить модель: {e2}")
                        self.embedding_model = None
            else:
                logger.warning(f"⚠️ Локальная модель не найдена: {local_model_path}")
                logger.info("🔄 Используем LLM-усиленный поиск без ML модели")
                self.embedding_model = None
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели из {local_model_path}: {e}")
            logger.info("🔄 Используем fallback на LLM промпты")
            self.embedding_model = None
    
    def enhance_query_with_llm(self, query: str, query_type: str = "search") -> Dict[str, Any]:
        """Улучшение запроса с помощью LLM с продвинутым промптингом"""
        try:
            # Продвинутый промпт для улучшения семантики поиска
            enhanced_prompt = f"""
Ты эксперт по анализу диалогов колл-центра. Проанализируй запрос пользователя и преобразуй его в оптимальный поисковый запрос.

ТИП ЗАПРОСА: {query_type}
ИСХОДНЫЙ ЗАПРОС: "{query}"

ТВОЯ ЗАДАЧА:
1. Определи истинное намерение пользователя
2. Извлеки ключевые концепции (не слова!)
3. Расширь запрос семантически связанными понятиями
4. Добавь контекстные термины из области колл-центра

ПРИМЕРЫ:
- "покажи входящие" → концепция: "тип вызова", "вход", "клиент звонит"
- "недоволен клиент" → концепции: "жалоба", "недовольство", "проблема", "протест", "расстройство", "негативные эмоции"
- "грубый оператор" → концепции: "невежливость", "хамство", "грубость", "неуважение", "неучтивость"

ОТВЕТ:
Ответь ТОЛЬКО JSON с полями:
{{
    "enhanced_query": "расширенный запрос для поиска",
    "concepts": ["ключевая концепция 1", "концепция 2", ...],
    "query_intent": "описание намерения",
    "search_focus": "на чем фокусироваться в поиске"
}}
"""
            
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": "qwen/qwen3-coder-30b",
                    "messages": [{"role": "user", "content": enhanced_prompt}],
                    "max_tokens": 300,
                    "temperature": 0.2
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result['choices'][0]['message']['content'].strip()
                
                # Парсим JSON ответ
                try:
                    # Убираем markdown форматирование если есть
                    if '```json' in llm_response:
                        llm_response = llm_response.split('```json')[1].split('```')[0].strip()
                    elif '```' in llm_response:
                        llm_response = llm_response.split('```')[1].split('```')[0].strip()
                    
                    enhanced_data = json.loads(llm_response)
                    logger.info(f"✅ LLM улучшил запрос: {enhanced_data}")
                    return enhanced_data
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ LLM не вернул валидный JSON, используем текст как есть")
                    return {
                        "enhanced_query": llm_response,
                        "concepts": query.split(),
                        "query_intent": "general",
                        "search_focus": "general"
                    }
            else:
                logger.warning(f"⚠️ LLM недоступен (status: {response.status_code})")
                return self._fallback_enhancement(query)
                
        except Exception as e:
            logger.warning(f"⚠️ Ошибка LLM: {e}, используем fallback")
            return self._fallback_enhancement(query)
    
    def _fallback_enhancement(self, query: str) -> Dict[str, Any]:
        """Fallback улучшение без LLM"""
        # Убираем служебные слова
        stop_words = {"покажи", "найди", "диалоги", "звонки", "где", "когда", "как"}
        key_words = [w for w in query.lower().split() if w not in stop_words]
        
        return {
            "enhanced_query": " ".join(key_words),
            "concepts": key_words,
            "query_intent": "general",
            "search_focus": "general"
        }
    
    def semantic_search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Семантический поиск с использованием embeddings и LLM"""
        
        # 1. Улучшаем запрос с помощью LLM
        enhanced = self.enhance_query_with_llm(query)
        enhanced_query = enhanced.get("enhanced_query", query)
        concepts = enhanced.get("concepts", [])
        query_intent = enhanced.get("query_intent", "general")
        
        logger.info(f"🔍 Улучшенный запрос: '{query}' → '{enhanced_query}'")
        logger.info(f"🎯 Концепции: {concepts}")
        logger.info(f"💭 Намерение: {query_intent}")
        
        # 2. Генерируем embedding для улучшенного запроса
        if self.embedding_model:
            try:
                query_embedding = self.embedding_model.encode(enhanced_query, convert_to_numpy=True)
                logger.info(f"✅ Embedding создан, размер: {query_embedding.shape}")
                
                # 3. Гибридный поиск: семантика через embeddings + текстовый поиск
                # Используем query_string для семантического поиска
                # LLM уже расширил запрос с концепциями, теперь делаем умный поиск
                
                # Строим семантический запрос с использованием концепций от LLM
                semantic_query_parts = []
                if concepts:
                    semantic_query_parts.extend(concepts)
                semantic_query_parts.append(enhanced_query)
                
                search_body = {
                    "query": {
                        "bool": {
                            "should": [
                                # Точный поиск по типам
                                {"term": {"call_type": "Входящий звонок"}} if "входящ" in enhanced_query.lower() else None,
                                # Семантический поиск по тексту с концепциями
                                {
                                    "multi_match": {
                                        "query": " ".join(semantic_query_parts),
                                        "fields": ["text_full^3", "text_clean_full^2", "text_summary^1", "tags^2"],
                                        "type": "best_fields",
                                        "fuzziness": "AUTO"
                                    }
                                },
                                # Поиск по конкретным ключевым словам из расширенного запроса
                                {
                                    "match_phrase": {
                                        "text_full": {
                                            "query": enhanced_query,
                                            "boost": 2.0
                                        }
                                    }
                                }
                            ],
                            "minimum_should_match": "75%"
                        }
                    },
                    "size": limit
                }
                
                # Убираем None из списка
                search_body["query"]["bool"]["should"] = [q for q in search_body["query"]["bool"]["should"] if q is not None]
                
            except Exception as e:
                logger.error(f"❌ Ошибка создания embedding: {e}")
                # Fallback на обычный поиск
                search_body = self._build_fallback_search(enhanced_query, concepts)
        else:
            logger.warning("⚠️ Модель embeddings недоступна, используем fallback")
            search_body = self._build_fallback_search(enhanced_query, concepts)
        
        # 4. Выполняем поиск
        try:
            response = self.es.search(index=self.index_name, body=search_body)
            
            # 5. Обрабатываем и переранжируем результаты по семантике
            results = []
            candidates = []
            
            for hit in response['hits']['hits']:
                source = hit['_source']
                candidates.append({
                    "hit": hit,
                    "source": source
                })
            
            # Если есть embedding модель, переранжируем по семантическому сходству
            if self.embedding_model and query_embedding is not None:
                try:
                    # Генерируем embeddings для текстов кандидатов
                    candidate_texts = []
                    for cand in candidates:
                        text = f"{cand['source'].get('text_summary', '')} {cand['source'].get('text_full', '')[:500]}"
                        candidate_texts.append(text)
                    
                    # Генерируем embeddings
                    candidate_embeddings = self.embedding_model.encode(candidate_texts, convert_to_numpy=True, show_progress_bar=False)
                    
                    # Вычисляем косинусное расстояние
                    from numpy.linalg import norm
                    for i, (cand, cand_embedding) in enumerate(zip(candidates, candidate_embeddings)):
                        # Косинусное сходство
                        cosine_sim = query_embedding @ cand_embedding / (norm(query_embedding) * norm(cand_embedding) + 1e-8)
                        
                        # Объединяем BM25 score и семантический score
                        bm25_score = cand['hit']['_score']
                        semantic_score = float(cosine_sim * 10)  # Нормализуем к похожей шкале
                        combined_score = bm25_score + semantic_score
                        
                        cand['semantic_score'] = combined_score
                        cand['cosine_similarity'] = float(cosine_sim)
                
                except Exception as e:
                    logger.error(f"❌ Ошибка переранжирования: {e}")
                    for cand in candidates:
                        cand['semantic_score'] = cand['hit']['_score']
                        cand['cosine_similarity'] = 0
            else:
                for cand in candidates:
                    cand['semantic_score'] = cand['hit']['_score']
                    cand['cosine_similarity'] = 0
            
            # Сортируем по combined score
            candidates.sort(key=lambda x: x['semantic_score'], reverse=True)
            
            # Формируем финальные результаты
            for cand in candidates:
                hit = cand['hit']
                source = cand['source']
                
                result = {
                    "call_id": source['call_id'],
                    "call_type": source.get('call_type', ''),
                    "operator_name": source['operator_name'],
                    "qa_total_score": source['qa_total_score'],
                    "qa_critical_violation": source['qa_critical_violation'],
                    "tags": source['tags'],
                    "text_summary": source['text_summary'],
                    "semantic_score": cand['semantic_score'],
                    "cosine_similarity": cand.get('cosine_similarity', 0),
                    "relevance_reason": f"Семантика: {cand.get('cosine_similarity', 0):.3f} + BM25: {hit['_score']:.2f}"
                }
                results.append(result)
            
            return {
                "results": results,
                "total": response['hits']['total']['value'],
                "enhanced_query": enhanced_query,
                "concepts": concepts,
                "query_intent": query_intent,
                "semantic_features": {
                    "vector_search": self.embedding_model is not None,
                    "llm_enhancement": True,
                    "embedding_model": "multilingual-e5-base" if self.embedding_model else None
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска: {e}")
            return {
                "results": [],
                "total": 0,
                "error": str(e)
            }
    
    def _build_fallback_search(self, query: str, concepts: List[str]) -> Dict[str, Any]:
        """Fallback поиск без embeddings"""
        return {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["text_full^3", "text_clean_full^2", "text_summary^1"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "size": 10
        }

