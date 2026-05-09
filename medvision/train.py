"""
train.py — обучение DenseNet-121 на Chest X-Ray.

Запуск: python train.py
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import os
import json
import numpy as np
from datetime import datetime

# === ПУТЬ К ДАТАСЕТУ ===
# Поднимаемся на уровень выше из папки medvision/
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_ROOT = os.path.join(os.path.dirname(CURRENT_DIR), 'dataset')

print(f"Ищу датасет: {DATASET_ROOT}")

# === ПРОВЕРКА ===
for split in ['train', 'val', 'test']:
    path = os.path.join(DATASET_ROOT, split)
    exists = os.path.exists(path)
    print(f"  {split}: {'✓' if exists else '✗'} {path}")
    
    if exists:
        for cls in ['NORMAL', 'PNEUMONIA']:
            cls_path = os.path.join(path, cls)
            if os.path.exists(cls_path):
                count = len([f for f in os.listdir(cls_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
                print(f"    - {cls}: {count} файлов")

# === ТРАНСФОРМАЦИИ ===
train_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomRotation(degrees=10),
    transforms.ColorJitter(brightness=0.1, contrast=0.1),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

val_transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# === ЗАГРУЗКА ДАТАСЕТА ===
train_dataset = datasets.ImageFolder(os.path.join(DATASET_ROOT, 'train'), transform=train_transform)
val_dataset = datasets.ImageFolder(os.path.join(DATASET_ROOT, 'val'), transform=val_transform)
test_dataset = datasets.ImageFolder(os.path.join(DATASET_ROOT, 'test'), transform=val_transform)

print(f"\nКлассы: {train_dataset.classes}")
print(f"Train: {len(train_dataset)}")
print(f"Val: {len(val_dataset)}")
print(f"Test: {len(test_dataset)}")

# === DATALOADER ===
train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True, num_workers=0)
val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False, num_workers=0)
test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False, num_workers=0)

# === МОДЕЛЬ ===
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"\nУстройство: {device}")

model = models.densenet121(weights=models.DenseNet121_Weights.IMAGENET1K_V1)

# Замораживаем backbone
for param in model.parameters():
    param.requires_grad = False

# Заменяем classifier: 1024 → 2 класса
model.classifier = nn.Linear(model.classifier.in_features, 2)
model = model.to(device)

# === ОБУЧЕНИЕ ТОЛЬКО CLASSIFIER ===
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.classifier.parameters(), lr=0.001)

# === ЦИКЛ ОБУЧЕНИЯ ===
num_epochs = 5  # Начни с 5, потом увеличь до 10-15
best_acc = 0.0
history = {'train_loss': [], 'val_loss': [], 'val_acc': []}

os.makedirs('checkpoints', exist_ok=True)

for epoch in range(num_epochs):
    # --- Train ---
    model.train()
    train_loss = 0.0
    
    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        train_loss += loss.item()
    
    avg_train_loss = train_loss / len(train_loader)
    
    # --- Validation ---
    model.eval()
    val_loss = 0.0
    correct = 0
    total = 0
    all_probs = []
    all_labels = []
    
    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)
            val_loss += loss.item()
            
            probs = torch.softmax(outputs, dim=1)
            predicted = torch.argmax(probs, dim=1)
            
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            
            all_probs.extend(probs[:, 1].cpu().numpy())  # Вероятность PNEUMONIA
            all_labels.extend(labels.cpu().numpy())
    
    avg_val_loss = val_loss / len(val_loader)
    val_acc = correct / total
    
    history['train_loss'].append(avg_train_loss)
    history['val_loss'].append(avg_val_loss)
    history['val_acc'].append(val_acc)
    
    print(f"\nEpoch {epoch+1}/{num_epochs}")
    print(f"  Train Loss: {avg_train_loss:.4f}")
    print(f"  Val Loss:   {avg_val_loss:.4f}")
    print(f"  Val Acc:    {val_acc:.4f}")
    
    # Сохраняем лучшую модель
    if val_acc > best_acc:
        best_acc = val_acc
        torch.save({
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'val_acc': val_acc,
            'history': history
        }, 'checkpoints/best_model.pth')
        print(f"  ✓ Сохранена лучшая модель (acc={val_acc:.4f})")

# === ТЕСТИРОВАНИЕ ===
print("\n" + "="*50)
print("ТЕСТИРОВАНИЕ")
print("="*50)

checkpoint = torch.load('checkpoints/best_model.pth')
model.load_state_dict(checkpoint['model_state_dict'])

model.eval()
all_preds = []
all_labels = []
all_probs = []

with torch.no_grad():
    for images, labels in test_loader:
        images = images.to(device)
        outputs = model(images)
        probs = torch.softmax(outputs, dim=1)
        preds = torch.argmax(probs, dim=1)
        
        all_preds.extend(preds.cpu().numpy())
        all_labels.extend(labels.numpy())
        all_probs.extend(probs[:, 1].cpu().numpy())

# Метрики
print("\nClassification Report:")
print(classification_report(all_labels, all_preds, target_names=['NORMAL', 'PNEUMONIA']))

print(f"\nAUC-ROC: {roc_auc_score(all_labels, all_probs):.4f}")

# Confusion Matrix
cm = confusion_matrix(all_labels, all_preds)
print(f"\nConfusion Matrix:")
print(f"                 Предсказано")
print(f"                 NORMAL  PNEUMONIA")
print(f"Истинное NORMAL    {cm[0,0]:4d}     {cm[0,1]:4d}")
print(f"Истинное PNEUMONIA {cm[1,0]:4d}     {cm[1,1]:4d}")

# Сохраняем историю
with open('checkpoints/history.json', 'w') as f:
    json.dump(history, f, indent=2)

print("\nГотово! Модель сохранена в checkpoints/best_model.pth")