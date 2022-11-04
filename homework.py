import os

import logging
import sys
import time

import requests

import telegram

from dotenv import load_dotenv

from exceptions import (
    SendMessageError,
    UnexpectedStatusCodeError,
    ExpectedKeysNotFoundError,
    UnexpectedStatusError,
)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setLevel(logging.DEBUG)
STRFMT = '[%(asctime)s] [%(name)s] [%(levelname)s] > %(message)s'
DATEFMT = '%Y-%m-%d %H:%M:%S'
logger.addHandler(handler)
formatter = logging.Formatter(fmt=STRFMT, datefmt=DATEFMT)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат.
    Принимает на вход два параметра:
    экземпляр класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info("Сообщение успешно отправлено в Telegram: %s", message)
    except Exception as exc:
        raise SendMessageError("Не удалось отправить сообщение.") from exc


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python.
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=30,
        )
        if response.status_code != 200:
            raise UnexpectedStatusCodeError(
                "Не удалось соединиться с сервером."
                f"Код ответа: {response.status_code}"
                f"URL запроса: {ENDPOINT}"
                f"headers: {HEADERS}"
                f"params: {params}"
            )
        json_response = response.json()
    except Exception as exp:
        raise ConnectionError(
            "Ответ от сервера не получен/Формат ответа отличен от JSON "
        ) from exp
    return json_response


def check_response(response):
    """Проверяет ответ API на корректность.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python. Если ответ API соответствует ожиданиям,
    то функция должна вернуть список домашних работ (он может быть и пустым),
    доступный в ответе API по ключу 'homeworks'.
    """
    if not isinstance(response, dict):
        raise TypeError("Ответ сервер не является словарем.")

    if 'current_date' not in response and 'homeworks' not in response:
        raise ExpectedKeysNotFoundError("Ответ не содержит ожидаемых ключей.")

    homeworks = response.get('homeworks')

    if not isinstance(homeworks, list):
        raise TypeError("homeworks не является списком.")

    return homeworks


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В качестве параметра функция получает
    только один элемент из списка домашних работ.
    В случае успеха, функция возвращает подготовленную для отправки
    в Telegram строку, содержащую один из вердиктов словаря HOMEWORK_STATUSES.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name:
        raise KeyError("Имя работы не обнаружено.")
    if homework_status not in HOMEWORK_STATUSES:
        raise UnexpectedStatusError("Обнаружен недокументированный статус.")

    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        token_dict = {
            'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
            'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
            'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
        }
        for key, value in token_dict.items():
            if not value:
                logger.critical(
                    "Отсутствует обязательная переменная окружения: %s", key
                )
        sys.exit(
            "Выполнение команды приостановлено."
            "Отсутствует обязательная переменная окружения."
        )

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_message = ""
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homeworks = check_response(response)
            homework = homeworks[0]
            message = parse_status(homework)
        except IndexError:
            logger.debug("Новых статусов нет.")
            time.sleep(RETRY_TIME)
            continue
        except Exception as exc:
            message = f"Сбой в работе программы: {exc}"
            logger.exception(exc, exc_info=True)

        if last_message != message:
            last_message = message
            try:
                send_message(bot, message)
            except SendMessageError:
                logger.exception("Сбой в отправке сообщения!")
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
