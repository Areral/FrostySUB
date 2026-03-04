const BASE_URL = window.location.origin;

const APP_DATABASE = {
    "throne": {
        name: "Throne", icon: "fa-solid fa-chess-rook", url: "https://github.com/throneproj/Throne/releases/latest",
        guide: `
            <div class="step-list">
                <div class="step-item">Нажмите <b>«Получить доступ»</b> выше и скопируйте ссылку на подписку.</div>
                <div class="step-item">В клиенте нажмите на <b>«Профили»</b> -> <b>«Добавить профиль из буфера обмена»</b>.</div>
                <div class="step-item">Выделите все профили (Ctrl+A), нажмите <b>«Профили»</b> -> <b>«Тест задержки (пинга)»</b>.</div>
                <div class="step-item">Дождитесь надписи <i>«Тест задержек завершён!»</i> в логах снизу.</div>
                <div class="step-item">Кликните по колонке <b>«Задержка (пинг)»</b> для сортировки от меньшего к большему.</div>
                <div class="step-item">Сверху установите галочку <b>«Режим TUN»</b> (важно для обхода DPI).</div>
                <div class="step-item">Выберите сервер с лучшим пингом -> Правая кнопка мыши -> <b>«Запустить»</b>.</div>
            </div>
        `
    },
    "nekobox": {
        name: "NekoBox", icon: "fa-solid fa-cat", url: "https://github.com/MatsuriDayo/nekoray/releases/latest",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">Перейдите в <b>«Настройки»</b> -> <b>«Группы»</b> -> <b>«Новая группа»</b>.</div>
                <div class="step-item">Выберите тип <b>«Подписка»</b> и вставьте вашу ссылку. Нажмите Ок.</div>
                <div class="step-item">Нажмите кнопку <b>«Обновить подписки»</b>.</div>
                <div class="step-item">Включите галочку <b>«Режим TUN»</b> и запустите выбранный сервер.</div>
            </div>
        `
    },
    "v2rayn": {
        name: "v2rayN", icon: "fa-solid fa-v", url: "https://github.com/2dust/v2rayN/releases/latest",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на конфиг.</div>
                <div class="step-item">Перейдите в <b>«Подписки»</b> -> <b>«Настройки подписки»</b> -> <b>«Добавить»</b>.</div>
                <div class="step-item">Вставьте ссылку в поле <code>Url</code>, сохраните.</div>
                <div class="step-item">В главном меню нажмите <b>«Обновить подписку»</b>.</div>
                <div class="step-item">Выделите сервер с хорошим пингом и нажмите <b>Enter</b> для подключения.</div>
            </div>
        `
    },
    "singbox": {
        name: "Singbox UI", icon: "fa-solid fa-box", url: "https://github.com/Leadaxe/singbox-launcher/releases/latest",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">Запустите Singbox-launcher и перейдите во вкладку профилей.</div>
                <div class="step-item">Нажмите <b>«Добавить»</b> и вставьте вашу ссылку.</div>
                <div class="step-item">Сделайте тест задержки и выберите оптимальный маршрут.</div>
                <div class="step-item">Нажмите главную кнопку старта для активации туннеля.</div>
            </div>
        `
    },
    "karing": {
        name: "Karing", icon: "fa-solid fa-paper-plane", url: "https://github.com/KaringX/karing/releases/latest",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">Откройте приложение Karing.</div>
                <div class="step-item">Нажмите на значок <b>«+»</b> и выберите <b>«Импорт из буфера обмена»</b>.</div>
                <div class="step-item">Запустите тест задержки.</div>
                <div class="step-item">Выберите лучший сервер и сдвиньте переключатель подключения.</div>
            </div>
        `
    },
    "v2rayng": {
        name: "v2rayNG", icon: "fa-brands fa-android", url: "https://github.com/2dust/v2rayNG/releases/latest",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">В приложении нажмите на <b>«+»</b> (справа сверху) -> <b>«Импорт из буфера обмена»</b>.</div>
                <div class="step-item">Нажмите три точки -> <b>«Проверка профилей группы»</b>.</div>
                <div class="step-item">Снова три точки -> <b>«Сортировка по результатам теста»</b>.</div>
                <div class="step-item">Выберите сервер с зеленым пингом и нажмите кнопку <b>▶️ (Старт)</b>.</div>
            </div>
        `
    },
    "v2raytun": {
        name: "v2RayTun", icon: "fa-solid fa-rocket", url: "https://v2raytun.com/",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">Откройте v2RayTun и перейдите в раздел управления серверами.</div>
                <div class="step-item">Нажмите иконку <b>добавления</b> -> выберите <b>«Импорт из буфера обмена»</b>.</div>
                <div class="step-item">Обновите подписку, выберите сервер с зеленым пингом и нажмите кнопку старта.</div>
            </div>
        `
    },
    "v2box": {
        name: "V2Box", icon: "fa-brands fa-app-store-ios", url: "https://apps.apple.com/ru/app/v2box-v2ray-client/id6446814690",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку с нашего сайта.</div>
                <div class="step-item">Откройте V2Box, перейдите во вкладку <b>«Config»</b>.</div>
                <div class="step-item">Нажмите на <b>«+»</b> -> <b>«Добавить подписку»</b>.</div>
                <div class="step-item">Вставьте ссылку в поле <code>URL</code>, введите Имя и сохраните.</div>
                <div class="step-item">Дождитесь проверки пинга, выберите сервер и нажмите <b>«Подключиться»</b>.</div>
            </div>
        `
    },
    "shadowrocket": {
        name: "Shadowrocket", icon: "fa-solid fa-rocket", url: "https://apps.apple.com/us/app/shadowrocket/id932747118",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">Откройте Shadowrocket (клиент платный, но стабильный на iOS).</div>
                <div class="step-item">Нажмите <b>«+»</b> в правом верхнем углу, выберите тип <b>«Subscribe»</b>.</div>
                <div class="step-item">Вставьте ссылку в поле URL и сохраните.</div>
                <div class="step-item">Сделайте тест подключения (Connectivity Test), выберите сервер и включите VPN.</div>
            </div>
        `
    },
    "streisand": {
        name: "Streisand", icon: "fa-solid fa-shield-cat", url: "https://apps.apple.com/us/app/streisand/id6450534064",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на маршрут.</div>
                <div class="step-item">Откройте Streisand, нажмите на иконку <b>«+»</b> в правом верхнем углу.</div>
                <div class="step-item">Выберите <b>«Add Subscription»</b>.</div>
                <div class="step-item">Вставьте ссылку в поле <code>URL</code> и сохраните.</div>
                <div class="step-item">Зажмите палец на названии подписки и выберите <b>«Latency Test»</b>.</div>
                <div class="step-item">Выберите лучший узел и нажмите главную кнопку подключения.</div>
            </div>
        `
    },
    "hiddify": {
        name: "Hiddify", icon: "fa-solid fa-shield-halved", url: "https://github.com/hiddify/hiddify-app/releases/latest",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">Откройте приложение Hiddify и нажмите <b>«Новый профиль»</b>.</div>
                <div class="step-item">Выберите <b>«Добавить из буфера обмена»</b>.</div>
                <div class="step-item"><b>Важно:</b> Перейдите в настройки программы и измените "Вариант маршрутизации" на <b>"Индонезия"</b> (или "Россия").</div>
                <div class="step-item">Нажмите огромную круглую кнопку посередине экрана для запуска.</div>
            </div>
        `
    }
};

const PLATFORMS = {
    windows:['throne', 'nekobox', 'v2rayn', 'hiddify', 'karing', 'singbox'],
    android:['v2rayng', 'nekobox', 'v2raytun', 'hiddify', 'karing'],
    androidtv:['v2rayng'],
    ios:['v2box', 'streisand', 'shadowrocket', 'karing', 'v2raytun', 'hiddify'],
    mac:['hiddify', 'throne', 'karing', 'singbox'],
    linux:['throne', 'nekobox', 'hiddify', 'karing']
};

let currentPlatform = 'windows';
let currentAppId = PLATFORMS['windows'][0];

function init() {
    const ua = navigator.userAgent.toLowerCase();
    if (ua.includes("android") && (ua.includes("tv") || window.innerWidth > 1000)) currentPlatform = 'androidtv';
    else if (ua.includes("android")) currentPlatform = 'android';
    else if (ua.includes("iphone") || ua.includes("ipad")) currentPlatform = 'ios';
    else if (ua.includes("macintosh") || ua.includes("mac os")) currentPlatform = 'mac';
    else if (ua.includes("linux")) currentPlatform = 'linux';
    else currentPlatform = 'windows';
    
    currentAppId = PLATFORMS[currentPlatform][0];
    updateUI();
    initScrollSpy();
    initReveal();
    initFunPanel();
}

function switchPlatform(platform) {
    currentPlatform = platform;
    currentAppId = PLATFORMS[platform][0];
    updateUI();
}

function selectApp(appId) {
    currentAppId = appId;
    updateUI();
}

function updateUI() {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    const activeTab = document.getElementById(`tab-${currentPlatform}`);
    if(activeTab) activeTab.classList.add('active');

    const grid = document.getElementById('app-grid');
    grid.innerHTML = '';
    
    PLATFORMS[currentPlatform].forEach(appId => {
        const appInfo = APP_DATABASE[appId];
        const div = document.createElement('div');
        div.className = `app-card ${appId === currentAppId ? 'selected' : ''}`;
        div.onclick = () => selectApp(appId);
        div.innerHTML = `<i class="${appInfo.icon} app-icon"></i><div class="app-name">${appInfo.name}</div>`;
        grid.appendChild(div);
    });

    const currentApp = APP_DATABASE[currentAppId];
    const btn = document.getElementById('download-btn');
    btn.href = currentApp.url;
    document.getElementById('app-name-display').innerText = currentApp.name;
    document.getElementById('instruction-text').innerHTML = currentApp.guide;
}

function initReveal() {
    const reveals = document.querySelectorAll('.reveal');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
            }
        });
    }, { threshold: 0.1 });
    
    reveals.forEach(reveal => observer.observe(reveal));
}

function initScrollSpy() {
    const sections = document.querySelectorAll('section');
    const navBtns = document.querySelectorAll('.nav-btn');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const currentId = entry.target.getAttribute('id');
                navBtns.forEach(btn => {
                    btn.classList.remove('active');
                    if (btn.getAttribute('data-target') === currentId) {
                        btn.classList.add('active');
                    }
                });
            }
        });
    }, { rootMargin: '-40% 0px -60% 0px' });

    sections.forEach(sec => observer.observe(sec));

    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');
            document.getElementById(targetId).scrollIntoView({ behavior: 'smooth' });
        });
    });
}

function openModal(id) { document.getElementById(id).classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }

function acceptRules() {
    closeModal('rules-modal');
    setTimeout(() => openModal('configs-modal'), 300);
}

function copySub(path, name) {
    const fullUrl = BASE_URL + path;
    navigator.clipboard.writeText(fullUrl).then(() => {
        closeModal('configs-modal');
        const toast = document.getElementById('toast');
        document.getElementById('toast-text').innerText = `Спелл-карта [${name}] скопирована!`;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3500);
    });
}

// --- FUN PANEL EFFECTS (TOUHOU EASTER EGGS) ---
function initFunPanel() {
    const btnMist = document.getElementById('btn-mist');
    const btnDanmaku = document.getElementById('btn-danmaku');
    const btnBats = document.getElementById('btn-bats');
    
    const mistLayer = document.getElementById('mist-layer');
    
    let danmakuInterval = null;
    let batsInterval = null;

    btnMist.addEventListener('click', () => {
        btnMist.classList.toggle('active');
        mistLayer.classList.toggle('active');
    });

    btnDanmaku.addEventListener('click', () => {
        if (danmakuInterval) {
            clearInterval(danmakuInterval);
            danmakuInterval = null;
            btnDanmaku.classList.remove('active');
        } else {
            btnDanmaku.classList.add('active');
            danmakuInterval = setInterval(() => {
                const orb = document.createElement('div');
                orb.className = 'danmaku-bullet';
                const size = Math.random() * 12 + 6;
                orb.style.width = size + 'px';
                orb.style.height = size + 'px';
                orb.style.left = Math.random() * 100 + 'vw';
                orb.style.top = '-20px';
                orb.style.color = Math.random() > 0.5 ? '#f472b6' : '#e11d48';
                orb.style.backgroundColor = 'currentColor';
                orb.style.animationDuration = (Math.random() * 3 + 2) + 's';
                document.body.appendChild(orb);
                setTimeout(() => orb.remove(), 6000);
            }, 150);
        }
    });

    btnBats.addEventListener('click', () => {
        if (batsInterval) {
            clearInterval(batsInterval);
            batsInterval = null;
            btnBats.classList.remove('active');
        } else {
            btnBats.classList.add('active');
            batsInterval = setInterval(() => {
                const bat = document.createElement('div');
                bat.className = 'bat-spirit';
                bat.innerHTML = '<i class="fa-solid fa-ghost"></i>';
                bat.style.color = Math.random() > 0.5 ? '#8b5cf6' : '#e11d48';
                bat.style.left = '-50px';
                bat.style.top = (Math.random() * 80 + 10) + 'vh';
                bat.style.setProperty('--y-end', (Math.random() * 200 - 100) + 'px');
                bat.style.animationDuration = (Math.random() * 4 + 4) + 's';
                document.body.appendChild(bat);
                setTimeout(() => bat.remove(), 9000);
            }, 800);
        }
    });
}

init();
