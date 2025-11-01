import streamlit as st
import requests
import json
import os
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any, Optional
from datetime import datetime

# Импорт компонентов дашборда
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from ui.dialogue_dashboard import display_dialogue_dashboard, create_analytics_charts
except ImportError:
    # Fallback для прямого импорта
    from dialogue_dashboard import display_dialogue_dashboard, create_analytics_charts

st.set_page_config(
    page_title="Поиск диалогов",
    page_icon="🔍",
    layout="wide"
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")

def make_api_request(endpoint, method="GET", data=None, timeout=30):
    try:
        url = f"{API_BASE_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Ошибка API: {e}")
        return None

def hybrid_search(query, limit=10):
    """Гибридный поиск - максимально эффективная система"""
    search_request = {
        "query": query,
        "limit": limit
    }
    return make_api_request("/hybrid-search", method="POST", data=search_request)

# Инициализация session_state
if "show_dashboard" not in st.session_state:
    st.session_state.show_dashboard = {}

# Заголовок
st.title("🔍 Поиск диалогов колл-центра")
st.markdown("**Интеллектуальный поиск с использованием гибридного алгоритма**")

# === ПОИСКОВАЯ СТРОКА ===
col_search, col_button = st.columns([4, 1])

with col_search:
    search_query = st.text_input(
        "Введите запрос:",
        placeholder="Например: покажи входящие диалоги, недовольный клиент, проблемы с оператором...",
        key="search_input",
        label_visibility="collapsed"
    )

with col_button:
    st.write("")  # Отступ
    search_button = st.button("🔍 Поиск", type="primary", use_container_width=True)

# === ВЫПОЛНЕНИЕ ПОИСКА ===
if search_button and search_query:
    with st.spinner("Поиск..."):
        results = hybrid_search(search_query, limit=10)
    
    if results and results.get("results"):
        st.subheader(f"Найдено: {results.get('total', 0)} результатов")
        
        # Отображение результатов
        for i, res in enumerate(results["results"]):
            # Получаем релевантный фрагмент
            highlighted_text = res.get('text_summary', '')
            if not highlighted_text:
                highlighted_text = res.get('text_summary', 'Нет краткого содержания')
            
            # Компактная карточка
            with st.expander(f"📞 {res['call_id']} - {res['operator_name']} (Релевантность: {res.get('relevance_score', 0):.1f})"):
                # Основная информация
                col_info1, col_info2 = st.columns(2)
                
                with col_info1:
                    st.write(f"**Оператор:** {res['operator_name']}")
                    st.write(f"**Тип звонка:** {res.get('call_type', 'Не указан')}")
                    st.write(f"**QA Балл:** {res.get('qa_total_score', 0)}/{res.get('qa_max_total', 0)}")
                    st.write(f"**Критическое нарушение:** {'Да' if res.get('qa_critical_violation', False) else 'Нет'}")
                
                with col_info2:
                    st.write(f"**Теги:** {', '.join(res.get('tags', [])) if res.get('tags') else 'Нет'}")
                    st.write(f"**Покрытие регламента:** {res.get('reglament_coverage', 0)}/{res.get('reglament_required', 0)}")
                    st.write(f"**Эмпатия:** {res.get('empathy_count', 0)}")
                    st.write(f"**No-Go фразы:** {res.get('no_go_count', 0)}")
                
                # Релевантный фрагмент
                st.markdown("**🔍 Краткое содержание:**")
                if highlighted_text:
                    st.markdown(highlighted_text)
                else:
                    st.write("Нет краткого содержания")
                
                # Кнопка детального дашборда
                if st.button(f"📊 Детальный дашборд", key=f"dashboard_{i}"):
                    st.session_state.show_dashboard[i] = True
            
            # Детальный дашборд
            if st.session_state.show_dashboard.get(i, False):
                display_dialogue_dashboard(res, search_query)
                if st.button(f"❌ Закрыть дашборд", key=f"close_{i}"):
                    st.session_state.show_dashboard[i] = False
    
    elif results and results.get("total", 0) == 0:
        st.info("По вашему запросу ничего не найдено. Попробуйте изменить формулировку.")
    
    else:
        st.warning("Не удалось выполнить поиск. Проверьте подключение к API.")

elif search_button and not search_query:
    st.warning("Введите запрос для поиска")

# === ПОДСКАЗКИ ===
if not search_query or (search_button and not results):
    st.markdown("---")
    st.markdown("**💡 Примеры запросов:**")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("• Покажи входящие диалоги")
        st.markdown("• Недовольный клиент жалуется")
        st.markdown("• Проблемы с оператором")
        st.markdown("• Нарушение скрипта приветствия")
    
    with col2:
        st.markdown("• Диалоги про посудомоечные машины")
        st.markdown("• Где клиент ничего не купил")
        st.markdown("• Примеры качественной работы")
        st.markdown("• Оператор проявил эмпатию")

