// Мы не используем импорт { next }, чтобы избежать ошибок компиляции в статику
export default function middleware(req) {
  const url = new URL(req.url);
  const userAgent = req.headers.get('user-agent') || '';
  const accept = req.headers.get('accept') || '';

  // Твоя проверенная логика определения браузера
  const isBrowser = accept.includes('text/html') && 
                    userAgent.includes('Mozilla') && 
                    !userAgent.includes('v2rayNG') && 
                    !userAgent.includes('NekoBox') &&
                    !userAgent.includes('Hiddify');

  if (isBrowser) {
    // Если это браузер — ничего не делаем, Vercel просто покажет index.html
    return;
  }

  // Если это приложение (или прямой запрос не из браузера)
  // Мы делаем "rewrite" — подменяем контент главной страницы контентом файла подписки
  url.pathname = '/subscription.txt';
  
  // Статичный метод rewrite доступен в Edge Runtime Vercel автоматически
  return Response.rewrite(url);
}

// Настройка: обрабатывать только запросы к главной странице
export const config = {
  matcher: '/',
};
