import logging
import os
import time
import requests
import telegram
import exceptions


from http import HTTPStatus
from logging import StreamHandler
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler()
logger.addHandler(handler)


formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)

handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug('Попытка отправки сообщения в telegram')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Отправка сообщения в telegram')
    except telegram.error.TelegramError as error:
        logging.error(f'Не удалось отправить сообщение в telegram: {error}')
        raise Exception(error)


def get_api_answer(current_timestamp):
    """Получить статус домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params_request = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        logging.info(
            'Начало запроса: url = {url},'
            'headers = {headers},'
            'params = {params}'.format(**params_request))
        homework_statuses = requests.get(**params_request)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.InvalidResponseCode(
                'Не удалось получить ответ API, '
                f'ошибка: {homework_statuses.status_code}'
                f'причина: {homework_statuses.reason}'
                f'текст: {homework_statuses.text}')
        return homework_statuses.json()
    except Exception:
        raise exceptions.ConnectinError(
            'Не верный код ответа параметры запроса: url = {url},'
            'headers = {headers},'
            'params = {params}'.format(**params_request))


def check_response(response):
    """Проверить валидность ответа."""
    if not isinstance(response, dict):
        raise TypeError('Ошибка в типе ответа API')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа homeworks')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Homeworks не является списком')
    return homeworks[0]


def parse_status(homework):
    """Распарсить ответ."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе отсутсвует ключ homework_name')
    if 'status' not in homework:
        raise KeyError('В ответе отсутсвует ключ status')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception(f'Неизвестный статус работы - {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        logger.critical("Отсутствие обязательных переменных окружения!")
        return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 1630000000
    STATUS = ''
    if not check_tokens():
        logger.critical = ('Отсутсвуют переменные окружения')
        raise Exception('Отсутсвуют переменные окружения')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            new_status = parse_status(check_response(response))
            if new_status != STATUS:
                send_message(bot, new_status)
                if STATUS != '':
                    current_timestamp = int(time.time())
                STATUS = new_status
            else:
                logger.debug('Статус не поменялся')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
