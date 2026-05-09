"""
classifier.py — загрузка нейросети и классификация.

Используем transfer learning: берём DenseNet-121, предобученный на ImageNet,
и заменяем последний слой (classifier) на наш с 3 классами.
"""

import torch
import torch.nn as nn
from torchvision import models
import time
import os

# Для импорта config из родительской папки
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config


class MedicalClassifier:
    """
    Обертка над нейросетью. Реализует singleton-паттерн:
    модель загружается один раз при первом вызове и хранится в памяти.
    """
    
    _instance = None  # Единственный экземпляр класса
    
    def __new__(cls):
        """Singleton: гарантируем одну загруженную модель."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"Используется устройство: {self.device}")
        
        # Загружаем предобученную архитектуру
        self.model = models.densenet121(weights=models.DenseNet121_Weights.IMAGENET1K_V1)
        
        # Transfer learning: замораживаем все слои, кроме classifier
        # Это ускоряет обучение и предотвращает переобучение на малом датасете
        for param in self.model.parameters():
            param.requires_grad = False  # Не обновлять веса при обучении
        
        # Заменяем последний слой: 1024 входов → 3 класса
        num_features = self.model.classifier.in_features
        self.model.classifier = nn.Linear(num_features, Config.NUM_CLASSES)
        
        # В реальном проекте здесь загрузка дообученных весов:
        # checkpoint = torch.load('weights.pth', map_location=self.device)
        # self.model.load_state_dict(checkpoint['model_state_dict'])


        checkpoint_path = os.path.join(
            os.path.dirname(__file__),  # папка ml/
            '..',                       # вверх в medvision/
            'checkpoints', 
            'best_model.pth'
        )

        if os.path.exists(checkpoint_path):
            checkpoint = torch.load(checkpoint_path, map_location=self.device)
            
            # Загружаем только веса (state_dict)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            
            # Выводим инфо
            val_acc = checkpoint.get('val_acc', 'неизвестно')
            epoch = checkpoint.get('epoch', 'неизвестно')
            print(f"✓ Загружена обученная модель")
            print(f"  Эпоха: {epoch + 1}")
            print(f"  Точность на валидации: {val_acc:.2%}" if isinstance(val_acc, float) else f"  Точность: {val_acc}")
        else:
            print("⚠ Обученные веса не найдены!")
            print(f"  Искал: {checkpoint_path}")
            print("  Используются случайные веса (предсказания бессмысленны)")
        

        self.model = self.model.to(self.device)
        self.model.eval()  # Режим инференса (отключаем dropout, batchnorm статистики)
        
        self.class_names = Config.CLASS_NAMES
        self._initialized = True
    
    def predict(self, image_tensor):
        """
        Классификация одного изображения.
        
        Аргументы:
            image_tensor — тензор [1, 3, 224, 224] из preprocess.py
        
        Возвращает:
            dict с диагнозом, вероятностями, временем обработки
        """
        start_time = time.time()
        
        # Переносим тензор на GPU/CPU
        image_tensor = image_tensor.to(self.device)
        
        # Инференс без градиентов (экономит память и ускоряет)
        with torch.no_grad():
            # Прямой проход: [1, 3, 224, 224] → [1, 3]
            outputs = self.model(image_tensor)
            
            # Softmax превращает "сырые" выходы в вероятности [0, 1]
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            
            # Вероятности по каждому классу
            probs = probabilities[0].cpu().numpy()
            
            # Класс с максимальной вероятностью
            predicted_idx = int(torch.argmax(probabilities, dim=1).item())
            confidence = float(probs[predicted_idx])
        
        processing_time = time.time() - start_time
        
        # Формируем результат
        result = {
            'predicted_class': self.class_names[predicted_idx],
            'predicted_idx': predicted_idx,
            'confidence': confidence,
            'probabilities': {
                name: float(prob) 
                for name, prob in zip(self.class_names, probs)
            },
            'processing_time': processing_time,
            # Для Grad-CAM нужны feature maps — сохраняем их
            'feature_maps': None  # Заполняется в gradcam.py
        }
        
        return result


# Глобальная точка доступа к модели
_classifier = None

def get_classifier():
    """Фабричная функция — гарантирует единственный экземпляр."""
    global _classifier
    if _classifier is None:
        _classifier = MedicalClassifier()
    return _classifier


if __name__ == '__main__':
    # Тестовый запуск
    from preprocess import preprocess_image
    import numpy as np
    
    # Создаём случайное изображение для теста
    test_img = np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)
    from PIL import Image
    img = Image.fromarray(test_img)
    img.save('test.jpg')
    
    tensor = preprocess_image('test.jpg')
    classifier = get_classifier()
    result = classifier.predict(tensor)
    
    print(f"Диагноз: {result['predicted_class']}")
    print(f"Уверенность: {result['confidence']:.2%}")
    print(f"Время: {result['processing_time']:.3f} сек")
    print("Все вероятности:", result['probabilities'])