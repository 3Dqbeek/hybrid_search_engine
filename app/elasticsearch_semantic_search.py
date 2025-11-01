import os
import json
import requests
from typing import List, Dict, Any, Optional
from elasticsearch import Elasticsearch
from datetime import datetime
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ElasticsearchSemanticSearch:
    """Семантический поиск на основе Elasticsearch без ML моделей"""
    
    def __init__(self, elasticsearch_url: str, llm_url: str):
        self.es = Elasticsearch([elasticsearch_url])
        self.llm_url = llm_url
        self.index_name = "call_dialogues"
        
        # Расширенный словарь синонимов и семантических связей
        self.semantic_expansions = {
            # Эмоции и состояния
            "грубый": ["невежливый", "хамский", "неучтивый", "резкий", "жесткий", "агрессивный"],
            "невежливый": ["грубый", "хамский", "неучтивый", "неуважительный", "дерзкий"],
            "расстроен": ["огорчен", "печален", "грустен", "недоволен", "разочарован"],
            "злой": ["агрессивный", "раздраженный", "недовольный", "возмущенный", "яростный"],
            "довольный": ["удовлетворенный", "счастливый", "радостный", "приятно удивленный"],
            
            # Проблемы и неисправности
            "проблема": ["неисправность", "поломка", "сбой", "ошибка", "недоработка"],
            "сломался": ["неисправен", "не работает", "поломка", "сломан", "вышел из строя"],
            "не работает": ["сломался", "неисправен", "не функционирует", "не отвечает"],
            
            # Качество работы
            "качественно": ["профессионально", "хорошо", "отлично", "добросовестно", "тщательно"],
            "профессионально": ["качественно", "компетентно", "умело", "мастерски"],
            "хорошо": ["отлично", "качественно", "добросовестно", "успешно"],
            
            # Нарушения и проблемы
            "нарушение": ["отклонение", "несоответствие", "ошибка", "проблема", "сбой"],
            "скрипт": ["сценарий", "алгоритм", "процедура", "инструкция"],
            "приветствие": ["привет", "здравствуйте", "добро пожаловать", "добрый день"],
            "эмпатия": ["понимание", "сочувствие", "поддержка", "внимание к клиенту"],
            
            # Технические термины
            "аппарат": ["устройство", "прибор", "машина", "оборудование"],
            "мотор": ["двигатель", "привод", "механизм"],
            "запчасти": ["детали", "компоненты", "элементы"],
            
            # Действия оператора
            "помощь": ["поддержка", "консультация", "содействие", "помощь"],
            "консультация": ["совет", "рекомендация", "информация", "помощь"],
            "решение": ["ответ", "выход", "способ", "метод"],
        }
        
        # Контекстные правила для семантического поиска
        self.context_rules = {
            "проблемы_оператора": {
                "keywords": ["грубый", "невежливый", "хамский", "проблема", "нарушение", "ошибка"],
                "boost_fields": ["qa_total_score", "qa_critical_violation"],
                "boost_value": -1,  # Низкие баллы = проблемы
                "tags": ["Нарушение скрипта", "Запрещенные фразы", "Dead air"]
            },
            "качество_работы": {
                "keywords": ["качественно", "профессионально", "хорошо", "отлично", "успешно"],
                "boost_fields": ["qa_total_score"],
                "boost_value": 1,  # Высокие баллы = качество
                "tags": ["Допродажа", "Эмпатия"]
            },
            "эмоции_клиента": {
                "keywords": ["расстроен", "злой", "довольный", "счастливый", "недовольный"],
                "boost_fields": ["empathy_count"],
                "boost_value": -1,  # Низкая эмпатия = проблемы
                "tags": ["Эмпатия", "Dead air"]
            }
        }
    
    def expand_query_semantically(self, query: str) -> str:
        """Семантическое расширение запроса"""
        expanded_terms = []
        query_lower = query.lower()
        
        # Расширяем каждое слово
        for word in query_lower.split():
            if word in self.semantic_expansions:
                expanded_terms.extend(self.semantic_expansions[word])
            else:
                expanded_terms.append(word)
        
        # Добавляем контекстные термины
        for context, rules in self.context_rules.items():
            if any(keyword in query_lower for keyword in rules["keywords"]):
                expanded_terms.extend(rules["tags"])
        
        # Убираем дубликаты и формируем расширенный запрос
        unique_terms = list(set(expanded_terms))
        expanded_query = f"{query} {' '.join(unique_terms)}"
        
        logger.info(f"Запрос расширен: '{query}' -> '{expanded_query}'")
        return expanded_query
    
    def expand_query_with_llm(self, query: str) -> str:
        """Расширение запроса с помощью LLM или локального расширения"""
        # Сначала пробуем LLM
        try:
            # Улучшенный промпт для семантического расширения
            prompt = f"""
Запрос для поиска в базе диалогов колл-центра: "{query}"

Распиши этот запрос конкретными ключевыми словами для поиска по данным:
- Если просят "покажи диалоги" - ищи по полям text_full, text_summary
- Если просят "входящие" - ищи по call_type
- Если просят конкретное содержимое - расширь синонимами

Только ключевые слова для поиска, через пробел, без пояснений.
"""
            
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": "qwen/qwen3-coder-30b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 100,
                    "temperature": 0.1
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                expanded_query = result['choices'][0]['message']['content'].strip()
                logger.info(f"✅ Запрос расширен LLM: {expanded_query}")
                return expanded_query
            else:
                raise Exception(f"LLM status: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"⚠️ LLM недоступен: {e}, используем умное расширение")
            # Улучшенное локальное расширение с пониманием намерений
            return self._smart_expand_query(query)
    
    def _smart_expand_query(self, query: str) -> str:
        """Умное расширение запроса с пониманием намерений пользователя"""
        query_lower = query.lower()
        
        # Определяем намерение
        # Если просят "покажи диалоги" - игнорируем слово "диалоги", фокусируемся на критериях
        if "покажи" in query_lower or "найди" in query_lower:
            # Убираем служебные слова и фокусируемся на ключевых словах
            key_words = []
            for word in query_lower.split():
                if word not in ["покажи", "найди", "диалоги", "звонки", "разговоры", "где", "когда"]:
                    key_words.append(word)
                    # Добавляем синонимы
                    if word in self.semantic_expansions:
                        key_words.extend(self.semantic_expansions[word][:2])  # Первые 2 синонима
            
            expanded_query = " ".join(key_words)
            logger.info(f"🤖 Умное расширение: '{query}' -> '{expanded_query}'")
            return expanded_query
        
        # Для обычных запросов - просто расширяем синонимами
        return self.expand_query_semantically(query)
    
    def semantic_search(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Семантический поиск на основе Elasticsearch"""
        
        # 1. Расширяем запрос семантически
        expanded_query = self.expand_query_with_llm(query)
        
        # 2. Определяем контекст запроса
        context_type = self._detect_query_context(query)
        context_rules = self.context_rules.get(context_type, {})
        
        # 3. Строим интеллектуальный семантический запрос
        # Определяем, есть ли специальные фильтры
        filters = []
        query_lower = query.lower()
        
        # Фильтр по типу звонка
        if "входящ" in query_lower or "вход" in query_lower:
            filters.append({"term": {"call_type": "Входящий звонок"}})
        elif "исходящ" in query_lower or "исход" in query_lower:
            filters.append({"term": {"call_type": "Исходящий звонок"}})
        
        # Фильтр по оператору
        if "оператор" in query_lower:
            # Извлекаем имя оператора из запроса
            operator_filter = {"multi_match": {"query": expanded_query, "fields": ["operator_name"], "type": "phrase"}}
            filters.append(operator_filter)
        
        search_body = {
            "query": {
                "bool": {
                    "should": [
                        # Основной поиск по расширенному запросу
                        {
                            "multi_match": {
                                "query": expanded_query,
                                "fields": [
                                    "text_full^3",
                                    "text_clean_full^2", 
                                    "text_summary^1"
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        },
                        # Поиск по отдельным словам
                        {
                            "multi_match": {
                                "query": query,  # Оригинальный запрос
                                "fields": [
                                    "text_full^2",
                                    "text_clean_full^1.5", 
                                    "text_summary^1"
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        }
                    ],
                    "must": filters if filters else None,
                    "minimum_should_match": 1
                }
            },
            "sort": [
                {"_score": {"order": "desc"}}
            ],
            "highlight": {
                "fields": {
                    "text_full": {
                        "fragment_size": 200,
                        "number_of_fragments": 3,
                        "pre_tags": ["<mark class='semantic-match'>"],
                        "post_tags": ["</mark>"]
                    },
                    "text_clean_full": {
                        "fragment_size": 200,
                        "number_of_fragments": 2,
                        "pre_tags": ["<mark class='semantic-match'>"],
                        "post_tags": ["</mark>"]
                    }
                }
            },
            "size": limit
        }
        
        # 5. Выполняем поиск
        response = self.es.search(index=self.index_name, body=search_body)
        
        # 6. Обрабатываем результаты
        results = []
        for hit in response['hits']['hits']:
            source = hit['_source']
            
            # Создаем релевантный фрагмент с подсветкой
            highlighted_text = ""
            if 'highlight' in hit:
                highlights = []
                for field in ['text_full', 'dialogue_segments.text']:
                    if field in hit['highlight']:
                        highlights.extend(hit['highlight'][field])
                highlighted_text = " ".join(highlights) if highlights else source.get('text_summary', '')
            
            result = {
                "call_id": source['call_id'],
                "call_type": source.get('call_type', ''),
                "operator_name": source['operator_name'],
                "qa_total_score": source['qa_total_score'],
                "qa_critical_violation": source['qa_critical_violation'],
                "tags": source['tags'],
                "text_summary": source['text_summary'],
                "highlighted_text": highlighted_text,
                "semantic_score": hit['_score'],
                "relevance_reason": self._explain_relevance(query, source, hit['_score'])
            }
            results.append(result)
        
        return {
            "results": results,
            "total": response['hits']['total']['value'],
            "expanded_query": expanded_query,
            "semantic_features": {
                "query_expansion": True,
                "vector_search": False,  # Без ML моделей
                "llm_used": expanded_query != query,
                "context_type": context_type
            }
        }
    
    def _detect_query_context(self, query: str) -> str:
        """Определение контекста запроса"""
        query_lower = query.lower()
        
        for context, rules in self.context_rules.items():
            if any(keyword in query_lower for keyword in rules["keywords"]):
                return context
        
        return "general"
    
    def _explain_relevance(self, query: str, source: Dict, score: float) -> str:
        """Объяснение релевантности результата"""
        reasons = []
        
        if source['qa_total_score'] < 50:
            reasons.append("низкий QA балл")
        if source['qa_critical_violation']:
            reasons.append("критическое нарушение")
        if any(tag in source['tags'] for tag in ["Нарушение скрипта", "Запрещенные фразы"]):
            reasons.append("нарушения в работе")
        if source.get('empathy_count', 0) == 0:
            reasons.append("отсутствие эмпатии")
        
        return f"Релевантен ({score:.2f}): {', '.join(reasons)}" if reasons else f"Релевантен ({score:.2f})"


class ElasticsearchSemanticChat:
    """Семантический чат на основе Elasticsearch без ML моделей"""
    
    def __init__(self, es_url: str, llm_url: str, semantic_search: ElasticsearchSemanticSearch):
        self.es = Elasticsearch([es_url])
        self.llm_url = llm_url
        self.semantic_search = semantic_search
    
    async def process_semantic_query(self, query: str) -> Dict[str, Any]:
        """Обработка семантического запроса с использованием LLM"""
        
        # 1. Выполняем семантический поиск
        search_results = self.semantic_search.semantic_search(query, limit=5)
        
        # 2. Подготавливаем контекст для LLM
        context = self._prepare_context(search_results['results'])
        
        # 3. Формируем промпт для LLM
        prompt = f"""
Ты эксперт по анализу диалогов колл-центра. Проанализируй найденные диалоги и ответь на вопрос пользователя.

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {query}

НАЙДЕННЫЕ ДИАЛОГИ:
{context}

ИНСТРУКЦИИ:
1. Проанализируй найденные диалоги
2. Ответь на вопрос пользователя на основе данных
3. Укажи конкретные примеры из диалогов
4. Если нужно, предложи рекомендации
5. Используй только информацию из предоставленных диалогов

ОТВЕТ:
"""
        
        # 4. Отправляем запрос к LLM
        try:
            response = requests.post(
                f"{self.llm_url}/v1/chat/completions",
                json={
                    "model": "qwen/qwen3-coder-30b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.3
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                llm_response = result['choices'][0]['message']['content'].strip()
                
                return {
                    "type": "semantic_llm",
                    "query": query,
                    "expanded_query": search_results['expanded_query'],
                    "llm_response": llm_response,
                    "sources": search_results['results'],
                    "semantic_features": search_results['semantic_features'],
                    "formatted_response": self._format_llm_response(llm_response, search_results['results'])
                }
            else:
                raise Exception(f"LLM error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Ошибка LLM: {e}")
            # Fallback к локальному анализу
            return self._fallback_analysis(query, search_results)
    
    def _prepare_context(self, results: List[Dict]) -> str:
        """Подготовка контекста для LLM"""
        context = ""
        
        for i, result in enumerate(results, 1):
            context += f"\n--- ДИАЛОГ {i} ---\n"
            context += f"ID: {result['call_id']}\n"
            context += f"Оператор: {result['operator_name']}\n"
            context += f"QA балл: {result['qa_total_score']}\n"
            context += f"Проблемы: {', '.join(result['tags'])}\n"
            context += f"Краткое содержание: {result['text_summary']}\n"
            
            if result['highlighted_text']:
                context += f"Релевантные фрагменты: {result['highlighted_text']}\n"
            
            context += f"Причина релевантности: {result['relevance_reason']}\n"
        
        return context
    
    def _format_llm_response(self, llm_response: str, sources: List[Dict]) -> str:
        """Форматирование ответа LLM"""
        formatted = f"🤖 **СЕМАНТИЧЕСКИЙ АНАЛИЗ:**\n\n{llm_response}\n\n"
        
        if sources:
            formatted += "📚 **ИСТОЧНИКИ:**\n"
            for i, source in enumerate(sources[:3], 1):
                formatted += f"{i}. **{source['call_id']}** - {source['operator_name']} "
                formatted += f"(QA: {source['qa_total_score']}, Релевантность: {source['semantic_score']:.2f})\n"
                formatted += f"   Проблемы: {', '.join(source['tags'])}\n"
        
        return formatted
    
    def _fallback_analysis(self, query: str, search_results: Dict) -> Dict[str, Any]:
        """Fallback анализ без LLM"""
        results = search_results['results']
        
        if not results:
            return {
                "type": "no_results",
                "formatted_response": f"По запросу '{query}' ничего не найдено."
            }
        
        # Простой анализ результатов
        analysis = f"🔍 **НАЙДЕНО {len(results)} РЕЛЕВАНТНЫХ ДИАЛОГОВ:**\n\n"
        
        for i, result in enumerate(results[:3], 1):
            analysis += f"**{i}. {result['call_id']}** - {result['operator_name']}\n"
            analysis += f"• QA балл: {result['qa_total_score']}\n"
            analysis += f"• Проблемы: {', '.join(result['tags'])}\n"
            analysis += f"• Релевантность: {result['relevance_reason']}\n"
            
            if result['highlighted_text']:
                analysis += f"• Релевантный фрагмент: {result['highlighted_text'][:200]}...\n"
            
            analysis += "\n"
        
        return {
            "type": "fallback_analysis",
            "formatted_response": analysis,
            "sources": results,
            "expanded_query": search_results['expanded_query']
        }
