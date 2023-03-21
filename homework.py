import logging
import os
import requests
import telegram
import time

from http import HTTPStatus
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

CONNECTION_SUCSESS_PHRASE = 'Соединилсись с API, {response}'
CONNECTION_ERROR_PHRASE = 'Ошибка ресурса, {error}.'
ERROR_PHRASE = 'Сбой в работе программы: {error}'
PARAMS_PHRASE = 'Параметры запроса: {endpoint}, {headers}, {timestamp}'
SAND_MESSAGE_ERROR = 'Сообщение {message} не отправлено, ошибка: {error}'
SAND_MESSAGE_SUCSESS = 'Сообщение отправлено: {message}'
STATUS_PHRASE = 'Статус {status} неизвестен'
STATUS_PHRASE_VERDICT = 'Изменился статус проверки работы "{name}". {verdict}'
TOKEN_ERROR_MESSAGE = 'Нет токена {token}'
TYPE_ERROR_PHRASE = 'Неверный тип входящих данных, не словарь, тип: {types}'


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s, %(lineno)d',
    filename=f'{__file__}.log',
    filemode='w',
)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверка переменных окружения программы."""
    for token in TOKENS:
        check = 0
        if globals()[token] is None:
            check = check + 1
            logger.critical(f'{token} отсутствует')
            raise AttributeError(TOKEN_ERROR_MESSAGE.format(token=token))
        if check > 0:
            raise GeneratorExit('Отсутствие токена, бот выключен')


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SAND_MESSAGE_SUCSESS.format(message=message))
    except TelegramError as error:
        logger.exception(
            SAND_MESSAGE_ERROR.format(message=message, error=error))


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp},
        )
    except requests.RequestException as error:
        phrase = PARAMS_PHRASE.format(
            endpoint=ENDPOINT, headers=HEADERS, timestamp=timestamp)
        raise ConnectionError(CONNECTION_ERROR_PHRASE.format(error=error),
                              f'{phrase}')
    if response.status_code != HTTPStatus.OK:
        phrase = PARAMS_PHRASE.format(
            endpoint=ENDPOINT, headers=HEADERS, timestamp=timestamp)
        raise ConnectionResetError(f'Разрыв соединения. {phrase}')
    logger.debug(CONNECTION_SUCSESS_PHRASE.format(response=response))
    return response.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not response:
        raise Exception('Пустой ответ API')
    if not isinstance(response, dict):
        raise TypeError(TYPE_ERROR_PHRASE.format(types=type(response)))
    if 'homeworks' not in response:
        raise KeyError('Неверный ключ обращения к домашней работе')
    homework = response['homeworks']
    if not isinstance(homework, list):
        raise TypeError(TYPE_ERROR_PHRASE.format(types=type(homework)))
    return homework


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует необходимый ключ "homework_name"')
    if 'status' not in homework:
        raise KeyError('Отсутствует необходимый ключ "status"')
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(STATUS_PHRASE.format(status=status))
    verdict = HOMEWORK_VERDICTS[status]
    return STATUS_PHRASE_VERDICT.format(name=name, verdict=verdict)


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Поехали проверять домашку!')
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                send_message(bot, parse_status(homeworks[0]))
        except Exception as error:
            logger.error(ERROR_PHRASE.format(error=error))
        finally:
            time.sleep(RETRY_PERIOD)
            timestamp = response.get('current_date', timestamp)


if __name__ == '__main__':
    main()
