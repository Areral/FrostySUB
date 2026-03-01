const BASE_URL = window.location.origin;

const APP_DATABASE = {
    "throne": {
        name: "Throne", icon: "fa-solid fa-chess-rook", url: "https://github.com/throneproj/Throne/releases",
        guide: `
            <div class="step-list">
                <div class="step-item">Нажмите <b>«Получить доступ»</b> выше и скопируйте ссылку на подписку.</div>
                <div class="step-item">В клиенте нажмите на <b>«Профили»</b> -> <b>«Добавить профиль из буфера обмена»</b>.</div>
                <div class="step-item">Выделите все профили (Ctrl+A), нажмите <b>«Профили»</b> -> <b>«Тест задержки (пинга)»</b>.</div>
                <div class="step-item">Кликните по колонке <b>«Задержка»</b> для сортировки.</div>
                <div class="step-item">Сверху установите галочку <b>«Режим TUN»</b>.</div>
                <div class="step-item">Выберите лучший сервер -> Правая кнопка мыши -> <b>«Запустить»</b>.</div>
            </div>
        `
    },
    "v2rayng": {
        name: "v2rayNG", icon: "fa-solid fa-paper-plane", url: "https://github.com/2dust/v2rayNG/releases",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на конфиг из раздела <b>«Получить доступ»</b>.</div>
                <div class="step-item">В приложении нажмите на <b>«+»</b> (справа сверху) -> <b>«Импорт из буфера обмена»</b>.</div>
                <div class="step-item">Нажмите три точки -> <b>«Проверка профилей группы»</b>. Дождитесь окончания.</div>
                <div class="step-item">Снова три точки -> <b>«Сортировка по результатам теста»</b>.</div>
                <div class="step-item">Выберите сервер и нажмите кнопку <b>▶️ (Старт)</b> в правом нижнем углу.</div>
            </div>
            <details>
                <summary>Возможные проблемы и решения</summary>
                <div class="details-content">
                    <b>Нет интернета при подключении:</b><br>Убедитесь, что в настройках (левое меню) включен режим TUN.<br><br>
                    <b>Ошибка "Fail to detect internet connection":</b>
                    <ol>
                        <li>Зажмите иконку v2rayNG на рабочем столе -> "О приложении".</li>
                        <li>Нажмите "Остановить" и запустите заново.</li>
                        <li>Сделайте проверку профилей (Ping тест) еще раз.</li>
                    </ol>
                </div>
            </details>
        `
    },
    "v2box": {
        name: "V2Box", icon: "fa-solid fa-cube", url: "https://apps.apple.com/ru/app/v2box-v2ray-client/id6446814690",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку с этого сайта.</div>
                <div class="step-item">Откройте V2Box, перейдите во вкладку <b>«Config»</b>.</div>
                <div class="step-item">Нажмите на <b>«+»</b> (в правом верхнем углу) -> <b>«Добавить подписку»</b>.</div>
                <div class="step-item">Вставьте ссылку в поле <code>URL</code> и сохраните.</div>
                <div class="step-item">Дождитесь проверки пинга, выберите сервер (тапнув по нему) и нажмите <b>«Подключиться»</b>.</div>
            </div>
        `
    },
    "v2raytun": {
        name: "v2RayTun", icon: "fa-solid fa-rocket", url: "https://v2raytun.com/",
        guide: `
            <div class="step-list">
                <div class="step-item">Получите ссылку на подписку через кнопку выше.</div>
                <div class="step-item">Откройте v2RayTun и перейдите в раздел управления серверами.</div>
                <div class="step-item">Нажмите иконку <b>добавления</b> -> выберите <b>«Импорт из буфера обмена»</b>.</div>
                <div class="step-item">Обновите подписку, выберите сервер с зеленым пингом и нажмите огромную кнопку старта.</div>
            </div>
        `
    },
    "nekobox": {
        name: "NekoBox", icon: "fa-solid fa-cat", url: "https://github.com/MatsuriDayo/nekoray/releases",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на маршрут (например, Обход БС).</div>
                <div class="step-item">Перейдите в <b>«Настройки»</b> -> <b>«Группы»</b> -> <b>«Новая группа»</b>.</div>
                <div class="step-item">Выберите тип <b>«Подписка»</b> и вставьте вашу ссылку. Нажмите Ок.</div>
                <div class="step-item">Нажмите кнопку <b>«Обновить подписки»</b>.</div>
                <div class="step-item">Включите галочку <b>«Режим TUN»</b> и запустите выбранный сервер.</div>
            </div>
        `
    },
    "hiddify": {
        name: "Hiddify", icon: "fa-solid fa-shield-halved", url: "https://github.com/hiddify/hiddify-app/releases",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">Откройте приложение Hiddify и нажмите <b>«Новый профиль»</b>.</div>
                <div class="step-item">Выберите <b>«Добавить из буфера обмена»</b>.</div>
                <div class="step-item">Нажмите огромную круглую кнопку посередине экрана для запуска VPN.</div>
                <div class="step-item">Во вкладке "Прокси" можно выбрать конкретный сервер с лучшим пингом.</div>
            </div>
        `
    },
    "v2rayn": {
        name: "v2rayN", icon: "fa-solid fa-v", url: "https://github.com/2dust/v2rayN/releases",
        guide: `
            <div class="step-list">
                <div class="step-item">Копируем ссылку на конфиг.</div>
                <div class="step-item">Переходим в <b>«Подписки»</b> -> <b>«Настройки подписки»</b> -> <b>«Добавить»</b>.</div>
                <div class="step-item">Вставляем ссылку в поле <code>Url</code>, сохраняем.</div>
                <div class="step-item">В главном меню нажимаем <b>«Обновить подписку»</b>.</div>
                <div class="step-item">Выделяем сервер и нажимаем <b>Enter</b> для подключения.</div>
            </div>
        `
    }
};

const PLATFORMS = {
    windows:['throne', 'nekobox', 'v2rayn', 'hiddify'],
    android:['v2rayng', 'v2raytun', 'nekobox', 'hiddify'],
    ios:['v2box', 'v2raytun', 'hiddify'],
    linux:['throne', 'nekobox', 'hiddify']
};

let currentPlatform = 'windows';
let currentAppId = PLATFORMS['windows'][0];

function init() {
    const ua = navigator.userAgent.toLowerCase();
    if (ua.includes("android")) currentPlatform = 'android';
    else if (ua.includes("iphone") || ua.includes("ipad") || ua.includes("macintosh")) currentPlatform = 'ios';
    else if (ua.includes("linux")) currentPlatform = 'linux';
    else currentPlatform = 'windows';
    
    currentAppId = PLATFORMS[currentPlatform][0];
    updateUI();
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
        document.getElementById('toast-text').innerText = `${name} скопирован!`;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3000);
    });
}

init();
