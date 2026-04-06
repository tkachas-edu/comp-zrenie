# Умный фоторедактор — Smart Photo Filter

Веб-приложение для применения фильтров к изображениям: базовые операции работают прямо в браузере через **OpenCV.js**, а «умные» операции (обнаружение лиц, удаление фона, контуры) обрабатываются **Flask**-сервером на Python.

## Структура

```
comp-zrenie/
├── backend/
│   ├── app.py            # Flask API
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## Запуск

### 1. Бэкенд

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
# Сервер запустится на http://localhost:5000
```

> При первом запуске операция **«Удалить фон»** скачает модель (~170 МБ). Последующие запуски используют кэш.

### 2. Фронтенд

Фронтенд раздаётся самим Flask-сервером. После запуска `python app.py` откройте http://localhost:5000

## API

`POST /api/process` — `multipart/form-data`

| Поле        | Тип    | Описание                                      |
|-------------|--------|-----------------------------------------------|
| `image`     | file   | Изображение (JPEG, PNG, …)                    |
| `operation` | string | `detect_faces` / `remove_bg` / `find_edges`   |

Возвращает обработанное изображение (`image/jpeg` или `image/png`).

## Операции

| Операция       | Где         | Описание                                          |
|----------------|-------------|---------------------------------------------------|
| Оттенки серого | Браузер     | OpenCV.js `cvtColor`                              |
| Инверсия       | Браузер     | Побитовая инверсия RGB-каналов                    |
| Размытие       | Браузер     | OpenCV.js `GaussianBlur`                          |
| Найти лица     | Сервер      | Haar Cascade (`haarcascade_frontalface_default`)  |
| Удалить фон    | Сервер      | `rembg` (U²-Net), fallback — GrabCut             |
| Контуры        | Сервер      | Canny + наложение на оригинал                     |
