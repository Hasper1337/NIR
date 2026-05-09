// ===== НАВИГАЦИЯ =====
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const screen = item.dataset.screen;
        showScreen(screen);
        
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
    });
});

function showScreen(screenName) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    
    const screenMap = {
        'dashboard': 'screen-dashboard',
        'upload': 'screen-upload',
        'history': 'screen-history',
        'settings': 'screen-settings',
        'help': 'screen-help',
        'results': 'screen-results'
    };
    
    const screenId = screenMap[screenName];
    if (screenId) {
        document.getElementById(screenId).classList.add('active');
    }
    
    // Обновление заголовка
    const titles = {
        'dashboard': 'Главная панель',
        'upload': 'Загрузка изображения',
        'history': 'История анализов',
        'settings': 'Настройки модели',
        'help': 'Помощь',
        'results': 'Результаты анализа'
    };
    document.getElementById('page-title').textContent = titles[screenName] || '';
}

// ===== ЗАГРУЗКА ФАЙЛА =====
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFile(e.target.files[0]);
    }
});

let currentImageId = null;

function handleFile(file) {
    const formData = new FormData();
    formData.append('image', file);
    
    // Показываем прогресс
    document.querySelector('.upload-text').textContent = 'Загрузка...';
    
    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            alert('Ошибка загрузки: ' + data.message);
            return;
        }
        
        // Сохраняем ID
        currentImageId = data.image_id;
        console.log('Загружено, image_id:', currentImageId);
        
        // Показываем инфо
        const fileInfo = document.getElementById('file-info');
        fileInfo.style.display = 'block';
        fileInfo.dataset.currentImageId = data.image_id;  // Для надёжности
        
        document.getElementById('file-name').textContent = data.filename || file.name;
        document.getElementById('file-meta').textContent = `Размер: ${(file.size/1024/1024).toFixed(2)} MB`;
        
        // Прогресс 100%
        document.getElementById('progress-fill').style.width = '100%';
        document.getElementById('progress-text').textContent = 'Готово';
        
        // Показываем кнопки
        document.getElementById('upload-actions').style.display = 'flex';
    })
    .catch(err => {
        console.error(err);
        alert('Ошибка сети при загрузке');
    });
}


function resetUpload() {
    // Сброс всего
    currentImageId = null;
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('file-info').dataset.currentImageId = '';
    document.getElementById('upload-actions').style.display = 'none';
    document.getElementById('upload-zone').style.display = 'block';
    document.querySelector('.upload-text').textContent = 'Перетащите сюда изображение';
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('file-input').value = '';
}

function analyze() {
    const imageId = currentImageId;
    console.log('Анализируем image_id:', imageId);
    
    if (!imageId && imageId !== 0) {
        alert('Сначала загрузите изображение');
        return;
    }
    
    // Показываем загрузку
    document.querySelector('.upload-text').textContent = 'Анализируем...';
    document.getElementById('upload-actions').style.display = 'none';
    
    fetch(`/api/analyze/${imageId}`, {
        method: 'POST'
    })
    .then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
    })
    .then(data => {
        if (!data.success) {
            alert('Ошибка анализа: ' + data.message);
            document.getElementById('upload-actions').style.display = 'flex';
            return;
        }
        
        showScreen('results');
        displayResults(data);
    })
    .catch(err => {
        console.error(err);
        alert('Ошибка: ' + err.message);
        document.getElementById('upload-actions').style.display = 'flex';
    });
}

    // Показываем загрузку
    document.querySelector('.upload-text').textContent = 'Анализируем...';
    
    fetch(`/api/analyze/${imageId}`, {
        method: 'POST'
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            // Показываем информацию о файле
            document.getElementById('file-info').style.display = 'block';
            document.getElementById('file-name').textContent = data.filename;
            document.getElementById('file-meta').textContent = `ID: ${data.image_id}`;
            
            // === ВАЖНО: сохраняем image_id ===
            document.getElementById('file-info').dataset.imageId = data.image_id;
            
            // Показываем кнопки
            document.getElementById('upload-actions').style.display = 'flex';
            
            // Скрываем зону загрузки
            document.getElementById('upload-zone').style.display = 'none';
        }
    })

function displayResults(data) {
    // Диагноз
    const className = data.predicted_class;
    const isNormal = className === 'Норма';
    
    document.getElementById('result-class').textContent = className;
    document.getElementById('result-confidence').textContent = (data.confidence * 100).toFixed(1) + '%';
    
    // Бейдж диагноза
    const badge = document.getElementById('diagnosis-badge');
    badge.className = 'diagnosis-badge ' + (isNormal ? 'normal' : 'pathology');
    
    // Изображения
    const origImg = document.getElementById('original-img');
    origImg.src = data.original_url;
    origImg.classList.add('loaded');
    document.getElementById('original-placeholder').style.display = 'none';
    
    const heatImg = document.getElementById('heatmap-img');
    heatImg.src = data.heatmap_url;
    heatImg.classList.add('loaded');
    document.getElementById('heatmap-placeholder').style.display = 'none';
    
    // Вероятности
    const probsContainer = document.getElementById('probabilities-list');
    probsContainer.innerHTML = '';
    
    for (const [cls, prob] of Object.entries(data.probabilities)) {
        const percent = (prob * 100).toFixed(1);
        const color = cls === 'Норма' ? 'green' : 'red';
        
        probsContainer.innerHTML += `
            <div class="result-item">
                <span class="result-label">${cls}</span>
                <span class="result-value ${color}">${percent}%</span>
                <div class="result-bar">
                    <div class="result-fill ${color}" style="width: ${percent}%"></div>
                </div>
            </div>
        `;
    }
    
    // Сохраняем ID для PDF
    document.getElementById('results-panel').dataset.predictionId = data.prediction_id;
}