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

    if (screenName === 'history') {
        loadHistory();
    }
    if (screenName === 'settings') {
        loadSettings();
    }
    if (screenName === 'dashboard') {
        loadStats();
    }
}

// ===== AUTH =====
function showAuthScreen() {
    document.body.classList.add('auth-mode');
    document.getElementById('auth-screen').style.display = 'flex';
}

function hideAuthScreen() {
    document.body.classList.remove('auth-mode');
    document.getElementById('auth-screen').style.display = 'none';
}

function showAuthTab(tab) {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const loginTab = document.getElementById('tab-login');
    const registerTab = document.getElementById('tab-register');
    const error = document.getElementById('auth-error');

    if (error) error.textContent = '';

    if (tab === 'register') {
        registerForm.style.display = 'flex';
        loginForm.style.display = 'none';
        registerTab.classList.add('active');
        loginTab.classList.remove('active');
    } else {
        loginForm.style.display = 'flex';
        registerForm.style.display = 'none';
        loginTab.classList.add('active');
        registerTab.classList.remove('active');
    }
}

function setUserName(name) {
    const el = document.getElementById('user-name');
    if (el) el.textContent = name || 'Гость';
}

function checkSession() {
    fetch('/api/session')
        .then(r => r.json())
        .then(data => {
            if (!data.success || !data.logged_in) {
                setUserName('Гость');
                showAuthScreen();
                return;
            }
            setUserName(data.user.username);
            hideAuthScreen();
            showScreen('dashboard');
        })
        .catch(() => {
            showAuthScreen();
        });
}

const loginForm = document.getElementById('login-form');
if (loginForm) {
    loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const payload = {
            username: document.getElementById('login-username').value.trim(),
            password: document.getElementById('login-password').value
        };
        fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(r => r.json().then(data => ({ ok: r.ok, data })))
        .then(({ ok, data }) => {
            if (!ok || !data.success) {
                document.getElementById('auth-error').textContent = data.message || 'Ошибка входа';
                return;
            }
            checkSession();
        })
        .catch(() => {
            document.getElementById('auth-error').textContent = 'Ошибка сети';
        });
    });
}

const registerForm = document.getElementById('register-form');
if (registerForm) {
    registerForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const payload = {
            username: document.getElementById('register-username').value.trim(),
            email: document.getElementById('register-email').value.trim(),
            password: document.getElementById('register-password').value
        };
        fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(r => r.json().then(data => ({ ok: r.ok, data })))
        .then(({ ok, data }) => {
            if (!ok || !data.success) {
                document.getElementById('auth-error').textContent = data.message || 'Ошибка регистрации';
                return;
            }
            checkSession();
        })
        .catch(() => {
            document.getElementById('auth-error').textContent = 'Ошибка сети';
        });
    });
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
    .then(async r => {
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
            const msg = data.message || `HTTP ${r.status}`;
            throw new Error(msg);
        }
        return data;
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
    origImg.style.display = 'block';
    origImg.classList.add('loaded');
    document.getElementById('original-placeholder').style.display = 'none';
    
    const heatImg = document.getElementById('heatmap-img');
    heatImg.src = data.heatmap_url;
    heatImg.style.display = 'block';
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

// ===== СТАТИСТИКА =====
function loadStats() {
    fetch('/api/stats')
        .then(r => r.json())
        .then(data => {
            if (!data.success) return;
            const total = data.total_predictions ?? 0;
            const today = data.today_count ?? 0;
            const accuracy = data.accuracy;

            document.getElementById('stat-total').textContent = total;
            document.getElementById('stat-today').textContent = today;
            document.getElementById('stat-accuracy').textContent =
                accuracy !== null && accuracy !== undefined
                    ? `${(accuracy * 100).toFixed(1)}%`
                    : '—';

            renderRecent(data.recent || []);
        })
        .catch(err => console.error(err));
}

function renderRecent(items) {
    const body = document.getElementById('recent-body');
    if (!body) return;
    body.innerHTML = '';

    if (!items.length) {
        body.innerHTML = '<tr><td colspan="4">Нет данных</td></tr>';
        return;
    }

    for (const item of items) {
        const date = item.date ? new Date(item.date).toLocaleString('ru-RU') : '—';
        const diag = item.predicted_class || '—';
        const conf = item.confidence !== null && item.confidence !== undefined ? `${(item.confidence * 100).toFixed(1)}%` : '—';
        const badgeClass = diag === 'Норма' ? 'green' : (diag === 'Патология' ? 'red' : 'orange');

        body.innerHTML += `
            <tr>
                <td>${date}</td>
                <td>${item.filename || '—'}</td>
                <td><span class="badge ${badgeClass}">${diag}</span></td>
                <td>${conf}</td>
            </tr>
        `;
    }
}

// ===== ВЫХОД =====
const logoutBtn = document.getElementById('btn-logout');
if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        fetch('/api/logout', { method: 'POST' })
            .then(() => {
                resetUpload();
                showAuthScreen();
            })
            .catch(() => {
                resetUpload();
                showAuthScreen();
            });
    });
}

// Первичная проверка сессии
checkSession();

// ===== ИСТОРИЯ =====
let historyCache = [];

function loadHistory() {
    fetch('/api/history?limit=50&offset=0')
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                alert('Ошибка загрузки истории');
                return;
            }
            historyCache = data.items || [];
            renderHistory(historyCache);
        })
        .catch(err => {
            console.error(err);
            alert('Ошибка сети при загрузке истории');
        });
}

function renderHistory(items) {
    const body = document.getElementById('history-body');
    body.innerHTML = '';

    if (!items.length) {
        body.innerHTML = '<tr><td colspan="6">История пуста</td></tr>';
        return;
    }

    for (const item of items) {
        const date = item.upload_date ? new Date(item.upload_date).toLocaleString('ru-RU') : '—';
        const diag = item.predicted_class || '—';
        const conf = item.confidence !== null && item.confidence !== undefined ? `${(item.confidence * 100).toFixed(1)}%` : '—';
        const badgeClass = diag === 'Норма' ? 'green' : (diag === 'Патология' ? 'red' : 'orange');
        const predictionId = item.prediction_id;

        body.innerHTML += `
            <tr>
                <td>${item.image_id}</td>
                <td>${date}</td>
                <td>${item.filename || '—'}</td>
                <td><span class="badge ${badgeClass}">${diag}</span></td>
                <td>${conf}</td>
                <td>
                    <button class="btn-icon" onclick="viewResult(${predictionId || 'null'})">👁</button>
                    <button class="btn-icon" onclick="exportPDF(${predictionId || 'null'})">💾</button>
                </td>
            </tr>
        `;
    }
}

const historySearch = document.getElementById('history-search');
if (historySearch) {
    historySearch.addEventListener('input', () => {
        const query = historySearch.value.trim().toLowerCase();
        if (!query) {
            renderHistory(historyCache);
            return;
        }
        const filtered = historyCache.filter(item => {
            const date = item.upload_date ? new Date(item.upload_date).toLocaleString('ru-RU').toLowerCase() : '';
            const name = (item.filename || '').toLowerCase();
            return date.includes(query) || name.includes(query);
        });
        renderHistory(filtered);
    });
}

function viewResult(predictionId) {
    if (!predictionId) {
        alert('Анализ ещё не выполнен');
        return;
    }
    fetch(`/api/result/${predictionId}`)
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                alert('Ошибка загрузки результата');
                return;
            }
            showScreen('results');
            displayResults(data);
        })
        .catch(err => {
            console.error(err);
            alert('Ошибка сети при загрузке результата');
        });
}

// ===== PDF =====
function exportPDF(predictionId = null) {
    const id = predictionId || document.getElementById('results-panel').dataset.predictionId;
    if (!id) {
        alert('Сначала выполните анализ');
        return;
    }
    window.open(`/api/report/${id}`, '_blank');
}

// ===== НАСТРОЙКИ =====
function loadSettings() {
    fetch('/api/config')
        .then(r => r.json())
        .then(data => {
            if (!data.success) return;
            const cfg = data.config || {};
            if (cfg.model_name) document.getElementById('model-name').value = cfg.model_name;
            if (cfg.threshold !== undefined) document.getElementById('threshold').value = cfg.threshold;
            if (cfg.input_size !== undefined) document.getElementById('input-size').value = cfg.input_size;
        })
        .catch(err => console.error(err));
}

function saveSettings() {
    const payload = {
        model_name: document.getElementById('model-name').value,
        threshold: parseFloat(document.getElementById('threshold').value),
        input_size: parseInt(document.getElementById('input-size').value, 10)
    };

    fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            alert('Ошибка сохранения настроек');
            return;
        }
        alert('Настройки сохранены');
    })
    .catch(err => {
        console.error(err);
        alert('Ошибка сети при сохранении');
    });
}

function resetSettings() {
    fetch('/api/config/defaults')
        .then(r => r.json())
        .then(data => {
            if (!data.success) return;
            const cfg = data.config || {};
            if (cfg.model_name) document.getElementById('model-name').value = cfg.model_name;
            if (cfg.threshold !== undefined) document.getElementById('threshold').value = cfg.threshold;
            if (cfg.input_size !== undefined) document.getElementById('input-size').value = cfg.input_size;
        })
        .catch(err => console.error(err));
}