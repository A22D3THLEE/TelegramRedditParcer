import feedparser
import asyncio
import logging
import aiohttp
from aiogram import Bot
import pickle
from datetime import datetime
import pytz
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Конфигурация
TELEGRAM_BOT_TOKEN = "Your Token Bot"
TELEGRAM_CHANNEL_ID = "id channel"

# Удаляем дублирующиеся URL, сохраняя порядок
_feeds = [
    "https://www.reddit.com/r/codeagencyblog/new/.rss",
    "https://www.reddit.com/r/Qwen_AI/new/.rss",
    "https://www.reddit.com/r/machinelearningnews/new/.rss",
    "https://www.reddit.com/r/Python/new/.rss",
    "https://www.reddit.com/r/technology/new/.rss",
    "https://www.reddit.com/r/singularity/new/.rss",
    "https://www.reddit.com/r/artificial/new/.rss",
    "https://www.reddit.com/r/OpenAI/new/.rss",
    "https://www.reddit.com/r/cursor/new/.rss",
    "https://www.reddit.com/r/MistralAI/new/.rss",
    "https://www.reddit.com/r/MistralAI/new/.rss",
    "https://www.reddit.com/r/PromptEngineering/new/.rss",
    "https://www.reddit.com/r/LLMDevs/new/.rss",
    "https://www.reddit.com/r/AI_Agents/new/.rss",
    "https://www.reddit.com/r/productivity/new/.rss",
    "https://www.reddit.com/r/coolguides/new/.rss",
    "https://www.reddit.com/r/GoogleGeminiAI/new/.rss",
    "https://www.reddit.com/r/ChatGPTCoding/new/.rss",
    "https://www.reddit.com/r/perplexity_ai/new/.rss",
    "https://www.reddit.com/r/automation/new/.rss",
    "https://www.reddit.com/r/indiehackers/new/.rss",
    "https://www.reddit.com/r/ChatGPTPromptGenius/new/.rss",
    "https://www.reddit.com/r/AItoolsCatalog/new/.rss",
    "https://www.reddit.com/r/OpenAIDev/new/.rss",
    "https://www.reddit.com/r/salestechniques/new/.rss",
    "https://www.reddit.com/r/microsoft/new/.rss",
    "https://www.reddit.com/r/software/new/.rss",
    "https://www.reddit.com/r/AskScience/new/.rss",
    "https://www.reddit.com/r/EverythingScience/new/.rss",
    "https://www.reddit.com/r/compsci/new/.rss",
    "https://www.reddit.com/r/OutofTheLoop/new/.rss",
    "https://www.reddit.com/r/Windows11/new/.rss",
    "https://www.reddit.com/r/windows/new/.rss",
    "https://www.reddit.com/r/emulation/new/.rss",
    "https://www.reddit.com/r/technews/new/.rss",
    "https://www.reddit.com/r/ChatGPTPro/new/.rss",
    "https://www.reddit.com/r/science/new/.rss",
    "https://www.reddit.com/r/HumanoidBots/new/.rss",
    "https://www.reddit.com/r/ClaudeAI/new/.rss",
    "https://www.reddit.com/r/hackin/new/.rss",
    "https://www.reddit.com/r/hacking/new/.rss",
    "https://www.reddit.com/r/gadgets/new/.rss",
    "https://www.reddit.com/r/lAmA/new/.rss",
    "https://www.reddit.com/r/computertechs/new/.rss",
    #"https://www.reddit.com/r/ChatGPT/new/.rss",
    "https://www.reddit.com/r/LocalLLM/new/.rss",
    "https://www.reddit.com/r/ArtificialInteligence/new/.rss",
    "https://www.reddit.com/r/LocalLLaMA/new/.rss",
    "https://www.reddit.com/r/programming/new/.rss",
    "https://www.reddit.com/r/Futurology/new/.rss",
    "https://www.reddit.com/r/vibecoding/new/.rss",
    "https://www.reddit.com/r/Neuralink/new/.rss",
    "https://www.reddit.com/r/webdev/new/.rss",
    "https://www.reddit.com/r/n8n/new/.rss",
    "https://www.reddit.com/r/n8nPro/new/.rss",
    "https://www.reddit.com/r/grok/new/.rss",
    "https://www.reddit.com/r/Apps/new/.rss",
    "https://www.reddit.com/r/opensource/new/.rss",
]
REDDIT_FEEDS = list(dict.fromkeys(_feeds))

STATE_FILE = "state.pkl"
FETCH_DELAY = 3         # Задержка между обработкой сабреддитов
PARSING_INTERVAL = 240  # Интервал между циклами парсинга
REQUEST_TIMEOUT = 10    # Таймаут запроса
MESSAGE_DELAY = 2       # Задержка между отправкой сообщений
MAX_RETRIES = 3         # Максимальное количество попыток запроса
RETRY_DELAY = 5         # Задержка между попытками

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RSSBot/1.0; +https://t.me/rssreddit)"}

# Инициализация Telegram-бота
bot = Bot(token=TELEGRAM_BOT_TOKEN)

class FeedState:
    """Класс для управления состоянием: последняя временная метка и обработанные ссылки"""
    def __init__(self):
        self.last_timestamp, self.seen_links = self.load_state()

    def load_state(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "rb") as f:
                    state = pickle.load(f)
                    logging.info(f"Загружено состояние: {state}")
                    return state.get("last_timestamp", datetime.now(pytz.UTC)), state.get("seen_links", set())
            except Exception as e:
                logging.error(f"Ошибка загрузки состояния: {e}")
        now = datetime.now(pytz.UTC)
        self.save_state(now, set())
        return now, set()

    def save_state(self, timestamp, seen_links):
        try:
            with open(STATE_FILE, "wb") as f:
                pickle.dump({"last_timestamp": timestamp, "seen_links": seen_links}, f)
            self.last_timestamp = timestamp
            self.seen_links = seen_links
            logging.info(f"Сохранено состояние: timestamp={timestamp}, обработано ссылок: {len(seen_links)}")
        except Exception as e:
            logging.error(f"Ошибка сохранения состояния: {e}")

async def fetch_rss(session, url):
    """Асинхронная загрузка RSS-ленты с повторными попытками"""
    logging.info(f"Загрузка {url}")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT) as response:
                if response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", RETRY_DELAY))
                    logging.warning(f"Ошибка 429 для {url}, попытка {attempt}/{MAX_RETRIES}, ждём {retry_after} секунд")
                    await asyncio.sleep(retry_after)
                    continue
                if response.status != 200:
                    logging.warning(f"Ошибка {response.status} при загрузке {url}, попытка {attempt}/{MAX_RETRIES}")
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                text = await response.text()
                logging.info(f"Успешно загружен {url}")
                return feedparser.parse(text)
        except Exception as e:
            logging.error(f"Ошибка при загрузке {url}, попытка {attempt}/{MAX_RETRIES}: {e}")
            await asyncio.sleep(RETRY_DELAY)
    logging.error(f"Не удалось загрузить {url} после {MAX_RETRIES} попыток")
    return None

async def send_telegram_message(message, show_preview=True):
    """
    Отправка сообщения в Telegram канал.
    Если show_preview=True, включается предпросмотр (disable_web_page_preview=False).
    Если show_preview=False, предпросмотр отключается.
    """
    try:
        await bot.send_message(
            TELEGRAM_CHANNEL_ID,
            message,
            parse_mode="HTML",
            disable_web_page_preview=not show_preview
        )
        logging.info(f"Сообщение отправлено: {message[:50]}...")
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения: {e}")

async def parse_reddit(state):
    """Парсинг Reddit с поочерёдной загрузкой RSS-лент и проверкой на повторную обработку"""
    logging.info("Начало парсинга Reddit")
    current_parsing_time = datetime.now(pytz.UTC)
    last_parsing_time = state.last_timestamp

    async with aiohttp.ClientSession() as session:
        for url in REDDIT_FEEDS:
            feed = await fetch_rss(session, url)
            if feed is None:
                logging.warning(f"Пропуск {url} из-за ошибки загрузки")
                await asyncio.sleep(FETCH_DELAY)
                continue

            new_entries = []
            for entry in feed.entries:
                try:
                    published_parsed = entry.get("published_parsed")
                    if not published_parsed:
                        logging.warning(f"Пропущен пост без даты: {entry.get('title', 'без названия')}")
                        continue
                    entry_time = datetime(*published_parsed[:6], tzinfo=pytz.UTC)
                    # Если время публикации позже последнего парсинга И запись ещё не обработана
                    if entry_time > last_parsing_time:
                        title = entry.get("title")
                        link = entry.get("link")
                        if title and link:
                            # Проверка на повторное сообщение
                            if link in state.seen_links:
                                logging.info(f"Пропуск повторной записи: {title}")
                                continue
                            has_media = bool(entry.get("media_thumbnail") or entry.get("media_content") or entry.get("enclosures"))
                            new_entries.append((entry_time, title, link, has_media))
                        else:
                            logging.warning(f"Пропущен пост без title или link: {entry}")
                except Exception as e:
                    logging.error(f"Ошибка обработки поста: {e}")

            new_entries.sort(key=lambda x: x[0])
            if new_entries:
                logging.info(f"Найдено {len(new_entries)} новых постов в {url}")
                for entry_time, title, link, has_media in new_entries:
                    message = f"<b>{title}</b>\n{link}"
                    await send_telegram_message(message, show_preview=has_media)
                    # Добавляем ссылку в множество обработанных, чтобы избежать повторной отправки
                    state.seen_links.add(link)
                    await asyncio.sleep(MESSAGE_DELAY)
            else:
                logging.info(f"Новых постов в {url} нет")
            await asyncio.sleep(FETCH_DELAY)

    # Обновляем состояние после цикла парсинга
    state.save_state(current_parsing_time, state.seen_links)
    logging.info("Парсинг Reddit завершён")

async def main():
    """Основной цикл работы бота с периодическим парсингом"""
    state = FeedState()
    while True:
        try:
            await parse_reddit(state)
            logging.info(f"Ожидание {PARSING_INTERVAL} секунд до следующего парсинга")
            await asyncio.sleep(PARSING_INTERVAL)
        except Exception as e:
            logging.error(f"Ошибка в главном цикле: {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    logging.info("Запуск бота")
    asyncio.run(main())
