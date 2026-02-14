export default async function middleware(req) {
  const url = new URL(req.url);
  const userAgent = req.headers.get('user-agent') || '';
  const accept = req.headers.get('accept') || '';

  // Твоя логика определения браузера
  const isBrowser = accept.includes('text/html') && 
                    userAgent.includes('Mozilla') && 
                    !userAgent.includes('v2rayNG') && 
                    !userAgent.includes('NekoBox') &&
                    !userAgent.includes('Hiddify') &&
                    !userAgent.includes('Sing-box');

  if (isBrowser) {
    // Если это браузер — просто продолжаем (Vercel покажет index.html)
    return;
  }

  // Если это VPN клиент — напрямую запрашиваем файл и отдаем текст
  try {
    // Формируем абсолютный URL к файлу внутри твоего же проекта
    const subFileUrl = new URL('/subscription.txt', req.url);
    const response = await fetch(subFileUrl);

    if (!response.ok) {
      return new Response('Subscription file not found', { status: 404 });
    }

    const data = await response.text();

    // Возвращаем чистый текст подписки
    return new Response(data, {
      status: 200,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store, no-cache, must-revalidate',
        'Access-Control-Allow-Origin': '*'
      }
    });
  } catch (e) {
    // В случае ошибки выводим её текст (поможет при отладке)
    return new Response('Internal Error: ' + e.message, { status: 500 });
  }
}

// Конфигурация middleware
export const config = {
  matcher: '/',
};
