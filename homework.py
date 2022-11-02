import os

import logging
import sys
import time

import requests

import telegram

from dotenv import load_dotenv

from errors import (
    UnexpectedStatusCodeError,
    ExpectedKeysNotFoundError,
    UnexpectedStatusError,
    NewStatusNotFoundError,
    TokenNotFoundError,
)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setLevel(logging.DEBUG)
STRFMT = "[%(asctime)s] [%(name)s] [%(levelname)s] > %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"
logger.addHandler(handler)
formatter = logging.Formatter(fmt=STRFMT, datefmt=DATEFMT)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_TIME = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_STATUSES = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат, определяемый переменной
    окружения TELEGRAM_CHAT_ID. Принимает на вход два параметра:
    экземпляр класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info("Сообщение успешно отправлено в Telegram: %s", message)
    except Exception:
        logger.exception("Сбой в отправке сообщения!", exc_info=True)


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {"from_date": timestamp}
    response = requests.get(
        ENDPOINT,
        headers=HEADERS,
        params=params,
        timeout=30,
    )
    if response.status_code != 200:
        logger.error(
            "Не удалось соединиться с сервером. Код ответа: %s", response.status_code
        )
        raise UnexpectedStatusCodeError
    if not response:
        logger.error("Сервер не отвечает на запросы к эндпоинту.")
        raise ConnectionError

    return response.json()


def check_response(response):
    """Проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python. Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ (он может быть и пустым),
    доступный в ответе API по ключу 'homeworks'.
    """
    expected_keys = {"current_date", "homeworks"}

    if not isinstance(response, dict):
        logger.error("Ответ сервер не является словарем.")
        raise TypeError

    if not expected_keys.issubset(set(response.keys())):
        logger.error("Ответ не содержит ожидаемых ключей.")
        raise ExpectedKeysNotFoundError

    homeworks = response.get("homeworks")

    if not isinstance(homeworks, list):
        logger.error("homeworks не является списком.")
        raise TypeError

    if not homeworks:
        logger.debug("Новых статусов нет.")
        raise NewStatusNotFoundError

    return homeworks


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает
    только один элемент из списка домашних работ.
    В случае успеха, функция возвращает подготовленную для отправки
    в Telegram строку, содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    homework_name = homework.get("homework_name")
    homework_status = homework.get("status")
    if not homework_name:
        logger.error("Имя работы не обнаружено.")
        raise KeyError
    if homework_status not in HOMEWORK_STATUSES:
        logger.error("Обнаружен недокументированный статус.")
        raise UnexpectedStatusError

    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения,
    которые необходимы для работы программы.
    """
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        token_dict = {
            "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
            "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
            "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
        }
        for key, value in token_dict.items():
            if not value:
                logger.critical(
                    "Выполнение команды приостановлено. "
                    "Отсутствует обязательная переменная окружения: %s",
                    key,
                )
                raise TokenNotFoundError()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = []
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            homework = homeworks[0]

        except NewStatusNotFoundError:
            pass
        except Exception as error:
            message = f"Сбой в работе программы: {repr(error)}"
            if message not in last_message:
                last_message.clear()
                last_message.append(message)
                send_message(bot, message)
        else:
            message = parse_status(homework)
            send_message(bot, message)
        finally:
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)


if __name__ == "__main__":
    main()
