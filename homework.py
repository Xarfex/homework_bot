from http import HTTPStatus
import logging
import os
import requests
import sys
import telegram
from telegram import TelegramError
import time

from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('YP_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('MY_TG_CHAT_ID')
LOGS_PATH_FILE = os.path.expanduser(__file__)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_TOKEN']
#  STATUS_PHRASE = f'Изменился статус проверки работы "{key_1}". {key_2}'

logger = logging.getLogger(__name__)
fh = logging.FileHandler(f'{LOGS_PATH_FILE}' + '.log')
fh.setLevel(logging.DEBUG)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(lineno)d')
handler.setFormatter(formatter)
fh.setFormatter(formatter)
logger.addHandler(fh)


def check_tokens():
    """Проверка переменных окружения программы."""
    for token in TOKENS:
        if globals()[token] is None:
            logger.critical(f'{token} отсутствует')
            raise AttributeError(f'Нет токена {token}')
    return True


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено: {message}')
    except TelegramError as error:
        logger.exception(f'Сообщение {message} не отправлено, ошибка: {error}')


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp},
        )
    except requests.RequestException as error:
        raise ConnectionError(f'Ошибка ресурса, {error}: {response}')
    if response.status_code != HTTPStatus.OK:
        raise ConnectionError(response.status_code)
    logger.debug(f'Соединилсись с API, {response}')
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not response:
        raise Exception('Пустой ответ API')
    if not isinstance(response, dict):
        object_type = type(response)
        raise TypeError(
            f'Неверный тип входящих данных, не словарь, тип: {object_type}')
    if 'homeworks' not in response:
        raise NameError('Неверный запрос к API')
    hw = response['homeworks']
    if not isinstance(hw, list):
        object_type = type(hw)
        raise TypeError(
            f'Неверный тип входящих данных, не список, тип: {object_type}')
    return hw


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if 'homework_name' not in homework or 'status' not in homework:
        raise KeyError(f'Отсутствуют необходимые статусы в {homework}')
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise Exception(f'Статус {status} неизвестен')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Нет токенов для работы программы')
        raise KeyboardInterrupt('Отсутствие токена, бот выключен')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Поехали проверять домашку!')
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.info('Нет обновления статуса домашней работы')
            else:
                logger.info(
                    'Отправляется сообщение со статусом домашней работы')
                send_message(bot, parse_status(homeworks[0]))
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
