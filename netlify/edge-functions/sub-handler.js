export default async (request, context) => {
  const userAgent = request.headers.get("user-agent") || "";
  const accept = request.headers.get("accept") || "";

  // ВАША ЛОГИКА:
  // Если это браузер (есть text/html и Mozilla) -> показываем сайт.
  // За исключением случаев, когда это v2rayNG или NekoBox (они тоже могут слать Mozilla).
  const isBrowser = accept.includes("text/html") && 
                    userAgent.includes("Mozilla") && 
                    !userAgent.includes("v2rayNG") && 
                    !userAgent.includes("NekoBox");

  if (isBrowser) {
    // Просто продолжаем выполнение — Netlify покажет index.html из корня
    return;
  }

  // Если это НЕ браузер (VPN клиент) -> отдаем файл подписки
  try {
    // Подгружаем содержимое файла subscription.txt, который лежит рядом в репо
    const url = new URL("/subscription.txt", request.url);
    const response = await fetch(url);
    const data = await response.text();

    return new Response(data, {
      headers: {
        "content-type": "text/plain; charset=utf-8",
        "cache-control": "no-store",
        "access-control-allow-origin": "*",
      },
    });
  } catch (e) {
    return new Response("Error fetching subscription", { status: 500 });
  }
};

// Настраиваем, чтобы функция срабатывала на главной странице
export const config = { path: "/" };
