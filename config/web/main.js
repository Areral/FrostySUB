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
            <details>
                <summary><i class="fa-solid fa-triangle-exclamation" style="color:var(--touhou-red)"></i> Ошибка MSVCP / VCRUNTIME на Windows</summary>
                <div class="details-content">
                    <p>Если программа Throne не запускается и требует DLL файлы, сделайте следующее:</p>
                    <ol>
                        <li>Нажмите <b>Win+R</b>, введите <code>control</code>.</li>
                        <li>Откройте <b>«Программы и компоненты»</b>, удалите старые пакеты "Microsoft Visual C++".</li>
                        <li>Скачайте официальный <a href="https://cf.comss.org/download/Visual-C-Runtimes-All-in-One-Dec-2025.zip" target="_blank" style="color:var(--cyber-blue)">пакет Visual C++ Runtimes</a>.</li>
                        <li>Распакуйте архив и запустите <code>install_bat.all</code> <b>от имени администратора</b>.</li>
                        <li>Дождитесь окончания установки и перезапустите Throne.</li>
                    </ol>
                </div>
            </details>
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
    "v2rayng": {
        name: "v2rayNG", icon: "fa-solid fa-paper-plane", url: "https://github.com/2dust/v2rayNG/releases/latest",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">В приложении нажмите на <b>«+»</b> (справа сверху) -> <b>«Импорт из буфера обмена»</b>.</div>
                <div class="step-item">Нажмите три точки -> <b>«Проверка профилей группы»</b>. Дождитесь окончания.</div>
                <div class="step-item">Снова три точки -> <b>«Сортировка по результатам теста»</b>.</div>
                <div class="step-item">Выберите сервер с зеленым пингом и нажмите кнопку <b>▶️ (Старт)</b> в правом нижнем углу.</div>
            </div>
            <details>
                <summary><i class="fa-solid fa-wrench" style="color:var(--cyber-blue)"></i> Решение проблем подключения</summary>
                <div class="details-content">
                    <p><b>Нет интернета при подключении:</b><br>Убедитесь, что в настройках (левое верхнее меню) включен режим TUN.</p>
                    <p><b>Конфиги не появились после добавления:</b><br>Нажмите три полоски (меню) -> «Группы» -> Нажмите иконку обновления (кружок со стрелкой) справа сверху.</p>
                    <p><b>Ошибка "Cбой проверки интернет-соединения: net/http: 12X handshake timeout":</b></p>
                    <ol>
                        <li>Зажмите иконку v2rayNG на рабочем столе -> "О приложении".</li>
                        <li>Нажмите "Остановить".</li>
                        <li>Запустите приложение заново.</li>
                    </ol>
                    <p><b>Ошибка "Fail to detect internet connection: io: read/write closed pipe":</b></p>
                    <ol>
                        <li>Сделайте принудительную остановку приложения (как в шаге выше).</li>
                        <li>Запустите приложение, нажмите "три точки" -> "Проверка профилей группы".</li>
                        <li>Отсортируйте и выберите ДРУГОЙ сервер с низким пингом.</li>
                    </ol>
                </div>
            </details>
        `
    },
    "v2raytun": {
        name: "v2RayTun", icon: "fa-solid fa-rocket", url: "https://v2raytun.com/",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку.</div>
                <div class="step-item">Откройте v2RayTun и перейдите в раздел управления серверами.</div>
                <div class="step-item">Нажмите иконку <b>добавления</b> -> выберите <b>«Импорт из буфера обмена»</b>.</div>
                <div class="step-item">Обновите подписку, выберите сервер с зеленым пингом и нажмите огромную кнопку старта.</div>
            </div>
        `
    },
    "v2box": {
        name: "V2Box", icon: "fa-brands fa-app-store-ios", url: "https://apps.apple.com/ru/app/v2box-v2ray-client/id6446814690",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на подписку с нашего сайта.</div>
                <div class="step-item">Откройте V2Box, перейдите во вкладку <b>«Config»</b>.</div>
                <div class="step-item">Нажмите на <b>«+»</b> (в правом верхнем углу) -> <b>«Добавить подписку»</b>.</div>
                <div class="step-item">Вставьте ссылку в поле <code>URL</code>, введите любое Имя и сохраните.</div>
                <div class="step-item">Дождитесь проверки пинга, выберите сервер (тапнув по нему) и нажмите переключатель <b>«Подключиться»</b> внизу экрана.</div>
            </div>
            <details>
                <summary><i class="fa-solid fa-rotate"></i> Как обновить конфиги?</summary>
                <div class="details-content">
                    Перейдите во вкладку <b>«Config»</b> и нажмите на иконку обновления (круговая стрелка) слева от названия вашей подписки.
                </div>
            </details>
        `
    },
    "streisand": {
        name: "Streisand", icon: "fa-solid fa-shield-cat", url: "https://apps.apple.com/us/app/streisand/id6450534064",
        guide: `
            <div class="step-list">
                <div class="step-item">Скопируйте ссылку на маршрут (БС или ЧС).</div>
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
                <div class="step-item"><b>Важно:</b> Перейдите в настройки программы и измените "Вариант маршрутизации" на <b>"Индонезия"</b> (или "Россия", если доступно).</div>
                <div class="step-item">Нажмите огромную круглую кнопку посередине экрана для запуска VPN.</div>
                <div class="step-item">Для смены сервера (при включенном VPN) перейдите во вкладку <b>«Прокси»</b>.</div>
            </div>
            <details>
                <summary><i class="fa-solid fa-rotate"></i> Как обновить конфиги?</summary>
                <div class="details-content">
                    Зайдите в приложение Hiddify, выберите нужный вам профиль и нажмите <b>слева от названия профиля на иконку обновления</b>.
                </div>
            </details>
        `
    }
};

const PLATFORMS = {
    windows:['throne', 'nekobox', 'v2rayn', 'hiddify'],
    android:['v2rayng', 'v2raytun', 'nekobox', 'hiddify'],
    ios:['streisand', 'v2box', 'v2raytun', 'hiddify'],
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
        document.getElementById('toast-text').innerText = `Спелл-карта [${name}] скопирована!`;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 3500);
    });
}

init();
