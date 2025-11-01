import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import Dict, Any, List
import json

def display_dialogue_dashboard(dialogue_data: Dict[str, Any], query: str = ""):
    """Отображение полного дашборда диалога с подсветкой"""
    
    st.markdown("---")
    st.subheader(f"📊 Детальный дашборд диалога: {dialogue_data['call_id']}")
    
    # Заголовок с метриками
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        score_color = "green" if dialogue_data['qa_total_score'] >= 80 else "orange" if dialogue_data['qa_total_score'] >= 60 else "red"
        st.metric(
            "QA Балл", 
            f"{dialogue_data['qa_total_score']}/{dialogue_data['qa_max_total']}",
            delta=f"{dialogue_data['qa_total_score'] - dialogue_data['qa_max_total']/2:.0f}"
        )
    
    with col2:
        st.metric(
            "Критические нарушения", 
            "Да" if dialogue_data['qa_critical_violation'] else "Нет",
            delta="⚠️" if dialogue_data['qa_critical_violation'] else "✅"
        )
    
    with col3:
        coverage_percent = (dialogue_data['reglament_coverage'] / dialogue_data['reglament_required']) * 100
        st.metric(
            "Покрытие регламента", 
            f"{dialogue_data['reglament_coverage']}/{dialogue_data['reglament_required']}",
            delta=f"{coverage_percent:.0f}%"
        )
    
    with col4:
        st.metric(
            "Эмпатия", 
            dialogue_data['empathy_count'],
            delta="💚" if dialogue_data['empathy_count'] > 0 else "❌"
        )
    
    # Табы для разных секций
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Полный текст", "🎭 Сегменты", "📊 Аналитика", "🏷️ Теги", "📈 Графики"])
    
    with tab1:
        st.subheader("📝 Полный текст диалога")
        
        # Подсветка релевантных частей
        highlighted_text = dialogue_data.get('highlighted_text', '')
        if highlighted_text and query:
            st.markdown("**🔍 Релевантные фрагменты:**")
            st.markdown(highlighted_text, unsafe_allow_html=True)
            st.markdown("---")
        
        # Полный текст
        st.markdown("**📄 Полный текст:**")
        st.text_area("", dialogue_data['text_full'], height=200, disabled=True)
        
        # Очищенный текст
        if dialogue_data.get('text_clean_full'):
            st.markdown("**🧹 Очищенный текст (без персональных данных):**")
            st.text_area("", dialogue_data['text_clean_full'], height=150, disabled=True)
    
    with tab2:
        st.subheader("🎭 Сегменты диалога с эмоциями")
        
        if dialogue_data.get('dialogue_segments'):
            segments = dialogue_data['dialogue_segments']
            
            # Фильтр по роли
            roles = list(set([seg.get('role', 'unknown') for seg in segments]))
            selected_role = st.selectbox("Фильтр по роли:", ["Все"] + roles)
            
            # Отображение сегментов
            for i, segment in enumerate(segments):
                if selected_role != "Все" and segment.get('role') != selected_role:
                    continue
                
                emotion = segment.get('emotion', {}).get('dominant', 'neutral')
                confidence = segment.get('emotion', {}).get('confidence', 0)
                
                emotion_icons = {
                    "happiness": "😊", "anger": "😠", "fear": "😨", 
                    "sadness": "😢", "neutral": "😐", "enthusiasm": "🤩"
                }
                emotion_icon = emotion_icons.get(emotion, "😐")
                
                # Цветовая схема для эмоций
                emotion_colors = {
                    "happiness": "🟢", "anger": "🔴", "fear": "🟡", 
                    "sadness": "🔵", "neutral": "⚪", "enthusiasm": "🟣"
                }
                emotion_color = emotion_colors.get(emotion, "⚪")
                
                with st.expander(f"{emotion_color} {emotion_icon} **{segment.get('role', 'unknown')}** ({segment.get('start', '00:00')}-{segment.get('end', '00:00')}) - {emotion} ({confidence:.2f})"):
                    st.write(f"**Текст:** {segment.get('text', 'Нет текста')}")
                    
                    # Детали эмоции
                    if segment.get('emotion'):
                        emotion_data = segment['emotion']
                        st.write(f"**Эмоция:** {emotion_data.get('dominant', 'neutral')}")
                        st.write(f"**Уверенность:** {emotion_data.get('confidence', 0):.2f}")
        else:
            st.info("Сегменты диалога не найдены")
    
    with tab3:
        st.subheader("📊 Аналитика диалога")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🏷️ Классификация:**")
            st.write(f"• **Теги проблем:** {', '.join(dialogue_data.get('tags', []))}")
            st.write(f"• **Категории тем:** {', '.join(dialogue_data.get('topic_categories', []))}")
            st.write(f"• **Бренды:** {', '.join(dialogue_data.get('brands', []))}")
            st.write(f"• **Модели:** {', '.join(dialogue_data.get('models', []))}")
        
        with col2:
            st.markdown("**📈 Метрики:**")
            st.write(f"• **Запрещенные фразы:** {dialogue_data.get('no_go_count', 0)}")
            st.write(f"• **Эмпатия:** {dialogue_data.get('empathy_count', 0)}")
            st.write(f"• **Все регламенты пройдены:** {'Да' if dialogue_data.get('reglament_passed_all') else 'Нет'}")
            
            # Оценка качества
            score = dialogue_data['qa_total_score']
            if score >= 80:
                quality = "Отличное"
                color = "🟢"
            elif score >= 60:
                quality = "Хорошее"
                color = "🟡"
            else:
                quality = "Требует улучшения"
                color = "🔴"
            
            st.write(f"• **Общая оценка:** {color} {quality}")
    
    with tab4:
        st.subheader("🏷️ Теги и классификация")
        
        # Визуализация тегов
        tags = dialogue_data.get('tags', [])
        if tags:
            st.markdown("**🚨 Проблемы:**")
            for tag in tags:
                if "нарушение" in tag.lower() or "запрещенные" in tag.lower():
                    st.error(f"❌ {tag}")
                elif "эмпатия" in tag.lower() or "dead air" in tag.lower():
                    st.warning(f"⚠️ {tag}")
                else:
                    st.info(f"ℹ️ {tag}")
        
        # Категории
        categories = dialogue_data.get('topic_categories', [])
        if categories:
            st.markdown("**📂 Категории тем:**")
            for category in categories:
                st.write(f"• {category}")
        
        # Бренды и модели
        brands = dialogue_data.get('brands', [])
        models = dialogue_data.get('models', [])
        if brands or models:
            st.markdown("**🏭 Продукты:**")
            st.write(f"• **Бренды:** {', '.join(brands) if brands else 'Не указаны'}")
            st.write(f"• **Модели:** {', '.join(models) if models else 'Не указаны'}")
    
    with tab5:
        st.subheader("📈 Графики и визуализация")
        
        if dialogue_data.get('dialogue_segments'):
            segments = dialogue_data['dialogue_segments']
            
            # График эмоций по времени
            emotions_data = []
            for segment in segments:
                if segment.get('start') and segment.get('emotion'):
                    # Преобразуем время в секунды для графика
                    time_str = segment['start']
                    try:
                        time_parts = time_str.split(':')
                        seconds = int(time_parts[0]) * 60 + int(time_parts[1])
                        emotions_data.append({
                            'Время (сек)': seconds,
                            'Эмоция': segment['emotion'].get('dominant', 'neutral'),
                            'Роль': segment.get('role', 'unknown'),
                            'Уверенность': segment['emotion'].get('confidence', 0)
                        })
                    except:
                        continue
            
            if emotions_data:
                df_emotions = pd.DataFrame(emotions_data)
                
                # График эмоций по времени
                fig_emotions = px.scatter(
                    df_emotions, 
                    x='Время (сек)', 
                    y='Эмоция', 
                    color='Роль',
                    size='Уверенность',
                    title='Эмоции по времени диалога',
                    hover_data=['Уверенность']
                )
                st.plotly_chart(fig_emotions, use_container_width=True)
                
                # Распределение эмоций
                emotion_counts = df_emotions['Эмоция'].value_counts()
                fig_dist = px.pie(
                    values=emotion_counts.values, 
                    names=emotion_counts.index, 
                    title='Распределение эмоций'
                )
                st.plotly_chart(fig_dist, use_container_width=True)
                
                # График уверенности по ролям
                fig_confidence = px.box(
                    df_emotions, 
                    x='Роль', 
                    y='Уверенность',
                    title='Уверенность определения эмоций по ролям'
                )
                st.plotly_chart(fig_confidence, use_container_width=True)
            else:
                st.info("Недостаточно данных для построения графиков эмоций")
        
        # График метрик качества
        metrics_data = {
            'Метрика': ['QA Балл', 'Покрытие регламента', 'Эмпатия', 'Запрещенные фразы'],
            'Значение': [
                dialogue_data['qa_total_score'],
                dialogue_data['reglament_coverage'],
                dialogue_data['empathy_count'],
                dialogue_data['no_go_count']
            ],
            'Максимум': [
                dialogue_data['qa_max_total'],
                dialogue_data['reglament_required'],
                5,  # Предполагаемый максимум для эмпатии
                5   # Предполагаемый максимум для запрещенных фраз
            ]
        }
        
        df_metrics = pd.DataFrame(metrics_data)
        df_metrics['Процент'] = (df_metrics['Значение'] / df_metrics['Максимум'] * 100).round(1)
        
        fig_metrics = px.bar(
            df_metrics, 
            x='Метрика', 
            y='Процент',
            title='Метрики качества (в процентах от максимума)',
            color='Процент',
            color_continuous_scale='RdYlGn'
        )
        st.plotly_chart(fig_metrics, use_container_width=True)
    
    # Кнопка закрытия
    if st.button("❌ Закрыть дашборд"):
        st.rerun()

def create_analytics_charts(analytics_data: Dict[str, Any]):
    """Создание графиков для аналитики"""
    
    st.subheader("📊 Аналитические графики")
    
    # График распределения баллов
    if 'score_ranges' in analytics_data:
        score_ranges = analytics_data['score_ranges']
        if score_ranges:
            df_scores = pd.DataFrame([
                {"Диапазон": bucket['key'], "Количество": bucket['doc_count']}
                for bucket in score_ranges
            ])
            fig_scores = px.bar(df_scores, x="Диапазон", y="Количество", title="Распределение QA баллов")
            st.plotly_chart(fig_scores, use_container_width=True)
    
    # График топ проблем
    if 'top_problems' in analytics_data:
        problems = analytics_data['top_problems']
        if problems:
            df_problems = pd.DataFrame([
                {"Проблема": bucket['key'], "Количество": bucket['doc_count']}
                for bucket in problems[:5]
            ])
            fig_problems = px.pie(df_problems, values="Количество", names="Проблема", title="Топ проблем")
            st.plotly_chart(fig_problems, use_container_width=True)
    
    # График операторов
    if 'operators' in analytics_data:
        operators = analytics_data['operators']
        if operators:
            df_operators = pd.DataFrame([
                {
                    "Оператор": bucket['key'], 
                    "Средний балл": bucket['avg_score']['value'],
                    "Количество звонков": bucket['total_calls']['value']
                }
                for bucket in operators[:5]
            ])
            fig_operators = px.bar(df_operators, x="Оператор", y="Средний балл", title="Производительность операторов")
            st.plotly_chart(fig_operators, use_container_width=True)
    
    # График эмоций
    if 'emotions' in analytics_data:
        emotions = analytics_data['emotions']
        if emotions:
            df_emotions = pd.DataFrame([
                {"Эмоция": bucket['key'], "Количество": bucket['doc_count']}
                for bucket in emotions[:5]
            ])
            fig_emotions = px.bar(df_emotions, x="Эмоция", y="Количество", title="Распределение эмоций")
            st.plotly_chart(fig_emotions, use_container_width=True)

