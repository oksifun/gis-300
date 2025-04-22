import datetime

from mongoengine import Document, ObjectIdField, DateTimeField, StringField, \
    ListField, EmbeddedDocument, EmbeddedDocumentListField, IntField, DictField, \
    EmbeddedDocumentField, BooleanField

from lib.gridfs import get_file_from_gridfs, put_file_to_gridfs

SbolRegistryOutStatuses = (
    ('new', 'новый'),
    ('started', 'начато выполнение'),
    ('got_url', 'получена ссылка'),
    ('uploaded', 'файл загружен'),
    ('accepted', 'файл принят'),
    ('run', 'проводится'),
    ('finished', 'успешно завершено'),
    ('error', 'завершено с ошибкой'),
)
SbolRegistryInStatuses = (
    ('new', 'новый'),
    ('started', 'начато выполнение'),
    ('got_url', 'получена ссылка'),
    ('ready', 'файл готов к разбору'),
    ('finished', 'успешно завершено'),
    ('error', 'завершено с ошибкой'),
)


class SbolRegistryTaskFile(EmbeddedDocument):
    file_id = ObjectIdField(verbose='Ссылка на файл в GridFS', required=True)
    file_uuid = StringField(verbose='Ссылка на файл в GridFS', required=True)
    file_meta = DictField(verbose_name='Сопутствующие данные о файле')


class SbolInRegistryTask(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'sber_registries_in',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'reg_uuid',
            ('status', 'updated'),
        ],
    }

    # обязательные исходные данные
    created = DateTimeField(verbose_name='Создано', required=True)
    updated = DateTimeField(verbose_name='Изменено', required=True)
    reg_uuid = StringField(verbose_name='ИД реестра в СБОЛ', required=True)
    reg_name = StringField(
        verbose_name='Имя файла файла реестра', required=True
    )
    status = StringField(
        verbose_name='Текущий статус',
        choices=SbolRegistryInStatuses,
        required=True,
    )
    date = DateTimeField(verbose_name='Дата реестра', required=True)
    sum = IntField(verbose_name='Сумма реестра', required=True)
    bank_account = StringField(verbose_name='Расчётный счёт', required=True)
    warnings = ListField(StringField(), verbose_name='Некритичные ошибки')
    parse_tries = IntField(verbose_name='Кол-во попыток разбора')
    known_error = StringField(verbose_name='Известное обработанное исключение')
    error_message = StringField(
        verbose_name='Сообщение об ошибке, если она известна и обработана')

    # данные, которые появляются в процессе выполнения задачи
    provider = ObjectIdField(verbose_name='Организация', default=None)
    reg_file = EmbeddedDocumentField(
        SbolRegistryTaskFile,
        verbose_name='Данные файла реестра',
        default=None
    )
    log = ObjectIdField(
        verbose_name='Текущий лог соединения со СБОЛ',
        default=None
    )
    logs = ListField(
        ObjectIdField(),
        verbose_name='Бывшие (неудавшиеся, незавершённые попытки) логи '
                     'соединения со СБОЛ'
    )

    link_uuid = StringField(verbose_name='ИД ссылки в СБОЛ', default=None)
    link_url = StringField(verbose_name='Ссылка на файл', default=None)

    file = None

    def save_file(self):
        file_id, file_uuid = put_file_to_gridfs(
            resource_name='PaymentDoc',
            resource_id=None,
            file_bytes=self.file['file'],
            filename=self.file.get('filename'),
        )
        self.reg_file = SbolRegistryTaskFile(
            file_id=file_id,
            file_uuid=file_uuid,
        )

    def save(self, *args, **kwargs):
        self.updated = datetime.datetime.now()
        return super().save(*args, **kwargs)

    def prepare_file(self):
        if self.file:
            return
        filename, file = get_file_from_gridfs(self.reg_file.file_id)
        self.file = {
            'filename': filename,
            'file': file,
        }


class SbolOutRegistryTask(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'sber_registries_out',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'accrual_doc_id',
            'provider',
            ('status', 'updated'),
        ],
    }

    # обязательные исходные данные
    provider = ObjectIdField(verbose_name='Организация', required=True)
    created = DateTimeField(verbose_name='Создано', required=True)
    updated = DateTimeField(verbose_name='Изменено', required=True)
    accrual_doc_id = ObjectIdField(
        verbose_name='Документ начислений',
        required=True
    )
    status = StringField(
        verbose_name='Текущий статус',
        choices=SbolRegistryOutStatuses,
        required=True
    )
    reg_file = EmbeddedDocumentField(
        SbolRegistryTaskFile,
        verbose_name='Данные файла реестра',
        required=True,
    )
    known_error = StringField(verbose_name='Известное обработанное исключение')
    error_message = StringField(
        verbose_name='Сообщение об ошибке, если она известна и обработана')

    # данные, которые появляются в процессе выполнения задачи
    log = ObjectIdField(
        verbose_name='Текущий лог соединения со СБОЛ',
        default=None
    )
    logs = ListField(
        ObjectIdField(),
        verbose_name='Бывшие (неудавшиеся, незавершённые попытки) логи '
                     'соединения со СБОЛ'
    )
    reg_uuid = StringField(verbose_name='ИД реестра в СБОЛ', default=None)
    request_uuid = StringField(verbose_name='Запрос в СБОЛ', default=None)
    link_uuid = StringField(verbose_name='Ссылка в BigFiles СБОЛ', default=None)
    link_url = StringField(
        verbose_name='Относительная урла для загрузки файла',
        default=None
    )
    job_uuid = StringField(
        verbose_name='Задача по обработке файла в СБОЛ',
        default=None
    )
    doc_uuid = StringField(
        verbose_name='Документ (внутренний ИД)',
        default=None
    )
    doc_num = IntField(
        verbose_name='Документ (внутренний номер)',
        default=None
    )
    ticket = StringField(
        verbose_name='ИД документа запроса на проведение пакета реестров',
        default=None
    )

    file = None

    def prepare_file(self):
        filename, file = get_file_from_gridfs(self.reg_file.file_id)
        self.file = {
            'filename': filename,
            'file': file,
        }

    def save(self, *args, **kwargs):
        self.updated = datetime.datetime.now()
        return super().save(*args, **kwargs)


class SbolRequestId(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'SbolRequestId',
    }

    created = DateTimeField(verbose_name='Создано')
    request_id = StringField(verbose_name='СБОЛ RequestId')


class SberSession(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'SberSession',
    }

    created = DateTimeField(verbose_name='Создано')
    used = DateTimeField(verbose_name='Дата последнего использования')
    uuid = StringField(verbose_name='ИД сессии')


class SberLock(Document):
    """
    Блокировки обмена с УПШ. Наличие неразрешённой блокировки запрещает обмен
    """
    meta = {
        'db_alias': 'queue-db',
        'collection': 'SberLock',
    }

    created = DateTimeField(required=True, verbose_name='Создано')
    log = ObjectIdField(
        verbose_name='Лог соединения с УПШ',
        default=None
    )
    reason = StringField(required=True, verbose_name='Причина блокировки')
    resolved = DateTimeField(verbose_name='Когда решена причина блокировки')


class SbolLog(Document):
    meta = {
        'db_alias': 'logs-db',
        'collection': 'SbolLog',
    }

    created = DateTimeField(verbose_name='Создано')
    log = ListField(StringField(verbose_name='СБОЛ OrgId'))
    status = StringField(verbose_name='Статус завершения')

