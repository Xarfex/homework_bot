from http import HTTPStatus
import json
import logging
import os
import time

import requests
import telegram
from telegram import TelegramError

from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('YP_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('MY_TG_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_TOKEN']

API_PHRASE = 'Пустой ответ API'
CONNECTION_PHRASE = 'Соединилсись с API, {response}'
CONNECTION_ERROR_PHRASE = ('Ошибка ресурса, {error}.'
                           'Параметры запроса: {endpoint}, {headers}, {params}'
                           )
CONNECTION_WRONG_CODE = ('API вернул код, отличный от 200.'
                         'Параметры запроса: {endpoint}, {headers}, {params}')
ERROR_PHRASE = 'Сбой в работе программы: {error}'
FIRST_MESSAGE = 'Поехали проверять домашку!'
JSON_ERROR = ('Ошибка декодирования {error}.'
              'Параметры запроса: {endpoint}, {headers}, {params}')
KEY_ERROR_PHRASE = 'Отсутствует необходимый ключ {key}'
KEY_API_PHRASE = 'Нет ожидаемого ключа {key} в ответе API.'
SEND_MESSAGE_ERROR = 'Сообщение {message} не отправлено, ошибка: {error}'
SEND_MESSAGE_SUCCESS = 'Сообщение отправлено: {message}'
STATUS_PHRASE = 'Статус {status} неизвестен'
STATUS_PHRASE_VERDICT = 'Изменился статус проверки работы "{name}". {verdict}'
TOKEN_ERROR_MESSAGE = 'Нет токена {token}'
TOKEN_IS_ABSENT = '{token} отсутствует'
TYPE_DICTIONARY_ERROR = ('Неверный тип входящих данных,'
                         'не словарь, тип: {types}')
TYPE_LIST_ERROR = 'Неверный тип входящих данных, не список, тип: {types}'

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка переменных окружения программы."""
    for token in TOKENS:
        check = 0
        tokens = {}
        if globals()[token] is None:
            check = check + 1
            logger.critical(TOKEN_IS_ABSENT.format(token=token))
            tokens = tokens + f'{token}'
        count = -1
        while len(tokens) != check:
            count = count + 1
            raise ImportError(TOKEN_ERROR_MESSAGE.format(token=tokens[count]))
    if check > 0:
        raise SystemExit('Отсутствие токена, бот выключен')


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SEND_MESSAGE_SUCCESS.format(message=message))
    except TelegramError as error:
        logger.exception(
            SEND_MESSAGE_ERROR.format(message=message, error=error))


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp},
        )
    except requests.RequestException as error:
        phrase = CONNECTION_ERROR_PHRASE.format(
            error=error,
            endpoint=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        raise ConnectionError(phrase)
    except json.JSONDecodeError as json_error:
        phrase = CONNECTION_WRONG_CODE.format(
            error=json_error,
            endpoint=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        raise json.JSONDecodeError(phrase)
    if response.status_code != HTTPStatus.OK:
        phrase = CONNECTION_WRONG_CODE.format(
            endpoint=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        raise ConnectionError(phrase)
    logger.debug(CONNECTION_PHRASE.format(response=response))
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not response:
        raise AttributeError(API_PHRASE)
    if not isinstance(response, dict):
        raise TypeError(TYPE_DICTIONARY_ERROR.format(types=type(response)))
    if 'homeworks' not in response:
        raise KeyError(KEY_API_PHRASE.format(key='homeworks'))
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(TYPE_LIST_ERROR.format(types=type(homeworks)))
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(KEY_ERROR_PHRASE.format(key='homework_name'))
    if 'status' not in homework:
        raise KeyError(KEY_ERROR_PHRASE.format(key='status'))
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS_PHRASE.format(status=status))
    return STATUS_PHRASE_VERDICT.format(
        name=homework['homework_name'], verdict=HOMEWORK_VERDICTS[status])


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, FIRST_MESSAGE)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            logger.error(ERROR_PHRASE.format(error=error))
            send_message(bot, ERROR_PHRASE.format(error=error))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(lineno)d, %(asctime)s, %(levelname)s, %(message)s',
        filename=f'{__file__}.log',
        filemode='w',
    )
    main()
