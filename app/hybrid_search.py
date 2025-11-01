"""
Гибридный поисковый движок с многоуровневым ранжированием
Комбинирует BM25, Semantic Search, Keyword Density и Context Boost
"""

import logging
import math
import re
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
import numpy as np
from elasticsearch import Elasticsearch
import requests
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Анализ и понимание запроса"""
    
    def __init__(self, llm_url: str):
        self.llm_url = llm_url
    
    def analyze(self, query: str) -> Dict[str, Any]:
        """Полный анализ запроса"""
        # Базовые компоненты
        keywords = self._extract_keywords(query)
        intent = self._detect_intent(query)
        entities = self._extract_entities(query)
        
        # LLM расширение
        llm_analysis = self._llm_expand(query)
        
        return {
            'original_query': query,
            'keywords': keywords,
            'intent': intent,
            'entities': entities,
            'expanded_query': llm_analysis.get('enhanced_query', query),
            'concepts': llm_analysis.get('concepts', []),
            'query_type': self._classify_query_type(query, intent)
        }
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Извлечение ключевых слов"""
        # Убираем стоп-слова
        stop_words = {'покажи', 'найди', 'где', 'когда', 'как', 'что', 'диалоги', 'звонки', 'разговоры'}
        words = query.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords
    
    def _detect_intent(self, query: str) -> str:
        """Определение намерения пользователя"""
        query_lower = query.lower()
        
        # Паттерны для определения intent
        if any(w in query_lower for w in ['входящ', 'вход']):
            return 'входящие_звонки'
        elif any(w in query_lower for w in ['недоволь', 'жалоб', 'проблем']):
            return 'недовольство_клиента'
        elif any(w in query_lower for w in ['оператор', 'менеджер']) and any(w in query_lower for w in ['груб', 'хам', 'невежлив']):
            return 'проблемы_с_оператором'
        elif any(w in query_lower for w in ['прода', 'куп', 'заказ']):
            return 'продажи'
        elif any(w in query_lower for w in ['эмпат', 'доволен', 'доволь']):
            return 'положительные_эмоции'
        else:
            return 'общий_поиск'
    
    def _extract_entities(self, query: str) -> Dict[str, List[str]]:
        """Извлечение сущностей из запроса"""
        entities = {
            'operators': [],
            'products': [],
            'emotions': [],
            'call_types': []
        }
        
        query_lower = query.lower()
        
        # Типы звонков
        if 'входящ' in query_lower:
            entities['call_types'].append('Входящий звонок')
        if 'исходящ' in query_lower:
            entities['call_types'].append('Исходящий звонок')
        
        # Эмоции
        emotion_keywords = {
            'недоволь': 'negative',
            'жалоб': 'negative',
            'груб': 'negative',
            'доволен': 'positive',
            'эмпат': 'positive'
        }
        
        for word, emotion in emotion_keywords.items():
            if word in query_lower:
                entities['emotions'].append(emotion)
        
        return entities
    
    def _classify_query_type(self, query: str, intent: str) -> str:
        """Классификация типа запроса"""
        if intent in ['входящие_звонки']:
            return 'structured'  # Структурированный запрос (фильтры)
        elif intent in ['недовольство_клиента', 'проблемы_с_оператором']:
            return 'semantic'  # Семантический (нужен контекст)
        else:
            return 'keyword'  # Ключевые слова
    
    def _llm_expand(self, query: str) -> Dict[str, Any]:
        """Расширение запроса через LLM"""
        try:
            prompt = f"""
Проанализируй запрос для поиска в диалогах колл-центра: "{query}"

Извлеки:
1. Ключевые концепции (не слова!)
2. Синонимы
3. Контекстные термины

Ответь JSON:
{{
    "enhanced_query": "расширенный запрос",
    "concepts": ["концепция1", "концепция2"]
}}
"""
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": "qwen/qwen3-coder-30b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.2
                },
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result['choices'][0]['message']['content'].strip()
                
                # Парсим JSON
                if '```json' in llm_response:
                    llm_response = llm_response.split('```json')[1].split('```')[0].strip()
                elif '```' in llm_response:
                    llm_response = llm_response.split('```')[1].split('```')[0].strip()
                
                return json.loads(llm_response)
        except Exception as e:
            logger.warning(f"LLM расширение недоступно: {e}")
        
        # Fallback
        return {
            "enhanced_query": query,
            "concepts": []
        }


class KeywordDensityScorer:
    """Подсчет плотности ключевых слов в документе"""
    
    def score(self, query_words: List[str], text: str, metadata: Dict[str, Any] = None) -> Dict[str, float]:
        """
        Подсчет плотности ключевых слов
        
        Возвращает:
        - density_score: общая плотность
        - tf_scores: TF для каждого слова
        - proximity_bonus: бонус за близость слов
        - position_bonus: бонус за позицию
        """
        if not text or not query_words:
            return {
                'density_score': 0.0,
                'tf_scores': {},
                'proximity_bonus': 1.0,
                'position_bonus': 1.0
            }
        
        # Токенизация
        text_lower = text.lower()
        text_words = re.findall(r'\w+', text_lower)
        total_words = len(text_words)
        
        if total_words == 0:
            return {
                'density_score': 0.0,
                'tf_scores': {},
                'proximity_bonus': 1.0,
                'position_bonus': 1.0
            }
        
        # TF для каждого слова
        tf_scores = {}
        word_positions = {}
        
        for query_word in query_words:
            word_lower = query_word.lower()
            count = text_words.count(word_lower)
            
            # TF (Term Frequency) с логарифмической нормализацией
            tf = count / total_words
            tf_log = 1 + math.log(1 + tf * total_words) if tf > 0 else 0
            
            tf_scores[query_word] = tf_log
            
            # Позиции слова в тексте
            positions = [i for i, w in enumerate(text_words) if w == word_lower]
            word_positions[query_word] = positions
        
        # Общая плотность
        density_score = sum(tf_scores.values()) / len(query_words) if query_words else 0.0
        
        # Proximity Bonus (близость слов запроса)
        proximity_bonus = self._calculate_proximity_bonus(query_words, word_positions)
        
        # Position Bonus (позиция в документе)
        position_bonus = self._calculate_position_bonus(query_words, word_positions, total_words)
        
        return {
            'density_score': density_score,
            'tf_scores': tf_scores,
            'proximity_bonus': proximity_bonus,
            'position_bonus': position_bonus
        }
    
    def _calculate_proximity_bonus(self, query_words: List[str], word_positions: Dict[str, List[int]]) -> float:
        """Бонус за близость слов запроса"""
        if len(query_words) < 2:
            return 1.0
        
        min_distance = float('inf')
        
        # Находим минимальное расстояние между любыми двумя словами запроса
        for i, word1 in enumerate(query_words):
            for word2 in query_words[i+1:]:
                if word1 in word_positions and word2 in word_positions:
                    for pos1 in word_positions[word1]:
                        for pos2 in word_positions[word2]:
                            distance = abs(pos1 - pos2)
                            min_distance = min(min_distance, distance)
        
        if min_distance == float('inf'):
            return 1.0
        
        # Бонус за близость
        if min_distance <= 3:
            return 3.0  # Слова очень близко
        elif min_distance <= 5:
            return 2.0  # Близко
        elif min_distance <= 10:
            return 1.5  # Средне
        else:
            return 1.0  # Далеко
    
    def _calculate_position_bonus(self, query_words: List[str], word_positions: Dict[str, List[int]], total_words: int) -> float:
        """Бонус за позицию слова в документе (начало важнее)"""
        if not word_positions or total_words == 0:
            return 1.0
        
        # Находим среднюю позицию всех слов запроса
        all_positions = []
        for word in query_words:
            if word in word_positions:
                all_positions.extend(word_positions[word])
        
        if not all_positions:
            return 1.0
        
        avg_position = sum(all_positions) / len(all_positions)
        relative_position = avg_position / total_words if total_words > 0 else 0.5
        
        # Бонус: начало документа важнее
        if relative_position < 0.1:
            return 2.5  # В начале документа
        elif relative_position < 0.3:
            return 2.0  # В первой трети
        elif relative_position < 0.5:
            return 1.5  # В первой половине
        else:
            return 1.0  # Во второй половине


class ContextBoostScorer:
    """Контекстное усиление на основе метаданных"""
    
    def calculate_boost(self, query_analysis: Dict[str, Any], document: Dict[str, Any]) -> float:
        """Вычисление контекстного усиления"""
        boost = 1.0
        intent = query_analysis.get('intent', '')
        entities = query_analysis.get('entities', {})
        
        # 1. Тип звонка
        call_types = entities.get('call_types', [])
        if call_types:
            doc_call_type = document.get('call_type', '')
            if doc_call_type in call_types:
                boost *= 5.0
        
        # 2. Недовольство клиента
        if 'недовольство' in intent.lower() or 'недоволь' in intent.lower():
            if document.get('problem_call_has', False):
                boost *= 4.0
            if document.get('qa_critical_violation', False):
                boost *= 3.0
            if document.get('no_go_count', 0) > 0:
                boost *= 2.0
        
        # 3. Проблемы с оператором
        if 'оператор' in intent.lower():
            operator_name = query_analysis.get('entities', {}).get('operators', [])
            if operator_name:
                doc_operator = document.get('operator_name', '')
                if any(op.lower() in doc_operator.lower() for op in operator_name):
                    boost *= 3.0
        
        # 4. Положительные эмоции
        if 'положительные_эмоции' in intent:
            if document.get('empathy_count', 0) > 0:
                boost *= 2.5
            if document.get('qa_total_score', 0) >= 80:
                boost *= 1.5
        
        # 5. Продажи
        if 'продажи' in intent:
            # Можно добавить логику для определения продаж
            pass
        
        return boost


class ExactMatchScorer:
    """Подсчет точных совпадений"""
    
    def score(self, query: str, text: str) -> float:
        """Подсчет бонуса за точное совпадение"""
        query_lower = query.lower().strip()
        text_lower = text.lower()
        
        # 1. Точное совпадение всей фразы
        if query_lower in text_lower:
            return 10.0
        
        # 2. Все слова запроса присутствуют
        query_words = set(query_lower.split())
        text_words = set(re.findall(r'\w+', text_lower))
        
        if query_words.issubset(text_words):
            return 5.0
        
        # 3. Большинство слов (>= 80%)
        match_ratio = len(query_words & text_words) / len(query_words) if query_words else 0
        if match_ratio >= 0.8:
            return 2.0
        elif match_ratio >= 0.6:
            return 1.0
        
        return 0.0


class HybridSearchEngine:
    """
    Гибридный поисковый движок с многоуровневым ранжированием
    """
    
    def __init__(self, elasticsearch_url: str, llm_url: str, embedding_model=None):
        self.es = Elasticsearch([elasticsearch_url])
        self.llm_url = llm_url
        self.embedding_model = embedding_model
        self.index_name = "call_dialogues"
        
        # Инициализация компонентов
        self.query_analyzer = QueryAnalyzer(llm_url)
        self.keyword_density_scorer = KeywordDensityScorer()
        self.context_boost_scorer = ContextBoostScorer()
        self.exact_match_scorer = ExactMatchScorer()
        
        # Веса для финального ранжирования
        self.weights = {
            'bm25': 0.30,
            'semantic': 0.25,
            'keyword_density': 0.25,
            'exact_match': 0.15,
            'context_boost': 0.08,
            'proximity_bonus': 0.05,
            'position_bonus': 0.02
        }
    
    def search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Основной метод поиска
        
        Процесс:
        1. Анализ запроса
        2. Многоуровневая выборка (BM25 + Semantic)
        3. Дедупликация
        4. Многофакторный подсчет
        5. Финальное ранжирование
        """
        logger.info(f"🔍 Гибридный поиск: '{query}'")
        
        # Stage 1: Query Understanding
        query_analysis = self.query_analyzer.analyze(query)
        logger.info(f"📊 Анализ: intent={query_analysis['intent']}, keywords={query_analysis['keywords']}")
        
        # Stage 2: Multi-Stage Retrieval
        candidates = self._multi_stage_retrieval(query, query_analysis)
        logger.info(f"📦 Найдено кандидатов: {len(candidates)}")
        
        # Stage 3: Multi-Factor Scoring
        scored_candidates = self._multi_factor_scoring(query, query_analysis, candidates)
        
        # Stage 4: Final Ranking
        ranked = sorted(scored_candidates, key=lambda x: x['final_score'], reverse=True)
        
        # Формируем результаты
        results = []
        for item in ranked[:limit]:
            # Включаем все данные документа
            source_data = item.get('_source_data', {})
            if not source_data:
                # Если нет _source_data, создаем из item
                source_data = {
                    'timestamp': '',
                    'operator_phone': '',
                    'customer_phone': '',
                    'topic_categories': [],
                    'brands': [],
                    'models': [],
                    'text_full': item.get('text_full', ''),
                    'text_clean_full': '',
                    'qa_max_total': 0,
                    'reglament_coverage': 0,
                    'reglament_required': 0,
                    'reglament_passed_all': False,
                    'empathy_count': item.get('empathy_count', 0),
                    'no_go_count': item.get('no_go_count', 0),
                    'dialogue_segments': [],
                    'emotion_meta': {}
                }
            
            results.append({
                "call_id": item['call_id'],
                "call_type": item.get('call_type', ''),
                "operator_name": item.get('operator_name', ''),
                "qa_total_score": item.get('qa_total_score', 0),
                "qa_critical_violation": item.get('qa_critical_violation', False),
                "tags": item.get('tags', []),
                "text_summary": item.get('text_summary', ''),
                "semantic_score": item['final_score'],
                "score_breakdown": item.get('score_breakdown', {}),
                "relevance_reason": self._generate_relevance_reason(item),
                "_source_data": source_data
            })
        
        return {
            "results": results,
            "total": len(ranked),
            "query": query,
            "query_analysis": query_analysis
        }
    
    def _multi_stage_retrieval(self, query: str, query_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Многоуровневая выборка кандидатов"""
        all_candidates = []
        candidate_ids = set()
        
        # Stage 2a: BM25 Search (500 кандидатов)
        bm25_candidates = self._bm25_search(query, query_analysis, limit=500)
        for cand in bm25_candidates:
            if cand['call_id'] not in candidate_ids:
                cand['source'] = 'bm25'
                all_candidates.append(cand)
                candidate_ids.add(cand['call_id'])
        
        # Stage 2b: Semantic Search (100 кандидатов)
        if self.embedding_model:
            semantic_candidates = self._semantic_search(query, query_analysis, limit=100)
            for cand in semantic_candidates:
                if cand['call_id'] not in candidate_ids:
                    cand['source'] = 'semantic'
                    all_candidates.append(cand)
                    candidate_ids.add(cand['call_id'])
                else:
                    # Обновляем существующий кандидат
                    for existing in all_candidates:
                        if existing['call_id'] == cand['call_id']:
                            existing['semantic_score'] = cand.get('semantic_score', 0)
                            existing['source'] = 'both'
                            break
        
        logger.info(f"📦 После объединения: {len(all_candidates)} уникальных кандидатов")
        return all_candidates
    
    def _bm25_search(self, query: str, query_analysis: Dict[str, Any], limit: int = 500) -> List[Dict[str, Any]]:
        """BM25 поиск через Elasticsearch"""
        expanded_query = query_analysis.get('expanded_query', query)
        concepts = query_analysis.get('concepts', [])
        
        # Строим запрос
        should_clauses = []
        
        # Основной поиск
        should_clauses.append({
            "multi_match": {
                "query": expanded_query,
                "fields": ["text_full^3", "text_clean_full^2", "text_summary^1", "tags^2"],
                "type": "best_fields",
                "fuzziness": "AUTO"
            }
        })
        
        # Поиск по концепциям
        if concepts:
            should_clauses.append({
                "multi_match": {
                    "query": " ".join(concepts),
                    "fields": ["text_full^2", "text_summary^1"],
                    "type": "best_fields"
                }
            })
        
        # Фильтры
        must_clauses = []
        entities = query_analysis.get('entities', {})
        
        if entities.get('call_types'):
            must_clauses.append({
                "terms": {"call_type": entities['call_types']}
            })
        
        search_body = {
            "query": {
                "bool": {
                    "should": should_clauses,
                    "must": must_clauses if must_clauses else None,
                    "minimum_should_match": 1
                }
            },
            "size": limit
        }
        
        try:
            response = self.es.search(index=self.index_name, body=search_body)
            candidates = []
            
            for hit in response['hits']['hits']:
                source = hit['_source']
                candidates.append({
                    'call_id': source['call_id'],
                    'call_type': source.get('call_type', ''),
                    'operator_name': source.get('operator_name', ''),
                    'qa_total_score': source.get('qa_total_score', 0),
                    'qa_critical_violation': source.get('qa_critical_violation', False),
                    'problem_call_has': source.get('problem_call_has', False),
                    'empathy_count': source.get('empathy_count', 0),
                    'no_go_count': source.get('no_go_count', 0),
                    'tags': source.get('tags', []),
                    'text_full': source.get('text_full', ''),
                    'text_summary': source.get('text_summary', ''),
                    'bm25_score': hit['_score'],
                    '_source_data': source
                })
            
            return candidates
        except Exception as e:
            logger.error(f"❌ Ошибка BM25 поиска: {e}")
            return []
    
    def _semantic_search(self, query: str, query_analysis: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        """Семантический поиск с embeddings"""
        if not self.embedding_model:
            return []
        
        try:
            expanded_query = query_analysis.get('expanded_query', query)
            query_embedding = self.embedding_model.encode(expanded_query, convert_to_numpy=True)
            
            # Простой текстовый поиск для получения кандидатов
            search_body = {
                "query": {
                    "multi_match": {
                        "query": expanded_query,
                        "fields": ["text_full", "text_summary"],
                        "type": "best_fields"
                    }
                },
                "size": limit
            }
            
            response = self.es.search(index=self.index_name, body=search_body)
            candidates = []
            
            for hit in response['hits']['hits']:
                source = hit['_source']
                text = f"{source.get('text_summary', '')} {source.get('text_full', '')[:500]}"
                
                # Генерируем embedding для документа
                doc_embedding = self.embedding_model.encode(text, convert_to_numpy=True)
                
                # Косинусное сходство
                cosine_sim = np.dot(query_embedding, doc_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding) + 1e-8
                )
                
                candidates.append({
                    'call_id': source['call_id'],
                    'call_type': source.get('call_type', ''),
                    'operator_name': source.get('operator_name', ''),
                    'qa_total_score': source.get('qa_total_score', 0),
                    'qa_critical_violation': source.get('qa_critical_violation', False),
                    'problem_call_has': source.get('problem_call_has', False),
                    'empathy_count': source.get('empathy_count', 0),
                    'no_go_count': source.get('no_go_count', 0),
                    'tags': source.get('tags', []),
                    'text_full': source.get('text_full', ''),
                    'text_summary': source.get('text_summary', ''),
                    'semantic_score': float(cosine_sim),
                    '_source_data': source
                })
            
            return candidates
        except Exception as e:
            logger.error(f"❌ Ошибка семантического поиска: {e}")
            return []
    
    def _multi_factor_scoring(self, query: str, query_analysis: Dict[str, Any], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Многофакторный подсчет очков"""
        scored = []
        
        # Нормализация BM25 scores
        bm25_scores = [c.get('bm25_score', 0) for c in candidates if 'bm25_score' in c]
        max_bm25 = max(bm25_scores) if bm25_scores else 1.0
        
        # Нормализация Semantic scores
        semantic_scores = [c.get('semantic_score', 0) for c in candidates if 'semantic_score' in c]
        max_semantic = max(semantic_scores) if semantic_scores else 1.0
        
        for candidate in candidates:
            scores = {}
            
            # 1. BM25 Score (0.30)
            bm25 = candidate.get('bm25_score', 0)
            scores['bm25'] = (bm25 / max_bm25) * 100 if max_bm25 > 0 else bm25 * 10  # Fallback если нет max
            
            # 2. Semantic Score (0.25)
            semantic = candidate.get('semantic_score', 0)
            if max_semantic > 0:
                scores['semantic'] = (semantic / max_semantic) * 100
            else:
                scores['semantic'] = semantic * 100  # Fallback
            
            # 3. Keyword Density (0.25)
            query_words = query_analysis.get('keywords', [])
            text = candidate.get('text_full', '') or candidate.get('text_summary', '')
            density_result = self.keyword_density_scorer.score(query_words, text)
            scores['keyword_density'] = density_result['density_score'] * 20  # Увеличиваем вес
            
            # 4. Exact Match (0.15)
            exact = self.exact_match_scorer.score(query, text)
            scores['exact_match'] = exact
            
            # 5. Context Boost (0.08)
            context_boost = self.context_boost_scorer.calculate_boost(query_analysis, candidate)
            scores['context_boost'] = (context_boost - 1.0) * 20  # Нормализация
            
            # 6. Proximity Bonus (из Keyword Density)
            scores['proximity_bonus'] = (density_result['proximity_bonus'] - 1.0) * 10
            
            # 7. Position Bonus (из Keyword Density)
            scores['position_bonus'] = (density_result['position_bonus'] - 1.0) * 10
            
            # Финальный скор
            final_score = (
                scores['bm25'] * self.weights['bm25'] +
                scores['semantic'] * self.weights['semantic'] +
                scores['keyword_density'] * self.weights['keyword_density'] +
                scores['exact_match'] * self.weights['exact_match'] +
                scores['context_boost'] * self.weights['context_boost'] +
                scores['proximity_bonus'] * self.weights['proximity_bonus'] +
                scores['position_bonus'] * self.weights['position_bonus']
            )
            
            candidate['final_score'] = final_score
            candidate['score_breakdown'] = scores
            scored.append(candidate)
        
        return scored
    
    def _generate_relevance_reason(self, item: Dict[str, Any]) -> str:
        """Генерация объяснения релевантности"""
        breakdown = item.get('score_breakdown', {})
        reasons = []
        
        if breakdown.get('exact_match', 0) > 5:
            reasons.append("точное совпадение")
        if breakdown.get('context_boost', 0) > 2:
            reasons.append("контекстное соответствие")
        if breakdown.get('keyword_density', 0) > 5:
            reasons.append("высокая плотность ключевых слов")
        if breakdown.get('semantic', 0) > 50:
            reasons.append("семантическое сходство")
        
        return ", ".join(reasons) if reasons else "релевантность по комбинации факторов"
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Обновление весов для настройки"""
        self.weights.update(new_weights)
        logger.info(f"✅ Веса обновлены: {self.weights}")

