"""
models.py — структура таблиц в базе данных.

SQLAlchemy ORM позволяет работать с таблицами как с Python-классами.
Не нужно писать SQL-запросы вручную.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """Таблица пользователей. Пока упрощённая — без паролей для демо."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь 1:N — один пользователь может загрузить много изображений
    images = db.relationship('Image', backref='user', lazy=True)


class Image(db.Model):
    """Метаданные загруженных изображений."""
    __tablename__ = 'images'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)      # Имя файла на диске
    original_name = db.Column(db.String(255))                  # Оригинальное имя
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    file_size = db.Column(db.Integer)                          # Размер в байтах
    
    # Связь 1:1 — одно изображение = один результат классификации
    prediction = db.relationship('Prediction', backref='image', uselist=False)


class Prediction(db.Model):
    """Результат классификации одного изображения."""
    __tablename__ = 'predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.Integer, db.ForeignKey('images.id'), unique=True)
    
    # Основной диагноз (класс с максимальной вероятностью)
    predicted_class = db.Column(db.String(50))
    confidence = db.Column(db.Float)                           # Вероятность основного класса
    processing_time = db.Column(db.Float)                    # Время инференса в секундах
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связь 1:N — один предикт содержит вероятности по всем классам
    details = db.relationship('Result', backref='prediction', lazy=True)
    
    # Путь к сгенерированному heatmap
    heatmap_path = db.Column(db.String(255))


class Result(db.Model):
    """Детализация: вероятность по каждому классу отдельно."""
    __tablename__ = 'results'
    
    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey('predictions.id'))
    class_name = db.Column(db.String(50))
    probability = db.Column(db.Float)


class ModelConfig(db.Model):
    """Настройки модели (можно менять через интерфейс)."""
    __tablename__ = 'model_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(50), default='densenet121')
    threshold = db.Column(db.Float, default=0.85)
    input_size = db.Column(db.Integer, default=224)