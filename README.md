# Платформа для отслеживания и симуляции торговли валютами


## 📂 Структура проекта
```
finalproject_<фамилия>_<группа>/
│  
├── data/
│    ├── users.json             # список пользователей
│    ├── portfolios.json        # портфели и кошельки
│    └── rates.json             # курсы валют
├── valutatrade_hub/
│    ├── __init__.py
│    ├── core/
│    │    ├── __init__.py
│    │    ├── models.py         # реализация классов  
│    │    ├── utils.py          # вспомогательные функции
│    │    └── usecases.py       # бизнес-логика 
│    └── cli/
│         ├─ __init__.py
│         └─ interface.py       # команды
│
├── main.py
├── Makefile
├── poetry.lock
├── pyproject.toml
├── README.md
└── .gitignore                 # исключить dist/, __pycache__/ и т.п.
```
---

## Статус проекта

* 
---

## Автор

Алёна Вылегжанина, М25-555