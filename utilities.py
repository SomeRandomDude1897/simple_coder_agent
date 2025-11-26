import requests
import json
import os


def get_bybit_kline_string(
    symbol: str, interval: str, start_ts: int, end_ts: int, category: str = "linear"
) -> str:
    """
    Получает исторические котировки с Bybit и возвращает отформатированный строковый отчет.
    Включает High, Low и Current (Close) цену для каждого временного интервала.
    """
    import urllib.request
    import urllib.parse
    import json
    import ssl
    from datetime import datetime

    try:
        # Базовый URL API Bybit V5
        base_url = "https://api.bybit.com"
        endpoint = "/v5/market/kline"

        params = {
            "category": category,
            "symbol": symbol,
            "interval": interval,
            "start": start_ts,
            "end": end_ts,
            "limit": 1000,
        }

        query_string = urllib.parse.urlencode(params)
        full_url = f"{base_url}{endpoint}?{query_string}"

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})

        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            if response.status == 200:
                raw_data = response.read().decode("utf-8")
                json_data = json.loads(raw_data)

                # Проверка на ошибки API
                if json_data.get("retCode") != 0:
                    return f"Ошибка API Bybit: {json_data.get('retMsg')}"

                # Извлекаем список свечей
                # Структура свечи: [timestamp, open, high, low, close, volume, turnover]
                kline_list = json_data.get("result", {}).get("list", [])

                if not kline_list:
                    return f"Нет данных для пары {symbol} за указанный период."

                # Формируем заголовок отчета
                report_lines = [f"=== ОТЧЕТ ПО ВАЛЮТНОЙ ПАРЕ: {symbol} ==="]
                report_lines.append(f"Интервал: {interval}, Категория: {category}")
                report_lines.append("-" * 50)

                # Bybit возвращает данные от новых к старым.
                # Для отчета развернем список, чтобы время шло хронологически (reversed).
                for candle in reversed(kline_list):
                    ts_ms = int(candle[0])
                    high_price = float(candle[2])
                    low_price = float(candle[3])
                    current_price = float(
                        candle[4]
                    )  # Close цена считается "текущей" для закрытой свечи

                    # Конвертация времени
                    dt_obj = datetime.fromtimestamp(ts_ms / 1000)
                    time_str = dt_obj.strftime("%Y-%m-%d %H:%M:%S")

                    # Формируем строку
                    line = (
                        f"Время: {time_str} | "
                        f"High: {high_price:<10} | "
                        f"Low: {low_price:<10} | "
                        f"Current: {current_price}"
                    )
                    report_lines.append(line)

                return "\n".join(report_lines)
            else:
                return f"Ошибка HTTP запроса. Статус: {response.status}"

    except Exception as e:
        return f"Критическая ошибка выполнения функции: {str(e)}"


def ask_openrouter_llm(user_prompt="", system=""):
    # First API call with reasoning

    open_router_api_key = os.getenv("OPENROUTER_API_KEY")

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {open_router_api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": "x-ai/grok-4.1-fast:free",
                "messages": [
                    {
                        "role": "user",
                        "content": system + "\n" + user_prompt[0],
                    },
                ],
                "extra_body": {"reasoning": {"enabled": False}},
            }
        ),
    )

    # Extract the assistant message with reasoning_details
    response = response.json()
    print(response)
    print(":)")
    return response["choices"][0]["message"]["content"]
