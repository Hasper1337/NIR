"""
preprocess.py — подготовка изображений перед подачей в нейросеть.

Медицинские снимки приходят в разных форматах и разрешениях.
Нейросеть требует строго фиксированный вход: тензор [3, 224, 224].
"""

import torch
from torchvision import transforms
from PIL import Image, UnidentifiedImageError
import numpy as np
import os

# Импортируем настройки из корня проекта
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config


def get_transforms():
    """
    Создаёт цепочку преобразований (pipeline).
    
    Порядок важен:
    1. Resize — меняем размер до 224×224 (или чуть больше для CenterCrop)
    2. CenterCrop — вырезаем центральную часть (убираем артефакты по краям)
    3. ToTensor — PIL Image → torch.Tensor [0, 1]
    4. Normalize — приводим к статистикам ImageNet (transfer learning требует)
    """
    return transforms.Compose([
        transforms.Resize(size=256),           # Сначала немного больше
        transforms.CenterCrop(size=Config.INPUT_SIZE),  # Точно 224×224
        transforms.ToTensor(),                  # [H, W, C] → [C, H, W], значения [0,1]
        transforms.Normalize(                  # (x - mean) / std
            mean=Config.IMAGENET_MEAN,
            std=Config.IMAGENET_STD
        )
    ])


def preprocess_image(image_path):
    """
    Загружает изображение с диска и готовит тензор для модели.
    
    Аргументы:
        image_path — путь к файлу (PNG, JPEG, DICOM)
    
    Возвращает:
        tensor — тензор формы [1, 3, 224, 224] (батч из 1 изображения)
    """
    # Открываем изображение. PIL поддерживает PNG, JPEG, BMP, TIFF
    # Для DICOM нужна библиотека pydicom (опционально)
    ext = os.path.splitext(image_path)[1].lower()
    try:
        if ext in {'.dcm', '.dicom'}:
            image = load_dicom(image_path)
        else:
            image = Image.open(image_path).convert('RGB')  # Принудительно RGB, даже если grayscale
    except UnidentifiedImageError:
        raise ValueError('Невозможно распознать формат изображения')
    
    transform = get_transforms()
    tensor = transform(image)  # [3, 224, 224]
    
    # Добавляем размерность батча: [3, 224, 224] → [1, 3, 224, 224]
    # Нейросеть ожидает батч, даже если изображение одно
    tensor = tensor.unsqueeze(0)
    
    return tensor


def load_dicom(dicom_path):
    """
    Загрузка DICOM-файла (медицинский формат).
    Требует установки: pip install pydicom
    """
    try:
        import pydicom
        ds = pydicom.dcmread(dicom_path)
        # DICOM → numpy array → PIL Image
        img_array = ds.pixel_array
        # Нормализация в диапазон 0-255
        img_array = ((img_array - img_array.min()) / 
                     (img_array.max() - img_array.min()) * 255).astype(np.uint8)
        return Image.fromarray(img_array).convert('RGB')
    except ImportError:
        raise ImportError("Установите pydicom: pip install pydicom")