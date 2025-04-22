from copy import deepcopy
from datetime import datetime

from uuid import UUID
from bson import ObjectId

from mongoengine import QuerySet, Document, EmbeddedDocument, BooleanField
from mongoengine.fields import StringField, IntField, DateTimeField, \
    DictField, ListField, ObjectIdField, UUIDField, EmbeddedDocumentField

from app.gis.models.choices import (
    GisRecordStatusType,
    GIS_OPERATION_CHOICES, CANCELABLE_STATUSES, GIS_RECORD_STATUSES,
    GIS_RECORD_STATUS_CHOICES, GIS_RECORD_OLD_STATUS_CHOICES, GisTaskStateType,
    GIS_TASK_STATE_CHOICES
)

from app.gis.utils.common import get_guid, get_time, deep_update, dt_from
from processing.models.billing.embeddeds.base import DenormalizedEmbeddedMixin


class _GisLog(EmbeddedDocument):
    """Запись журнала операции"""

    debug = StringField(verbose_name="Отладочный текст")
    info = StringField(verbose_name="Информационный текст")
    warn = StringField(verbose_name="Текст предупреждения")
    error = StringField(verbose_name="Текст ошибки")

    time = DateTimeField(default=datetime.now, verbose_name="Время записи")

class DenormalizedProviderInfoEmbedded(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'Provider'

    id = ObjectIdField(db_field="_id", required=True)
    str_name = StringField(
        verbose_name='Полное наименование организации'
    )
    ogrn = StringField(
        verbose_name='Значение реквизита ОГРН организации',
    )
    inn = StringField(
        verbose_name='Значение реквизита ИНН организации',
    )
    crm_status = StringField(
        verbose_name='Статус организации',
    )
    gis_online_changes = BooleanField(
        default=False,
        verbose_name="Выгружать изменения в ГИС ЖКХ?",
    )

class DenormalizedHouseInfoEmbedded(DenormalizedEmbeddedMixin, EmbeddedDocument):
    DENORMALIZE_FROM = 'House'

    id = ObjectIdField(db_field="_id")
    address = StringField(verbose_name='Адрес дома')
    fias_addrobjs = ListField(
        StringField(),
        verbose_name='Родительские addrobj дома'
    )
    gis_uid = StringField(
        null=True,
        verbose_name='Уникальный номер дома в ГИС ЖКХ'
    )
    gis_fias = StringField(
        null=True,
        verbose_name='ФИАС в ГИС ЖКХ'
    )
    cadastral_number = StringField(
        verbose_name='Кадастровый номер помещения',
    )

class GisRecord(Document):
    """Запись об операции"""

    meta = dict(
        db_alias='legacy-db', collection='GisRecord',
        indexes=[
            'saved', '-saved',  # gte, lte
            'parent_id', 'follower_id', 'pending_id',  # для поиска связных
            ('agent_id', '-saved'),
            ('provider_id', '-saved'),  # порядок(-) только в составных индексах
            ('status', '-saved'),  # purge
        ], index_background=True, auto_create_index=False,
    )
    # TODO collection = GisRecord._get_collection()
    #  collection.drop_index('ack_guid_1')
    #  collection.drop_index('message_guid_1')

    # region ПОЛЯ МОДЕЛИ
    generated_id = ObjectIdField(primary_key=True,  # ~ _id
        default=ObjectId,  # дата_и_время(4)-рандом(5)-счетчик(3)
        verbose_name="Автоматически генерируемый идентификатор записи")

    operation = StringField(required=True, choices=GIS_OPERATION_CHOICES,
        verbose_name="Наименование (класса) операции (НЕ объектов)")

    parent_id = ObjectIdField(  # по умолчанию default = None, required = False
        verbose_name="Идентификатор записи порождающей операции")
    child_id = ObjectIdField(  # порожденная / идентичная
        verbose_name="Идентификатор выполняемой после формирования операции")
    pending_id = ObjectIdField(  # упреждающая (предшествующая)
        verbose_name="Идентификатор ожидаемой выполнения операции")
    follower_id = ObjectIdField(  # последующая / отложенная
        verbose_name="Идентификатор выполняемой после завершения операции")

    provider_id = ObjectIdField(
        verbose_name="Идентификатор (организации) поставщика информации")
    provider_info = EmbeddedDocumentField(
        DenormalizedProviderInfoEmbedded,
        verbose_name='Инфомрация об организации (поставщике информации)'
    )
    agent_id = ObjectIdField(
        verbose_name="Идентификатор (платежного) агента ~ Р(К)Ц")
    relation_id = ObjectIdField(
        verbose_name="Идентификатор связанной организации, откуда брать данные")
    house_id = ObjectIdField(verbose_name="Идентификатор дома операции")
    house_info = EmbeddedDocumentField(
        DenormalizedHouseInfoEmbedded,
        verbose_name="Информация о доме операции"
    )

    object_type = StringField(verbose_name="Тип объектов операции")
    # WARN кроме list может использоваться tuple как значение ListField
    object_ids = ListField(field=ObjectIdField(), default=None,
        # по умолчанию default = [], required = False
        verbose_name="Аргументы формирования (идентификаторы объектов) запроса")
    period = DateTimeField(verbose_name="Период (первое число месяца) данных")
    request = DictField(default=None,  # по умолчанию default = {}
        verbose_name="Ключевая (сформированная) часть запроса операции")

    fraction = ListField(field=IntField(min_value=1), default=None,  # [cur,tot]
        verbose_name="Порядковый номер подзапроса и их общее количество")

    required = DictField(default=None,  # requirements?
        verbose_name="Требуемый для выполнения операции процент ид-ов ГИС ЖКХ")
    options = DictField(default=None,  # по умолчанию required = False
        verbose_name="Параметры выполнения и атрибуты запроса операции")

    desc = StringField(null=True, verbose_name="Описание операции")

    message_guid = UUIDField(default=get_guid,  # не primary_key
        verbose_name="Идентификатор сообщения запроса квитанции (НЕ состояния)")
    ack_guid = UUIDField(  # не primary_key
        verbose_name="Идентификатор квитанции о приеме сообщения в обработку")

    retries = IntField(  # default=None
        verbose_name="Количество попыток получения состояния обработки")
    restarts = IntField(  # 0 ~ null не сохраняется
        verbose_name="Количество перезапусков запроса после ошибок")

    scheduled = DateTimeField(
        verbose_name="Планируемое время запуска (задачи) операции")

    canceled = DateTimeField(
        verbose_name="Время отмены выполнения операции")

    acked = DateTimeField(
        verbose_name="Время получения подтверждения запроса (квитанции)")
    stated = DateTimeField(
        verbose_name="Время получения состояния (результата) выполнения")
    stored = DateTimeField(
        verbose_name="Время сохранения результата выполнения операции")

    saved = DateTimeField(required=True,  # по умолчанию default = None
        verbose_name="Время сохранения (изменения) записи об операции")

    status = StringField(required=True,
        choices=GIS_RECORD_STATUS_CHOICES + GIS_RECORD_OLD_STATUS_CHOICES,
        verbose_name="Текущее состояние выполнения операции")

    warnings = ListField(field=StringField(max_length=1200), default=None,
        verbose_name="Предупреждения в процессе выполнения операции")
    fails = IntField(default=0,
        verbose_name="Количество ошибок (в данных) объектов операции")

    error = StringField(verbose_name="Ошибка в процессе выполнения операции")
    trace = StringField(verbose_name="Причина возникновения ошибки (если есть)")

    log = ListField(StringField(min_length=1), default=None,  # не []
        verbose_name="Журнал (выполнения) операции")
    task_owner = ObjectIdField(
        null=True,
        default=None,
        verbose_name="Ответственный сотрудник")
    task_state = StringField(
        default=GisTaskStateType.NEW,
        choices=GIS_TASK_STATE_CHOICES,
        verbose_name="Статус работы")
    # endregion ПОЛЯ МОДЕЛИ

    # region СВОЙСТВА ЗАПИСИ ОБ ОПЕРАЦИИ
    @property
    def version(self) -> str:
        """Используемая версия запроса"""
        return (
            self.request.get('version') if self.request else None
        ) or 'ОТСУТСТВУЕТ'

    @property
    def is_import(self) -> bool:
        """Запись об операции импорта (загрузки в) ГИС ЖКХ?"""
        # operation_name: str = self.operation.lower()
        return self.operation.startswith('import')

    @property
    def family(self) -> QuerySet:
        """
        Порождающая и порожденные (записи об) операции

        WARN Исключая текущую запись об операции!
        """
        raw_query: dict = {'$or': [
            {'_id': self.parent_id, 'child_id': {'$ne': None}},  # порождающая
            {'parent_id': self.parent_id},  # порожденные
        ]} if self.parent_id \
            else {'parent_id': self.generated_id}

        raw_query['_id'] = {'$ne': self.generated_id}  # кроме текущей

        return GisRecord.objects(__raw__=raw_query)

    @property
    def crowd(self) -> QuerySet:
        """
        Упреждающие (записи об) операции

        WARN Исключая текущую запись об операции!
        """
        assert self.follower_id, "Запись об операции не является упреждающей"

        return GisRecord.objects(__raw__={
            'follower_id': self.follower_id,  # все упреждающие
            '_id': {'$ne': self.generated_id},  # кроме текущей
        })

    @property
    def __alike_ids(self) -> list:
        """
        Список записей об подобных текущей актуальных операциях

        Обрабатываемые более 3-х дней сообщения отправляются с новым ид-ом
        """
        ACKED_IN_HOURS = 24  # квитанция получена не далее чем, дней

        return GisRecord.objects(__raw__={
            '_id': {'$ne': self.generated_id},  # не текущая
            'parent_id': None,  # без порожденных или порождающие
            'provider_id': self.provider_id, 'house_id': self.house_id,
            'operation': self.operation,  # об аналогичной операции
            'canceled': None,  # неотмененной
            'acked': {'$gte': get_time(hours=-ACKED_IN_HOURS)},  # с квитанцией
            'stated': None,  # без состояния обработки
        }).distinct('id')  # .count?
    # endregion СВОЙСТВА ЗАПИСИ ОБ ОПЕРАЦИИ

    @classmethod
    def insert_the(cls, data: dict):
        """Сохранить запись об операции"""
        def id_or_none(field_name: str) -> ObjectId or None:
            return ObjectId(data[field_name]) if field_name in data else None

        assert data.get('ack_guid'), "Отсутствует идентификатор квитанции"

        return cls(
            generated_id=ObjectId(data.get('id') or data.get('_id')
                or data.get('generated_id')),  # или новый
            message_guid=UUID(data['message_guid']),
            ack_guid=UUID(data['ack_guid']),
            operation=data['operation'],
            provider_id=id_or_none('provider_id'),
            house_id=id_or_none('house_id'),
            agent_id=id_or_none('agent_id'),
            fraction=data.get('fraction'),
            options=data.get('options'),
            desc=data.get('desc'),
            acked=dt_from(data.get('acked')),
            stated=dt_from(data.get('stated')),
            stored=dt_from(data.get('stored')),
            scheduled=dt_from(data.get('scheduled')),
            saved=dt_from(data['saved']), status=data['status'],
        ).save()

    def __str__(self) -> str:
        """
        Строковое представление записи об операции
        """
        id_or_not = f"с идентификатором {self.generated_id}" \
            if self.generated_id else "БЕЗ идентификатора"

        org_or_anon = f"о выполняемой {self.provider_id}" \
            if self.provider_id else "об анонимной"
        self_or_agent = f"от лица {self.agent_id}" if self.agent_id \
            else "от своего лица" if self.provider_id \
            else "(без поставщика информации)"
        house_or_not = f"для дома {self.house_id}" \
            if self.house_id else "без указания дома"

        return f"Запись {org_or_anon} {self_or_agent} {house_or_not}" \
            f" операции {id_or_not}"

    def __copy__(self) -> 'GisRecord':
        """
        Аналогичная (не идентичная) текущей запись об операции

        Данные запроса и состояние (выполнения) операции не копируются
        """
        return GisRecord(
            operation=self.operation,  # WARN desc должен генерироваться заново
            provider_id=self.provider_id, house_id=self.house_id,
            provider_info=self.provider_info, house_info=self.house_info,
            agent_id=self.agent_id,  # необходим для формирования и отображения
            relation_id=self.relation_id,  # запись о связанной организации
            object_type=self.object_type, period=self.period,  # WARN заменяемые
            follower_id=self.follower_id,  # parent_id и child_id при порождении
            options=self.options or None,  # с теми же параметрами выполнения
            status=GisRecordStatusType.PENDING,  # по умолчанию - Отложена
        )  # WARN подлежит сохранению

    def clone_reset(self, ) -> 'GisRecord':
        """
        Создание полной независимой копии текущей записи,
        с обнулением определенных полей для перезапуска.
        """
        # Создаем глубокую копию текущего объекта
        clone_data = deepcopy(self.to_mongo().to_dict())
        reset_fields = [
            'message_guid', 'ack_guid', 'retries', 'restarts', 'scheduled',
            'canceled', 'acked', 'stated', 'stored', 'saved', 'warnings',
            'fails', 'error', 'trace', 'log', 'task_owner', 'task_state'
        ]
        # Обнуляем определенные поля
        for field in reset_fields:
            clone_data[field] = None

        # Меняем статус на 'Создана' с текущей датой
        clone_data['status'] = GisRecordStatusType.CREATED
        clone_data['saved'] = datetime.now()

        # Удаляем _id, чтобы MongoDB создала новый уникальный ID
        clone_data.pop('_id', None)

        # Создаем новый объект из клонированных данных
        clone_record = GisRecord(**clone_data)

        # Сохраняем новую запись в базе данных
        clone_record.save()

        return clone_record

    def child(self) -> 'GisRecord':
        """
        Создать порожденную текущей запись об операции
        """
        child_record: GisRecord = self.__copy__()  # идентичная запись
        assert child_record.generated_id, \
            "Отсутствует идентификатор порожденной записи об операции"

        if self.child_id:  # текущая запись является порождающей?
            # WARN нельзя выполнять порожденную до подготовки запроса
            child_record.child_id = self.child_id  # сдвигаем в очереди

        # связываем (подлежащую сохранению) порождающую с порожденной
        self.child_id = child_record.generated_id  # генерируется при создании

        # идентификатор порождающей или текущей записи об операции
        child_record.parent_id = self.parent_id or self.generated_id

        return child_record

    def heir(self, element_limit: int = 0, **update_data) -> 'GisRecord':
        """
        Создать продолжающую (наследующую) текущую запись об операции

        :param element_limit: ограничение кол-ва аргументов запроса операции
        :param update_data: обновленные данные запроса операции
        """
        child_record = self.child()  # порожденная текущей запись об операции

        child_record.object_type = self.object_type  # копируем тип объектов

        if not self.object_ids:  # запрос без аргументов?
            pass  # child_record.object_ids = None  # нечего передавать
        elif element_limit == 0:  # ограничение не наложено?
            assert update_data, \
                "Возможна передача всех аргументов только измененного запроса"
            child_record.object_ids = self.object_ids  # все аргументы запроса
        elif len(self.object_ids) > element_limit:  # нарушено ограничение?
            if not self.fraction:  # порождающая запись операции?
                fractions = -(len(self.object_ids) // -element_limit)  # ~ ceil
                self.fraction = [1, fractions]  # первый подзапрос

            child_record.fraction = [self.fraction[0] + 1, self.fraction[1]]

            # [элементы списка][больше кол-ва элементов:] = [] - пустой список
            child_record.object_ids = self.object_ids[element_limit:] or None
            self.object_ids = self.object_ids[:element_limit]
        # WARN порождающая запись об операции подлежит сохранению

        request_copy: dict = {**self.request} if self.request else {}

        if update_data:  # изменение данных запроса операции?
            child_record.request = deep_update(request_copy, update_data)
        else:  # копия запроса порождающей (записи об) операции!
            child_record.request = request_copy

        return child_record  # WARN подлежащая сохранению порожденная запись

    def clean(self):
        """
        Очистка данных (документа) записи об операции

        Выполняется перед валидацией и сохранением записи
        """
        if self.log is not None and not self.log:  # пустой список?
            self.log = None  # обнуляем пустой журнал

        if self.object_ids is not None and not self.object_ids:  # пустой?
            self.object_ids = None  # обнуляем отсутствующие аргументы запроса

        if self.request == {}:  # пустой запрос?
            self.request = None  # обнуляем данные запроса

        if self.options == {}:  # только запрашивались (не записывались)?
            self.options = None  # обнуляем параметры выполнения операции

        if self.required == {}:  # все требования (не) выполнены?
            self.required = None  # обнуляем перечень требований

        if self.restarts == 0:  # запрос не перезапускался после ошибок?
            self.restarts = None  # обнуляем количество перезапусков

        if self.retries == 0:  # результат получен с первой попытки?
            self.retries = None  # обнуляем количество попыток

        self.saved = get_time()  # дата и время последнего сохранения

    def warning(self, message: str):
        """Добавить предупреждение в запись об операции"""
        if self.warnings is None:  # список предупреждений пуст?
            self.warnings = []  # создаем новый список

        if message not in self.warnings:  # сообщение еще не добавлялось?
            self.warnings.append(message)  # добавляем в список

    def fail(self):
        """Получена ошибка в данных"""
        self.fails = self.fails + 1 if self.fails else 1

    def cancel(self,
            skip_child: bool = False, skip_follower: bool = False) -> list:
        """
        Отменить выполнение порождающей и/или порожденных операции
        """
        canceled_ids: list = []

        if not skip_child and self.child_id:
            child: GisRecord = \
                GisRecord.objects(generated_id=self.child_id).first()
            assert child is not None, f"Запись об операции {self.child_id}" \
                f" порожденная {self.parent_id or self.generated_id} не найдена"
            if child.status in CANCELABLE_STATUSES:
                canceled_ids += child.cancel()

        if not skip_follower and self.follower_id:
            follower: GisRecord = \
                GisRecord.objects(generated_id=self.follower_id).first()
            assert follower is not None, f"Последующая за {self.generated_id}" \
                f" запись об операции {self.follower_id} не найдена"
            if follower.status in CANCELABLE_STATUSES:
                canceled_ids += follower.cancel()

        if self.status in CANCELABLE_STATUSES:
            self.status = GisRecordStatusType.CANCELED  # Отменена
            self.canceled = get_time()  # фиксируем дату и время

            self.save()  # сохраняем запись об отмененной операции
            canceled_ids.append(self.generated_id)

        return canceled_ids

    @classmethod
    def purge(cls, before: datetime,
            after: datetime = None, *statuses: str) -> list:
        """
        Удалить неактуальные записи об операциях

        :param before: сохраненные до указанной даты
        :param after: сохраненные после указанной даты (или только до)

        :param statuses: состояние (записи об) операции (или все)
        """
        assert before and (not after or after < before)  # ---a-----b--->
        query: dict = {'saved': {'$lte': before}}
        if after:
            query['saved']['$gte'] = after

        if statuses:
            assert all(s in GIS_RECORD_STATUSES for s in statuses)
            query['status'] = {'$in': list(statuses)}

        record_ids: list = cls.objects(__raw__=query).distinct('id')

        if record_ids:
            cls.objects(__raw__={'_id': {'$in': record_ids}}).delete()

        return record_ids


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    true = True; false = False; null = None
    ISODate = lambda dt: datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S.%fZ")

    r = GisRecord.insert_the({})  # TODO данные записи об операции
    print('INSERTED RECORD ID', r.generated_id)
