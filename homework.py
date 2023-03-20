import os
import requests
import logging
import time
import telegram

from dotenv import load_dotenv
from http import HTTPStatus
from telegram import TelegramError

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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


def check_tokens():
    """Проверка переменных окружения программы."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    }
    for token, value in tokens.items():
        if value is None:
            logging.error(f'{token} отсутствует')
    return all(tokens.values())


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение отправлено: {message}')
    except TelegramError as error:
        logging.error(f'Сообщение не отправлено, ошибка: {error}')


def get_api_answer(timestamp):
    """Запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp},
        )
        if response.status_code != HTTPStatus.OK:
            logging.error(
                f'Ошибка ресурса, {response.status_code}'
            )
            raise Exception(response.status_code)
        return response.json()
    except Exception as error:
        logging.error(f'Ошибка ресурса, {error}')
        raise SystemError(f'Ошибка ресурса, {error}')


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if not response:
        logging.error('Пустой ответ API')
        raise Exception('Пустой ответ API')
    elif not isinstance(response, dict):
        raise TypeError('Неверный тип входящих данных, не словарь')
    elif 'homeworks' not in response:
        logging.error('Неверный запрос к API')
        raise KeyError('Неверный запрос к API')
    elif 'current_date' not in response:
        logging.error('Неверный запрос к по дате API')
        raise KeyError('Неверный запрос по дате к API')
    elif not isinstance(response['homeworks'], list):
        raise TypeError('Неверный тип данных, не список')
    return response['homeworks']


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if 'homework_name' not in homework or 'status' not in homework:
        raise KeyError('Отсутствует')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS or None:
        raise Exception('Статус неизвестен')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Нет токенов для работы программы')
        raise SystemExit('Критическая ошибка, бот выключен')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    send_message(bot, 'Поехали проверять домашку!')
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                send_message(bot, 'Нет домашних работ')
            else:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
            timestamp = int(time.time())
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
