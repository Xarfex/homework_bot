from http import HTTPStatus
import logging
import os
import time

from dotenv import load_dotenv
from telegram import TelegramError
import requests
import telegram

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

API_ANSWER = 'Пустой ответ API'
CONNECTION = 'Соединилсись с API, {response}'
CONNECTION_ERROR = ('Ошибка ресурса, {error}.'
                    'Параметры запроса: {endpoint}, {headers}, {params}'
                    )
CONNECTION_WRONG_CODE = ('API вернул код, отличный от 200.'
                         'Код возврата: {code}.'
                         'Параметры запроса: {endpoint}, {headers}, {params}')
ERROR = 'Сбой в работе программы: {error}'
FIRST_MESSAGE = 'Поехали проверять домашку!'
JSON_ERROR = ('Ошибка декодирования {error}.'
              'Параметры запроса: {endpoint}, {headers}, {params}')
KEY_ERROR = 'Отсутствует необходимый ключ {key}.'
KEY_API = 'Нет ожидаемого ключа {key} в ответе API.'
RESPONSE_JSON_ERROR = ('Отсутствует необходимый ключ {key}.'
                       'Значение из JSON: {value}.'
                       'Параметры запроса: {endpoint}, {headers}, {params}')
SEND_MESSAGE_ERROR = 'Сообщение {message} не отправлено, ошибка: {error}'
SEND_MESSAGE_SUCCESS = 'Сообщение отправлено: {message}'
STATUS = 'Статус {status} неизвестен'
STATUS_VERDICT = 'Изменился статус проверки работы "{name}". {verdict}'
TOKEN_ERROR_MESSAGE = 'Нет токена {token}'
TOKEN_IS_ABSENT = '{token} отсутствует'
TYPE_DICTIONARY_ERROR = ('Неверный тип входящих данных,'
                         'не словарь, тип: {types}')
TYPE_LIST_ERROR = 'Неверный тип входящих данных, не список, тип: {types}'

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка переменных окружения программы."""
    empty_tokens = [
        token for token in TOKENS if globals()[token] is None
    ]
    if empty_tokens:
        logger.critical(TOKEN_IS_ABSENT.format(token=empty_tokens))
        raise MemoryError(TOKEN_ERROR_MESSAGE.format(token=empty_tokens))


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SEND_MESSAGE_SUCCESS.format(message=message))
        return True
    except TelegramError as error:
        logger.exception(
            SEND_MESSAGE_ERROR.format(message=message, error=error))
        return False


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    request = dict(
        url=ENDPOINT, headers=HEADERS, params=params)
    try:
        response = requests.get(
            **request
        )
    except requests.RequestException as error:
        raise ConnectionError(CONNECTION_ERROR.format(
            error=error,
            **request,
        ))
    if response.status_code != HTTPStatus.OK:
        raise ValueError(CONNECTION_WRONG_CODE.format(
            code=response.status_code,
            **request,
        ))
    response_json = response.json()
    for key in ['error', 'code']:
        if key in response_json:
            raise ValueError(RESPONSE_JSON_ERROR.format(
                key=key,
                value=response_json.get(key),
                **request,))
    return response_json


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(TYPE_DICTIONARY_ERROR.format(types=type(response)))
    if 'homeworks' not in response:
        raise KeyError(KEY_API.format(key='homeworks'))
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(TYPE_LIST_ERROR.format(types=type(homeworks)))
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(KEY_ERROR.format(key='homework_name'))
    if 'status' not in homework:
        raise KeyError(KEY_ERROR.format(key='status'))
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS.format(status=status))
    return STATUS_VERDICT.format(
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
                if send_message(bot, parse_status(homeworks[0])):
                    timestamp = response.get('current_date', timestamp)
        except Exception as error:
            send_message(bot, ERROR.format(error=error))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    formatter = '%(lineno)d, %(asctime)s, %(levelname)s, %(message)s'
    logging.basicConfig(
        level=logging.DEBUG,
        format=formatter,
        filename=f'{__file__}.log',
        filemode='w',
    )
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(formatter))
    logging.getLogger('').addHandler(console)
    main()
