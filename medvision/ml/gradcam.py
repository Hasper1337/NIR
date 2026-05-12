"""
gradcam.py — рабочая версия Grad-CAM без inplace-операций.

Исправление: используем register_forward_hook на последний conv-слой
и backward через torch.autograd.grad вместо .backward().
"""

import torch
import torch.nn.functional as F
import numpy as np
import cv2
from PIL import Image
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config


class GradCAM:
    """
    Grad-CAM через forward hooks и torch.autograd.grad.
    Избегает inplace-операций DenseNet.
    """
    
    def __init__(self, model):
        self.model = model
        self.features = None
        self.gradients = None
        
        # Находим последний conv-слой в features
        self.target_layer = None
        for module in model.features.modules():
            if isinstance(module, torch.nn.Conv2d):
                self.target_layer = module
        
        if self.target_layer is None:
            raise ValueError("Conv2d слой не найден!")
        
        # Регистрируем hooks
        self.target_layer.register_forward_hook(self._save_features)
        self.target_layer.register_full_backward_hook(self._save_gradients)
        
        print(f"Grad-CAM: target = {type(self.target_layer).__name__}")
    
    def _save_features(self, module, input, output):
        self.features = output
    
    def _save_gradients(self, module, grad_input, grad_output):
        self.gradients = grad_output[0]
    
    def generate(self, image_tensor, target_class=None):
        self.model.eval()
        
        # Forward с включёнными градиентами
        image_tensor.requires_grad = True
        output = self.model(image_tensor)
        
        if target_class is None:
            target_class = output.argmax(dim=1).item()
        
        # Целевой score (логит целевого класса)
        target_score = output[0, target_class]
        
        # Вычисляем градиенты через autograd.grad (без inplace)
        grads = torch.autograd.grad(
            outputs=target_score,
            inputs=self.features,
            retain_graph=True,
            create_graph=False
        )[0]
        
        # Grad-CAM: усредняем градиенты по пространству
        weights = grads.mean(dim=(2, 3), keepdim=True)
        
        # Взвешенная сумма feature maps
        cam = (weights * self.features).sum(dim=1, keepdim=True)
        cam = F.relu(cam)
        
        # Нормализация
        cam = cam - cam.min()
        cam = cam / (cam.max() + 1e-8)
        
        # Интерполяция до 224x224
        cam = F.interpolate(cam, size=(224, 224), mode='bilinear', align_corners=False)
        cam = cam[0, 0].detach().cpu().numpy()
        
        # Цветовая карта
        heatmap = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
        
        # Денормализация изображения
        mean = torch.tensor(Config.IMAGENET_MEAN).view(3, 1, 1)
        std = torch.tensor(Config.IMAGENET_STD).view(3, 1, 1)
        img = image_tensor[0].detach().cpu() * std + mean
        img = img.permute(1, 2, 0).numpy()
        img = np.clip(img, 0, 1)
        img = np.uint8(255 * img)
        
        # Наложение
        alpha = 0.5
        result = np.uint8(alpha * heatmap + (1 - alpha) * img)
        
        return result, cam


def save_gradcam(image_tensor, save_path, target_class=None, model=None):
    if model is None:
        from ml.classifier import get_classifier
        model = get_classifier().model
    
    gradcam = GradCAM(model)
    result_img, _ = gradcam.generate(image_tensor, target_class)
    
    Image.fromarray(result_img).save(save_path)
    return save_path


if __name__ == '__main__':
    from ml.classifier import get_classifier
    from ml.preprocess import preprocess_image
    from PIL import Image
    import numpy as np
    
    test = np.random.randint(50, 200, (224, 224, 3), dtype=np.uint8)
    Image.fromarray(test).save('test_gradcam.jpg')
    
    tensor = preprocess_image('test_gradcam.jpg')
    classifier = get_classifier()
    pred = classifier.predict(tensor)
    
    print(f"Предсказан класс: {pred['predicted_class']} (индекс {pred['predicted_idx']})")
    
    save_gradcam(tensor, 'test_heatmap.jpg', target_class=pred['predicted_idx'])
    print("✓ Heatmap сохранён в test_heatmap.jpg")