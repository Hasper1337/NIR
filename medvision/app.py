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
from flask import Flask, render_template, request, jsonify, send_file, session
from werkzeug.utils import secure_filename
import json
from sqlalchemy import func, inspect, text
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config, BASE_DIR
from models import db, User, Image, Prediction, Result, ModelConfig
from ml.preprocess import preprocess_image
from ml.classifier import get_classifier
from ml.gradcam import save_gradcam
from ml.reporter import generate_report

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

    inspector = inspect(db.engine)
    if 'users' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('users')]
        if 'password_hash' not in columns:
            db.session.execute(text('ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)'))
            db.session.commit()
    
    # Создаём тестового пользователя, если нет
    if not User.query.first():
        demo_user = User(
            username='demo',
            email='demo@medvision.ru',
            password_hash=generate_password_hash('demo')
        )
        db.session.add(demo_user)
        db.session.commit()
        print("Создан демо-пользователь (id=1)")
    else:
        demo_user = User.query.filter_by(username='demo').first()
        if demo_user:
            demo_user.password_hash = generate_password_hash('demo')
            db.session.commit()


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


def _current_user():
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None


@app.route('/api/session', methods=['GET'])
def get_session():
    user = _current_user()
    if not user:
        return jsonify({'success': True, 'logged_in': False})
    return jsonify({
        'success': True,
        'logged_in': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        }
    })


@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not username or not email or not password:
        return jsonify({'success': False, 'message': 'Заполните все поля'}), 400
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({'success': False, 'message': 'Пользователь уже существует'}), 400

    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password)
    )
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id

    return jsonify({'success': True})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'success': False, 'message': 'Введите логин и пароль'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'Неверные данные'}), 401

    if not user.password_hash:
        if user.username == 'demo' and password == 'demo':
            user.password_hash = generate_password_hash('demo')
            db.session.commit()
        else:
            return jsonify({'success': False, 'message': 'Неверные данные'}), 401

    if not check_password_hash(user.password_hash, password):
        return jsonify({'success': False, 'message': 'Неверные данные'}), 401

    session['user_id'] = user.id
    return jsonify({'success': True})


@app.route('/api/stats', methods=['GET'])
def stats():
    """Статистика для главного экрана."""
    total_predictions = Prediction.query.count()
    total_images = Image.query.count()
    today_str = datetime.utcnow().strftime('%Y-%m-%d')
    today_count = db.session.query(Prediction).filter(func.date(Prediction.created_at) == today_str).count()

    accuracy = None
    history_path = os.path.join(BASE_DIR, 'checkpoints', 'history.json')
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
            val_acc = history.get('val_acc', [])
            if val_acc:
                accuracy = max(val_acc)
        except Exception:
            accuracy = None

    recent_query = db.session.query(Image, Prediction)\
        .outerjoin(Prediction, Image.id == Prediction.image_id)\
        .order_by(Image.upload_date.desc())\
        .limit(5).all()

    recent = []
    for img, pred in recent_query:
        recent.append({
            'date': img.upload_date.isoformat() if img.upload_date else None,
            'filename': img.original_name,
            'predicted_class': pred.predicted_class if pred else None,
            'confidence': pred.confidence if pred else None
        })

    return jsonify({
        'success': True,
        'total_predictions': total_predictions,
        'total_images': total_images,
        'today_count': today_count,
        'accuracy': accuracy,
        'recent': recent
    })


@app.route('/api/logout', methods=['POST'])
def logout():
    """Демо-выход (без сессий)."""
    session.pop('user_id', None)
    return jsonify({'success': True})


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
    user = _current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Требуется вход'}), 401
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
    user = _current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Требуется вход'}), 401

    img_record = Image.query.get_or_404(image_id)
    if img_record.user_id != user.id:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403
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

            user = _current_user() or User.query.first()

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

    except (ValueError, OSError, ImportError) as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400
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
    
    user = _current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Требуется вход'}), 401

    # JOIN таблиц Image и Prediction — только завершённые анализы
    query = db.session.query(Image, Prediction)\
        .join(Prediction, Image.id == Prediction.image_id)\
        .filter(Image.user_id == user.id)\
        .order_by(Image.upload_date.desc())\
        .limit(limit).offset(offset).all()
    
    results = []
    for img, pred in query:
        item = {
            'image_id': img.id,
            'filename': img.original_name,
            'upload_date': img.upload_date.isoformat() if img.upload_date else None,
            'prediction_id': pred.id if pred else None,
            'predicted_class': pred.predicted_class if pred else None,
            'confidence': round(pred.confidence, 2) if pred else None,
            'heatmap_url': f'/static/heatmaps/{pred.heatmap_path}' if pred and pred.heatmap_path else None
        }
        results.append(item)
    
    return jsonify({
        'success': True,
        'total': db.session.query(Prediction)\
            .join(Image, Image.id == Prediction.image_id)\
            .filter(Image.user_id == user.id).count(),
        'items': results
    })


@app.route('/api/result/<int:prediction_id>', methods=['GET'])
def get_result(prediction_id):
    """Детальная информация о конкретном анализе."""
    prediction = Prediction.query.get_or_404(prediction_id)
    user = _current_user()
    if not user or not prediction.image or prediction.image.user_id != user.id:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403
    
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
        'heatmap_url': f'/static/heatmaps/{prediction.heatmap_path}' if prediction.heatmap_path else None,
        'original_url': f'/static/uploads/{prediction.image.filename}' if prediction.image else None
    })


@app.route('/api/report/<int:prediction_id>', methods=['GET'])
def export_report(prediction_id):
    """Генерация и отдача PDF-отчёта по предсказанию."""
    prediction = Prediction.query.get_or_404(prediction_id)
    user = _current_user()
    if not user or not prediction.image or prediction.image.user_id != user.id:
        return jsonify({'success': False, 'message': 'Нет доступа'}), 403
    details = Result.query.filter_by(prediction_id=prediction.id).all()
    probs = {d.class_name: round(d.probability, 4) for d in details}

    prediction_data = {
        'predicted_class': prediction.predicted_class,
        'confidence': prediction.confidence,
        'probabilities': probs,
        'original_url': f'/static/uploads/{prediction.image.filename}' if prediction.image else None,
        'heatmap_url': f'/static/heatmaps/{prediction.heatmap_path}' if prediction.heatmap_path else None
    }

    report_name = f"report_{prediction.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    report_path = os.path.join(Config.REPORT_FOLDER, report_name)
    generate_report(prediction_data, report_path)
    return send_file(report_path, as_attachment=True, download_name=report_name)


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


@app.route('/api/config/defaults', methods=['GET'])
def model_config_defaults():
    """Дефолтные настройки модели из Config."""
    return jsonify({
        'success': True,
        'config': {
            'model_name': Config.MODEL_NAME,
            'threshold': Config.CONFIDENCE_THRESHOLD,
            'input_size': Config.INPUT_SIZE
        }
    })


# === ЗАПУСК ===
if __name__ == '__main__':
    # debug=True — автоперезагрузка при изменении кода
    app.run(host='0.0.0.0', port=5000, debug=True)