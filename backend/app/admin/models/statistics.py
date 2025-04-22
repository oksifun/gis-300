import datetime

from mongoengine import Document, DateTimeField, IntField


class TasksGlobalStatistics(Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'global_tasks_stats',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '-date',
        ],
    }
    created = DateTimeField(
        verbose_name="Дата создания",
        default=datetime.datetime.now,
    )
    date = DateTimeField(
        required=True,
        verbose_name="Дата статистики - день",
    )

    autopay = IntField(verbose_name="Успешные задачи автоплатежа")
    registry = IntField(verbose_name="Парсинг реестров")
    registry_mail = IntField(
        verbose_name="Парсинг реестров, полученных по почте",
    )
    registry_mail_error = IntField(
        verbose_name="Ошибки парсинга реестров, полученных по почте",
    )
    bank_statement =IntField(verbose_name="Выписка банка")
    bank_statement_mail = IntField(
        verbose_name="Выписка банка, полученная по почте",
    )
    fiscal = IntField(verbose_name="Создано чеков")
    fiscal_success = IntField(verbose_name="Чеков фискализировано")
    fiscal_finished = IntField(verbose_name="Чеков получено")
    fiscal_exp = IntField(verbose_name="Чеков помечено просроченными")
    bill_notify = IntField(verbose_name="Уведомлений о квитанции по email")
