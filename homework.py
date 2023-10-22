import logging
import os
import sys
import time
import requests
import telegram

from asyncio import exceptions
from requests.exceptions import RequestException
from json import JSONDecodeError
from http import HTTPStatus
from dotenv import load_dotenv


load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format=(
        "%(asctime)s, %(levelname)s, %(message)s"
    ),
    handlers=[logging.FileHandler("program_log.txt", encoding="UTF-8"),
              logging.StreamHandler(sys.stdout)]
)


def check_tokens():
    """Проверка токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN])


def send_message(bot, message):
    """Отправка сообщения."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logging.debug("Удачная отправка сообщения в Telegram.")


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {"from_date": timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code != HTTPStatus.OK:
            raise exceptions.ApiConnectError(
                "Ответ от API не получен."
            )
        try:
            data = response.json()
        except JSONDecodeError as json_error:
            raise exceptions.ApiResponseError(f'Ошибка при разборе JSON: '
                                              f'{json_error}')
    except RequestException as error:
        raise exceptions.ApiConnectError(
            f'При обращении к API возникла ошибка: '
            f'{error}')
    return data


def check_response(response):
    """Проверяем данные."""
    if not isinstance(response, dict):
        raise TypeError('Структура данных в ответе API '
                        'не соответствует ожиданиям.')
    if "homeworks" not in response:
        raise KeyError('Данные в ответе API '
                       'под ключом "homeworks" не являются списком.')
    if "current_date" not in response:
        raise KeyError("Такого ключа current_date не существует.")
    if not isinstance(response["homeworks"], list):
        raise TypeError("Неверный тип данных.")
    return response["homeworks"]


def parse_status(homework):
    """Анализируем статус."""
    if not isinstance(homework, dict):
        raise TypeError(f'homework не dict, а {type(homework)}')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" '
                       'в ответе API домашки')
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" '
                       'в ответе API домашки')
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'{homework_status} нет в словаре HOMEWORK_VERDICTS'
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    homework_name = homework['homework_name']
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = "Бот недоступен."
        logging.critical(error_message)
        raise SystemExit(error_message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    new_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if len(homework) != 0:
                if new_status != homework[0]['status']:
                    message = parse_status(homework[0])
                    send_message(bot, message)
                    new_status = homework[0]['status']
        except telegram.error.TelegramError as error:
            error_message = f'Ошибка при отправке сообщения: {error}'
            logging.error(error_message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
