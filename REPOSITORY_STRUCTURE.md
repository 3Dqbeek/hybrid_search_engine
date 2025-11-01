# 📁 Структура репозитория

```
hybrid_search_engine/
│
├── 📄 README.md                    # Главная документация
├── 📄 INSTALLATION.md              # Установка и настройка
├── 📄 INTEGRATION.md               # Руководство по интеграции
├── 📄 QUICK_START.md               # Быстрый старт
├── 📄 SYSTEM_OVERVIEW.md          # Обзор системы
├── 📄 CHANGELOG.md                 # История изменений
├── 📄 REPOSITORY_STRUCTURE.md      # Этот файл
│
├── 📄 docker-compose.yml           # Docker Compose конфигурация
├── 📄 Dockerfile                   # Docker образ
├── 📄 requirements.txt             # Python зависимости
├── 📄 .gitignore                  # Git ignore правила
│
├── 📂 app/                         # Backend модули
│   ├── __init__.py
│   ├── hybrid_search.py            # Основной гибридный движок
│   ├── quality_semantic_search.py  # Семантический поиск
│   ├── elasticsearch_semantic_search.py
│   └── api.py                     # REST API (опционально)
│
├── 📂 ui/                          # Frontend модули
│   ├── __init__.py
│   ├── simple_search_ui.py         # Упрощенный UI
│   └── dialogue_dashboard.py       # Дашборд диалога
│
├── 📂 docs/                        # Документация
│   ├── HYBRID_SEARCH_DOCUMENTATION.md  # Полное описание
│   └── HYBRID_SEARCH_DESIGN.md         # Архитектурный дизайн
│
└── 📂 data/                        # Данные (опционально)
    └── init_realistic.sql          # Пример SQL схемы
```

## Описание файлов

### Основные файлы

- **README.md** - Начало здесь! Обзор проекта, возможности, примеры
- **INSTALLATION.md** - Подробное руководство по установке
- **INTEGRATION.md** - Как интегрировать в свою систему
- **QUICK_START.md** - Быстрый старт за 5 минут

### Код

- **app/hybrid_search.py** - Главный класс `HybridSearchEngine`
- **app/api.py** - REST API обертка (опционально)
- **ui/simple_search_ui.py** - Streamlit интерфейс

### Документация

- **docs/HYBRID_SEARCH_DOCUMENTATION.md** - Полное техническое описание (20KB)
- **docs/HYBRID_SEARCH_DESIGN.md** - Архитектурный дизайн (6.8KB)

### Конфигурация

- **docker-compose.yml** - Docker Compose для запуска всех сервисов
- **requirements.txt** - Python зависимости
- **.gitignore** - Игнорируемые файлы Git
