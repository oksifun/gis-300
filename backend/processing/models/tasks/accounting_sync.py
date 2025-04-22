from datetime import datetime

from mongoengine import Document, ObjectIdField, StringField, DateTimeField, \
    BooleanField, DynamicField, ListField, DictField, IntField

from lib.helpfull_tools import DateHelpFulls as dhf
from processing.models.tasks.base import TaskMixin


class AccountingSyncTask(Document):
    """
    Модель задачи на синхронизацию данных изменения лицевого счета
    """
    meta = {
        "db_alias": "queue-db"
    }

    # Организация
    provider = ObjectIdField()
    # Название коллекции в которой произошли изменения
    object_collection = StringField(verbose_name="Коллекция объекта")
    # ID объекта в котором произошли изменения
    object_id = ObjectIdField(verbose_name="ID объекта")


class AccountingDailyBalanceControl(Document):
    """
    Контроль задач по ежедневному получению Сальдо из 1С
    по договорам организаций
    """
    meta = {
        "db_alias": "queue-db",
        'collection': 'AccountingDailyBalanceControl',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '-created_at',
        ],
    }
    contract = ObjectIdField(verbose_name='ID документа')
    client = ObjectIdField(verbose_name='Организация клиент')
    owner = ObjectIdField(verbose_name='Организация')
    number = StringField(verbose_name="Номер договора")
    date_on = DateTimeField(verbose_name="На дату")
    state = StringField(
        choices=('wip', 'ready', 'failed'),
        verbose_name="Состояние задачи"
    )
    description = StringField(verbose_name="Описание ошибки или др.")
    created_at = DateTimeField(
        default=lambda: dhf.start_of_day(datetime.now()),
        verbose_name="Дата создания записи"
    )
    params = DictField(verbose_name='JSON, который ушел в запросе к 1С')


class AccountingNomenclatureSendControl(Document):
    """
    Контроль задач отсылки справочника услуг в 1C
    """
    meta = {
        "db_alias": "queue-db",
        'collection': 'AccountingNomenclatureSendControl',
    }
    owner = ObjectIdField(verbose_name='ID организации хозяина')
    service = ObjectIdField(verbose_name='Услуга')
    name = StringField(verbose_name='Организация')
    state = StringField(
        choices=('wip', 'ready', 'failed'),
        verbose_name="Состояние задачи"
    )
    description = StringField(verbose_name="Описание ошибки или др.")
    created_at = DateTimeField(
        default=lambda: dhf.start_of_day(datetime.now()),
        verbose_name="Дата создания записи"
    )
    params = DictField(verbose_name='JSON, который ушел в запросе к 1С')


class AccountingIssuingDocumentsControl(Document):
    """
    Контроль задач выставления комплектов документов в 1C
    """
    meta = {
        "db_alias": "queue-db",
        'collection': 'AccountingIssuingDocumentsControl',
    }
    state = StringField(
        choices=('wip', 'ready', 'failed'),
        verbose_name="Состояние задачи"
    )
    contract = ObjectIdField(verbose_name='ID договора')
    owner = ObjectIdField(verbose_name='ID организации хозяина')
    client = ObjectIdField(verbose_name='ID организации клиента')
    date = DateTimeField(verbose_name='Дата с FE')
    period = DateTimeField(verbose_name='Дата с FE')
    email = BooleanField(
        verbose_name='нужно ли отправить комплект документов на e-mail'
    )
    bill = BooleanField(verbose_name='Надо ли сформировать счет')
    certificate = BooleanField(
        verbose_name='Надо ли сформировать акт выполненных работ'
    )
    delivery = BooleanField(verbose_name='Надо ли доставить квитанции')

    description = StringField(verbose_name="Описание ошибки или др.")
    created_at = DateTimeField(
        default=lambda: dhf.start_of_day(datetime.now()),
        verbose_name="Дата создания записи"
    )
    params_1 = DictField(
        verbose_name='JSON, который ушел в первом запросе к 1С'
    )
    params_2 = DictField(
        verbose_name='JSON, который ушел во втором запросе, если он был'
    )
    value = IntField(
        verbose_name='Кол-во выставленных счетов за текущий месяц'
    )
    last_value = IntField(
        verbose_name='Кол-во выставленных счетов за предыдущий месяц'
    )
    services = ListField(DictField(required=False))


class OwnIssuedDocuments(Document):
    """ Модель коллекция для хранения результатов о выставленных документах """

    meta = {
        'db_alias': 'queue-db',
        'collection': 'OwnIssuedDocuments',
    }
    period = DateTimeField(verbose_name='Период выставления')
    owner = ObjectIdField(verbose_name='ID организации поставляющей услуги')
    client = ObjectIdField(verbose_name='ID организации клиента')
    contract = ObjectIdField(verbose_name='ID договора')
    state = StringField(
        verbose_name='Состояние выставления',
        choices=(
            'failed',
            'ready',
            'wip',
        ),
    )
    description = StringField(verbose_name='Описание возникающих ошибок')
    updated = DateTimeField(verbose_name='Дата последнего обновления')
    params = DictField(verbose_name='JSON, который ушел в запросе к 1С')
    value = IntField(
        verbose_name='Кол-во выставленных счетов за текущий месяц'
    )
    last_value = IntField(
        verbose_name='Кол-во выставленных счетов за предыдущий месяц'
    )
    history_log = ListField(DictField(required=False))

    def save(self, *arg, **kwargs):
        self.updated = datetime.now()
        super().save(*arg, **kwargs)


class OwnSentNomenclatures(Document):
    """ Модель коллекция для хранения результатов о высланой номенклатуре """

    meta = {
        'db_alias': 'queue-db',
        'collection': 'OwnSentNomenclatures'
    }
    service = ObjectIdField(verbose_name='ID услуги')
    name = StringField(verbose_name='Имя услуги')
    full_name = StringField(verbose_name='Имя услуги')
    owner = ObjectIdField(verbose_name='ID организации хозяина')
    state = StringField(
        verbose_name='Состояние отсылки',
        choices=(
            'failed',
            'ready',
            'wip',
        ),
    )
    description = StringField(verbose_name='Описание возникающих ошибок')
    updated = DateTimeField(verbose_name='Дата последнего обновления')
    params = DictField(verbose_name='JSON, который ушел в запросе к 1С')

    def save(self, *arg, **kwargs):
        self.updated = datetime.now()
        super().save(*arg, **kwargs)


class ExportAccrualsSummary(Document):
    """
    Лог экспорта суммарных данных по начислениям в 1C
    """
    meta = {
        "db_alias": "queue-db",
        'collection': 'ExportAccrualsSummary',
    }
    state = StringField(
        choices=('wip', 'ready', 'failed', 'no-inn'),
        verbose_name="Состояние задачи"
    )
    documents = ListField(ObjectIdField(), verbose_name='ID документа')
    provider = ObjectIdField(verbose_name='ID организации')
    description = StringField(verbose_name="Описание ошибки или др.")
    updated = DateTimeField(verbose_name='Дата последнего обновления')
    created_at = DateTimeField(
        default=lambda: dhf.start_of_day(datetime.now()),
        verbose_name="Дата создания записи"
    )
    binds = DynamicField(verbose_name='Привязки')
    file = ObjectIdField(
        null=True,
        verbose_name='file_id в GridFS'
    )
    params = DictField(verbose_name='JSON, который ушел в запросе к 1С')

    def save(self, *arg, **kwargs):
        self.updated = datetime.now()
        super().save(*arg, **kwargs)


class ManagersSpy(TaskMixin, Document):
    """ Модель для обслуживания хода сбора статистики работы менеджеров """

    meta = {
        'db_alias': 'queue-db',
        'collection': 'ManagersSpy'
    }


class MailNotifications(TaskMixin, Document):
    """ Модель для обслуживания хода рассылки писем через интерфейс """

    meta = {
        'db_alias': 'queue-db',
        'collection': 'MailNotifications'
    }
    body = StringField(verbose_name="Тело письма")
    subject = StringField(verbose_name="Тема письма")
    attachments = ListField(ObjectIdField(verbose_name="Вложения"))
    to_send = IntField(verbose_name='Писем на отправку')
    sent = IntField(default=0, verbose_name='Всего отправлено')
    total = IntField(verbose_name='Количество адресов найденных в файле')
    log = ListField(
        StringField(),
        default=[],
        verbose_name='Лог отправки писем'
    )