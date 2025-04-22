import datetime

from dateutil.relativedelta import relativedelta

from app.admin.core.stats.global_tasks_stats import GlobalTasksStatistics
from app.celery_admin.workers.config import celery_app
from app.messages.core.email.extended_mail import RegularMail
from lib.dates import start_of_day
from settings import GLOBAL_STATISTICS_MAIL


@celery_app.task(
    soft_time_limit=15 * 60,
    rate_limit='1/m',
    bind=True
)
def calculate_global_tasks_statistics(self, instantly_send_message=False):
    date = start_of_day(datetime.datetime.now() - relativedelta(days=1))
    _global_tasks_statistics_by_date(date, instantly_send_message)
    return 'success'


@celery_app.task(
    soft_time_limit=15 * 60,
    rate_limit='1/m',
    bind=True
)
def preliminary_global_tasks_statistics(self, instantly_send_message=False):
    date = start_of_day(datetime.datetime.now())
    _global_tasks_statistics_by_date(date, instantly_send_message)
    return 'success'


def _global_tasks_statistics_by_date(date, instantly_send_message=False):
    stats = GlobalTasksStatistics(date)
    stats.fill_all_stats()
    if instantly_send_message:
        send_global_tasks_statistics_message(date)
    else:
        send_global_tasks_statistics_message.delay(date)


@celery_app.task(
    soft_time_limit=60,
    rate_limit='1/m',
    bind=True
)
def send_global_tasks_statistics_message(self, date):
    stats = GlobalTasksStatistics(date)
    stats.load_stats()
    message = _get_global_tasks_statistics_message(stats.stats)
    mail = RegularMail(
        _from='great_white_shark@roscluster.ru',
        to='GLOBAL_STATISTICS_MAIL',
        subject='Статистика задач',
        body=message,
        addresses=GLOBAL_STATISTICS_MAIL,
        instantly=True,
    )
    mail.send()
    return 'success'


_STATISTICS_TITLES = {
    'autopay': "Автоплатежей списано",
    'registry': "Реестров всего обработано",
    'registry_mail': "Реестров получено по почте",
    'registry_mail_error': "Реестров с почты с ошибкой",
    'bank_statement': "Выписок банка обработано всего",
    'bank_statement_mail': "Выписок банка получено по почте",
    'fiscal': "Чеков создано",
    'fiscal_success': "Чеков фискализировано",
    'fiscal_finished': "Чеков обработано окончательно",
    'fiscal_exp': "Чеков помечено просроченными",
    'bill_notify': "Уведомлено о квитанции по email",
}


def _get_global_tasks_statistics_message(stats):
    day_str = stats.date.strftime('%d.%m.%Y')
    if stats.date >= start_of_day(datetime.datetime.now()):
        result = f"Предварительная статистика задач за день {day_str}"
    else:
        result = f"Статистика задач за день {day_str}"
    result += '<br>\n<br>\n'
    result += '<br>\n'.join(
        [
            f'{title}: {stats[field_name]}'
            for field_name, title in _STATISTICS_TITLES.items()
        ]
    )
    return result
