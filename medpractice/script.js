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
        'settings': 'Параметры системы',
        'help': 'Справка и поддержка',
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

function handleFile(file) {
    document.getElementById('file-name').textContent = file.name;
    document.getElementById('file-meta').textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB • ${file.type || 'DICOM'}`;
    document.getElementById('file-info').style.display = 'block';
    document.getElementById('upload-actions').style.display = 'flex';
    
    // Имитация загрузки
    let progress = 0;
    const fill = document.getElementById('progress-fill');
    const text = document.getElementById('progress-text');
    
    const interval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress >= 100) {
            progress = 100;
            clearInterval(interval);
            text.textContent = 'Готово к анализу ✓';
        } else {
            text.textContent = `Загрузка... ${Math.round(progress)}%`;
        }
        fill.style.width = progress + '%';
    }, 200);
}

function resetUpload() {
    document.getElementById('file-info').style.display = 'none';
    document.getElementById('upload-actions').style.display = 'none';
    document.getElementById('progress-fill').style.width = '0%';
    document.getElementById('progress-text').textContent = 'Загрузка... 0%';
    fileInput.value = '';
}

function analyze() {
    // Переход к результатам
    showScreen('results');
    document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
    document.querySelector('[data-screen="dashboard"]').classList.add('active');
}
