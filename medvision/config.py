"""
config.py — настройки приложения.

Здесь собраны все параметры, которые можно менять
без переписывания кода: пути, размеры, пороги.
"""

import os

# Абсолютный путь к папке проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    # === Flask ===
    SECRET_KEY = 'your-secret-key-change-in-production'
    
    # === База данных SQLite ===
    # База хранится в одном файле, переносится простым копированием
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, "medvision.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Отключаем лишние уведомления
    
    # === Пути для файлов ===
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    HEATMAP_FOLDER = os.path.join(BASE_DIR, 'static', 'heatmaps')
    REPORT_FOLDER = os.path.join(BASE_DIR, 'static', 'reports')
    
    # === Параметры модели ===
    MODEL_NAME = 'densenet121'           # Архитектура из torchvision
    INPUT_SIZE = 224                       # Размер входного изображения
    NUM_CLASSES = 2                    # Норма, Другая
    CONFIDENCE_THRESHOLD = 0.85          # Порог уверенности
    
    # === Предобработка ===
    # Среднее и стандартное отклонение ImageNet — стандарт для transfer learning
    IMAGENET_MEAN = [0.485, 0.456, 0.406]
    IMAGENET_STD = [0.229, 0.224, 0.225]
    
    # === Классы ===
    CLASS_NAMES = ['Норма', 'Патология']  # или ['NORMAL', 'PNEUMONIA']