from asyncio import exceptions
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
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
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if all(tokens):
        return True
    else:
        logging.critical("Отсутствие обязательных переменных окружения при "
                         "запуске бота.")
        return False


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug("Удачная отправка сообщения в Telegram.")
    except Exception as error:
        logging.error(f"Сбой при отправке сообщения в Telegram: {error}")


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    params = {"from_date": timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params=params)
        if response.status_code != HTTPStatus.OK:
            logging.error("Ответ от API не получен.")
            raise exceptions.ApiConnectError(
                "Ответ от API не получен."
            )
        logging.info(
            "Ответ от API получен."
        )
    except Exception as error:
        logging.error(f"Неверный код ответа: {error}")
        raise exceptions.ApiConnectError(
            f"При обращени к API возникла ошибка: {error}")
    return response.json()


def check_response(response):
    """Проверяем данные."""
    if not isinstance(response, dict):
        raise TypeError('Структура данных в ответе API '
                        'не соответствует ожиданиям.')
    if 'homeworks' in response:
        if not isinstance(response['homeworks'], list):
            raise TypeError("Данные в ответе API "
                            "под ключом 'homeworks' не являются списком.")
        return response['homeworks']
    else:
        raise AssertionError('Отсутствие ожидаемых ключей в ответе API.')


def parse_status(homework):
    """Анализируем статус."""
    if 'status' in homework and homework['status'] in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework['status']]
        if 'homework_name' in homework:
            return (f'Изменился статус проверки работы '
                    f'"{homework["homework_name"]}". {verdict}')
        else:
            raise ValueError('Отсутствует ключ "homework_name" '
                             'в ответе API домашки')
    else:
        raise ValueError('Недокументированный статус домашней работы '
                         'в ответе API')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit("Бот недоступен.")
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            api_response = get_api_answer(timestamp)
            if api_response:
                homeworks = check_response(api_response)
                if not homeworks:
                    logging.debug("Отсутствие в ответе новых статусов.")
                for homework in homeworks:
                    message = parse_status(homework)
                    if message:
                        send_message(bot, message)
                timestamp = api_response['last_attempt_timestamp']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
