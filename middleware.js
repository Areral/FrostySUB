import { next } from '@vercel/edge';

export default function middleware(req) {
  const url = new URL(req.url);
  const userAgent = req.headers.get('user-agent') || '';
  const accept = req.headers.get('accept') || '';

  // Ваша логика определения
  // Если в Accept есть html и это Mozilla (браузер), и НЕ VPN клиент
  const isBrowser = accept.includes('text/html') && 
                    userAgent.includes('Mozilla') && 
                    !userAgent.includes('v2rayNG') && 
                    !userAgent.includes('NekoBox') &&
                    !userAgent.includes('Hiddify');

  // Если зашел человек через браузер -> разрешаем просмотр index.html
  if (isBrowser) {
    return next();
  }

  // Если это приложение или прямой запрос -> делаем внутренний редирект на файл
  // rewrite не меняет URL в строке браузера/клиента, но отдает контент другого файла
  return new URL('/subscription.txt', req.url);
}

// Настраиваем срабатывание только на главную страницу
export const config = {
  matcher: '/',
};
