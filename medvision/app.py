"""
app.py — точка входа. Flask-приложение с REST API.

Эндпоинты:
- GET  /          — главная страница (SPA)
- POST /api/upload — загрузка изображения
- POST /api/analyze — классификация
- GET  /api/history — история анализов
- GET  /api/result/<id> — конкретный результат
"""

import os
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import json

from config import Config
from models import db, User, Image, Prediction, Result, ModelConfig
from ml.preprocess import preprocess_image
from ml.classifier import get_classifier
from ml.gradcam import save_gradcam

# === Инициализация приложения ===
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config.from_object(Config)

# Инициализация базы данных
db.init_app(app)

# Создаём папки, если их нет
for folder in [Config.UPLOAD_FOLDER, Config.HEATMAP_FOLDER, Config.REPORT_FOLDER]:
    os.makedirs(folder, exist_ok=True)


# === Создание таблиц при первом запуске ===
with app.app_context():
    db.create_all()  # Создаёт все таблицы по models.py
    
    # Создаём тестового пользователя, если нет
    if not User.query.first():
        demo_user = User(username='demo', email='demo@medvision.ru')
        db.session.add(demo_user)
        db.session.commit()
        print("Создан демо-пользователь (id=1)")


# === МАРШРУТЫ ===
import logging
import traceback
logging.basicConfig(level=logging.DEBUG)

@app.route('/api/routes', methods=['GET'])
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'path': str(rule)
        })
    return jsonify({'routes': routes})
@app.errorhandler(500)

def handle_500(error):
    print("\n" + "="*70)
    print("ОШИБКА 500:")
    traceback.print_exc()
    print("="*70 + "\n")
    return jsonify({'success': False, 'message': 'Внутренняя ошибка сервера'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    print("\n" + "="*70)
    print("ОШИБКА:")
    traceback.print_exc()
    print("="*70 + "\n")
    return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/')
def index():
    """Главная страница — отдаём SPA."""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    """
    Загрузка изображения на сервер.
    
    Ожидает: multipart/form-data с полем 'image'
    Возвращает: JSON {success, image_id, filename, message}
    """
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'Нет файла'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Файл не выбран'}), 400
    
    # Проверка расширения
    allowed = {'png', 'jpg', 'jpeg', 'dcm', 'dicom'}
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if ext not in allowed:
        return jsonify({'success': False, 'message': f'Неподдерживаемый формат: {ext}'}), 400
    
    # Генерируем уникальное имя, чтобы не перезаписать существующие
    unique_name = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    save_path = os.path.join(Config.UPLOAD_FOLDER, unique_name)
    file.save(save_path)
    
    # Сохраняем в базу (привязываем к демо-пользователю)
    user = User.query.first()  # Демо-пользователь
    img_record = Image(
        user_id=user.id,
        filename=unique_name,
        original_name=file.filename,
        file_size=os.path.getsize(save_path)
    )
    db.session.add(img_record)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'image_id': img_record.id,
        'filename': unique_name,
        'message': 'Файл загружен'
    })


@app.route('/api/analyze/<int:image_id>', methods=['POST'])
def analyze(image_id):
    """
    Полная цепочка: загрузка из БД → предобработка → инференс → Grad-CAM → сохранение результата.
    """
    img_record = Image.query.get_or_404(image_id)
    image_path = os.path.join(Config.UPLOAD_FOLDER, img_record.filename)
    
    if not os.path.exists(image_path):
        return jsonify({'success': False, 'message': 'Файл не найден'}), 404
    
    try:
        # 1. Предобработка
        tensor = preprocess_image(image_path)
        
        # 2. Классификация
        classifier = get_classifier()
        result = classifier.predict(tensor)
        
        # 3. Grad-CAM
        heatmap_name = f"hm_{img_record.id}_{uuid.uuid4().hex[:8]}.jpg"
        heatmap_path = os.path.join(Config.HEATMAP_FOLDER, heatmap_name)
        save_gradcam(tensor, heatmap_path, target_class=result['predicted_idx'])
        
        # 4. Сохранение в БД
        prediction = Prediction(
            image_id=img_record.id,
            predicted_class=result['predicted_class'],
            confidence=result['confidence'],
            processing_time=result['processing_time'],
            heatmap_path=heatmap_name
        )
        db.session.add(prediction)
        db.session.flush()
        
        # Вероятности по классам
        for class_name, prob in result['probabilities'].items():
            detail = Result(
                prediction_id=prediction.id,
                class_name=class_name,
                probability=prob
            )
            db.session.add(detail)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'prediction_id': prediction.id,
            'predicted_class': result['predicted_class'],
            'confidence': round(result['confidence'], 4),
            'probabilities': result['probabilities'],
            'processing_time': round(result['processing_time'], 3),
            'heatmap_url': f'/static/heatmaps/{heatmap_name}',
            'original_url': f'/static/uploads/{img_record.filename}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/history', methods=['GET'])
def history():
    """
    Получение истории анализов.
    
    Параметры query: ?limit=20&offset=0
    Возвращает: список анализов с пагинацией
    """
    limit = request.args.get('limit', 20, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    # JOIN таблиц Image и Prediction
    query = db.session.query(Image, Prediction)\
        .outerjoin(Prediction, Image.id == Prediction.image_id)\
        .order_by(Image.upload_date.desc())\
        .limit(limit).offset(offset).all()
    
    results = []
    for img, pred in query:
        item = {
            'image_id': img.id,
            'filename': img.original_name,
            'upload_date': img.upload_date.isoformat() if img.upload_date else None,
            'predicted_class': pred.predicted_class if pred else None,
            'confidence': round(pred.confidence, 2) if pred else None,
            'heatmap_url': f'/static/heatmaps/{pred.heatmap_path}' if pred and pred.heatmap_path else None
        }
        results.append(item)
    
    return jsonify({
        'success': True,
        'total': Image.query.count(),
        'items': results
    })


@app.route('/api/result/<int:prediction_id>', methods=['GET'])
def get_result(prediction_id):
    """Детальная информация о конкретном анализе."""
    prediction = Prediction.query.get_or_404(prediction_id)
    
    # Все вероятности по классам
    details = Result.query.filter_by(prediction_id=prediction.id).all()
    probs = {d.class_name: round(d.probability, 4) for d in details}
    
    return jsonify({
        'success': True,
        'prediction_id': prediction.id,
        'predicted_class': prediction.predicted_class,
        'confidence': round(prediction.confidence, 4),
        'probabilities': probs,
        'processing_time': round(prediction.processing_time, 3),
        'created_at': prediction.created_at.isoformat() if prediction.created_at else None,
        'heatmap_url': f'/static/heatmaps/{prediction.heatmap_path}' if prediction.heatmap_path else None
    })


@app.route('/api/config', methods=['GET', 'POST'])
def model_config():
    """Получение/обновление настроек модели."""
    if request.method == 'GET':
        config = ModelConfig.query.first()
        if not config:
            return jsonify({'success': True, 'config': None})
        return jsonify({
            'success': True,
            'config': {
                'model_name': config.model_name,
                'threshold': config.threshold,
                'input_size': config.input_size
            }
        })
    
    # POST — обновление
    data = request.get_json()
    config = ModelConfig.query.first()
    if not config:
        config = ModelConfig()
        db.session.add(config)
    
    config.model_name = data.get('model_name', config.model_name)
    config.threshold = data.get('threshold', config.threshold)
    config.input_size = data.get('input_size', config.input_size)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Настройки обновлены'})


# === ЗАПУСК ===
if __name__ == '__main__':
    # debug=True — автоперезагрузка при изменении кода
    app.run(host='0.0.0.0', port=5000, debug=True)