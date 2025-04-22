from typing import Optional

from uuid import UUID
from bson import ObjectId

from mongoengine import Document, \
    ObjectIdField, UUIDField, StringField, DateTimeField, DictField

from pymongo.results import BulkWriteResult
from pymongo.errors import BulkWriteError

from app.gis.core.exceptions import InternalError

from app.gis.models.choices import GisGUIDStatusType, GisObjectType, \
    GIS_GUID_STATUS_CHOICES

from app.gis.utils.common import get_time, sb, dt_from


class GisTransportable:
    """Транспортируемый в ГИС ЖКХ объект"""

    _is_changed: bool = False  # признак (изменения) сохраняемого документа
    _is_deleted: bool = False  # признак подлежащего удалению документа

    # имеющие TransportGUID записи подлежат выгрузке в ГИС ЖКХ
    transport = UUIDField(verbose_name="Транспортный идентификатор ГИС ЖКХ")

    # имеющие GisRecord.pk записи - в процессе выгрузки или результат не получен
    record_id = ObjectIdField(verbose_name="Идентификатор записи об операции")

    @classmethod
    def assemble(cls, record_id: ObjectId) -> dict:
        """
        Собрать (транспортные) идентификаторы ГИС ЖКХ по записи об операции

        :returns: 'TransportGUID': GUID
        """
        assert issubclass(cls, Document)

        return {str(guid.transport): guid for guid in cls.objects(__raw__={
            'record_id': record_id,  # привязанные к (записи об) операции
            'transport': {'$ne': None},  # с транспортным идентификатором
        })}

    @property
    def is_changed(self) -> bool:
        """Подлежит сохранению?"""
        return self._is_changed

    @is_changed.setter
    def is_changed(self, value: bool):
        """Подлежит сохранению?"""
        self._is_changed = value

    @property
    def is_deleted(self) -> bool:
        """Подлежит удалению?"""
        return self._is_deleted

    @is_deleted.setter
    def is_deleted(self, value: bool):
        """Подлежит удалению?"""
        self._is_deleted = value

    @property
    def is_mapped(self) -> bool:
        """Сопоставлен (с операцией)?"""
        return self.record_id and self.transport

    @property
    def is_pending(self) -> bool:
        """Подлежит сохранению или удалению?"""
        return self._is_deleted or self._is_changed


class GUID(Document, GisTransportable):
    """Данные (идентификатор) ГИС ЖКХ"""

    ACCOUNT_TAGS: dict = {
        GisObjectType.UO_ACCOUNT: "ЛС КУ",
        GisObjectType.CR_ACCOUNT: "ЛС КР",
        GisObjectType.TKO_ACCOUNT: "ЛС ТКО",
        GisObjectType.RSO_ACCOUNT: "ЛС РСО",
        GisObjectType.RC_ACCOUNT: "ЛС РКЦ",
        GisObjectType.OGV_OMS_ACCOUNT: "ЛС ОГВ",

    }  # признаки ЛС
    METER_TAGS: dict = {
        GisObjectType.AREA_METER: "ИПУ",
        GisObjectType.HOUSE_METER: "ОДПУ",
    }  # признаки ПУ
    GIS_TAGS: dict = {
        GisObjectType.CHARTER: "устава",
        GisObjectType.CONTRACT: "ДУ",
    }  # признаки объектов ГИС ЖКХ
    VERSION_TAGS: dict = {
        GisObjectType.CONTRACT_OBJECT: "об. управления",
        GisObjectType.NOTIFICATION: "изв. о квитировании",
    }  # признаки объектов с идентификатором версии
    UNIQUE_TAGS: dict = {
        GisObjectType.ACCRUAL: "док. начислений",
    }  # признаки объектов с уникальным номером

    OBJECT_TAGS: dict = {
        **ACCOUNT_TAGS, **METER_TAGS, **GIS_TAGS,
        **VERSION_TAGS, **UNIQUE_TAGS,
        GisObjectType.PROVIDER: "организации",
        GisObjectType.LEGAL_ENTITY: 'ЮЛ',
        GisObjectType.HOUSE: "дома",
        GisObjectType.PORCH: "подъезда",
        GisObjectType.LIFT: "лифта",
        GisObjectType.AREA: "помещения",
        GisObjectType.ROOM: "комнаты",
    }  # все возможные признаки объектов
    DATED_TAGS: dict = {
        'Tenant': 'UOAccount',
        'ServiceBind': 'ContractObject',
    }  # больше не используемые признаки объектов

    SHARED_TAGS: list = [
        GisObjectType.PROVIDER, GisObjectType.HOUSE, GisObjectType.LEGAL_ENTITY
    ]  # признаки общих (без provider_id) данных ГИС ЖКХ

    # __raw__ позволяет искать (objects/filter) по ObjectId = None
    # null аналогичен $exists: False; в $in нельзя использовать set

    meta = dict(
        db_alias='legacy-db', collection='GUID',
        indexes=[
            'object_id', 'provider_id', 'record_id',
            'transport', 'gis', 'root', 'unique',
            ('provider_id', '-saved'),
            {'fields': ('tag', 'object_id', 'provider_id'), 'unique': True},
        ], index_background=True, auto_create_index=False,
    )

    # WARN _get_changed_fields включает список измененных ВЛОЖЕННЫХ полей
    _changed_fields: list = []  # нет по умолчанию в Document

    # region ПОЛЯ МОДЕЛИ
    # WARN record_id и transport в GisTransportable

    tag = StringField(required=True, choices=[*OBJECT_TAGS, *DATED_TAGS],
        verbose_name="Признак (название класса) объекта")  # TODO _type?

    # один и тот же объект может быть выгружен несколькими организациями!
    object_id = ObjectIdField(required=True,
        verbose_name="Идентификатор объекта")

    provider_id = ObjectIdField(sparse=True,  # допускается null
        verbose_name="Идентификатор организации (поставщика информации)")

    premises_id = ObjectIdField(
        verbose_name="Идентификатор помещения (дома, квартиры, комнаты)")

    # ид. версии обычно используется при внесении изменений в сущность
    # корневой ид. используется, к примеру, для выгрузки показаний ПУ
    gis = UUIDField(verbose_name="Идентификатор (версии) сущности ГИС ЖКХ")
    root = UUIDField(verbose_name="Идентификатор корневой сущности ГИС ЖКХ")
    version = UUIDField(verbose_name="Идентификатор версии сущности ГИС ЖКХ")

    unique = StringField(sparse=True,  # допускается null (старые записи)
        verbose_name="Уникальный номер ГИС ЖКХ")
    updated = DateTimeField(verbose_name="Дата обновления")

    number = StringField(verbose_name="Номер объекта")
    desc = StringField(null=True, verbose_name="Описание объекта")

    # WARN не всегда сущность ГИС ЖКХ можно (навсегда) удалить
    deleted = DateTimeField(verbose_name="Дата и время аннулирования"
        " сущности ГИС ЖКХ (удалена или отправлена в архив)")  # TODO annulled

    error = StringField(verbose_name="Описание ошибки (если была)")

    status = StringField(choices=GIS_GUID_STATUS_CHOICES,
        verbose_name="Состояние идентификатора ГИС ЖКХ")  # TODO убрать
    saved = DateTimeField(verbose_name="Дата и время сохранения объекта")
    # endregion ПОЛЯ МОДЕЛИ

    # region TODO ПОДЛЕЖАЩИЕ УДАЛЕНИЮ ПОЛЯ
    _ack = UUIDField(db_field='ack', verbose_name="Ид. квитанции ГИС ЖКХ")
    __data = DictField(db_field='data', default=None, verbose_name="Данные")
    # endregion ПОДЛЕЖАЩИЕ УДАЛЕНИЮ ПОЛЯ

    # region КЛАССОВЫЕ МЕТОДЫ
    @classmethod
    def insert_the(cls, data: dict):

        def id_or_none(field_name: str) -> ObjectId or None:

            return ObjectId(data[field_name]) if data.get(field_name) else None

        def uuid_or_none(field_name: str) -> UUID or None:

            return UUID(data[field_name]) if data.get(field_name) else None

        assert data.get('saved') and data.get('status'), \
            "Данные ГИС ЖКХ или состояние не сохранены"

        return GUID(
            id=ObjectId(data.get('id') or data.get('_id')),  # или новый
            record_id=id_or_none('record_id'), transport=data.get('transport'),
            provider_id=id_or_none('provider_id'),
            tag=data['tag'], object_id=ObjectId(data['object_id']),
            premises_id=id_or_none('premises_id'),
            desc=data['desc'],
            gis=uuid_or_none('gis'),
            root=uuid_or_none('root'), version=uuid_or_none('version'),
            unique=data.get('unique'), number=data.get('number'),
            updated=dt_from(data.get('updated')),
            deleted=dt_from(data.get('deleted')),
            saved=dt_from(data['saved']), status=data['status'],
            error=data.get('error'),
        ).save()

    @classmethod
    def object_name(cls, tag: str) -> str:
        """Получить название объекта из признака"""
        if tag in GUID.DATED_TAGS:  # устаревший признак?
            tag = GUID.DATED_TAGS[tag]
        return GUID.OBJECT_TAGS.get(tag) or f"с признаком {sb(tag)}"

    @classmethod
    def write(cls, requests: list) -> BulkWriteResult:
        """Выполнить запросы на изменение данных в БД"""
        try:
            pymongo_collection = cls._get_collection()  # низкоуровневая

            write_result: BulkWriteResult = pymongo_collection.bulk_write(
                requests,  # requests must be a list!
                bypass_document_validation=True,  # без валидации
                ordered=False,  # False - параллельно, True - последовательно
            )
        except BulkWriteError as bulk_write_error:
            """{'writeErrors': [
                {
                    'index': 0, 'code': 11000,
                    'errmsg': "code message collection index dup key",
                    'op': {'field': 'value',...}
                },...
            ],
                'writeConcernErrors': [], 'upserted': [], 'nMatched': 0,
                'nInserted': 0, 'nUpserted': 0, 'nModified': 0, 'nRemoved': 0,
            }"""
            raise InternalError(details='\n'.join(error['errmsg']
                for error in bulk_write_error.details['writeErrors']))

        return write_result
    # endregion КЛАССОВЫЕ МЕТОДЫ

    # region СВОЙСТВА ИДЕНТИФИКАТОРА
    @property
    def title(self) -> str:
        """Название (признака) типа объекта"""
        return GUID.object_name(self.tag)

    @property
    def is_pending(self) -> bool:
        """Подлежит сохранению или удалению?"""
        CONTROL_FIELDS: set = {
            'record_id',  # transport = None в операциях загрузки
            'gis', 'root', 'version',
            'unique', 'number',
            'updated', 'deleted',
            'error'
        }
        return super().is_pending or \
            bool(set(self._changed_fields) & CONTROL_FIELDS)

    @property
    def is_wip(self) -> bool:
        """В работе (другой операцией)?"""
        MAX_HOURS_TO_PROCESS = 24  # TODO в обработке ГИС ЖКХ не более суток

        return self.status in {
            GisGUIDStatusType.NEW,
            GisGUIDStatusType.CHANGED,
            GisGUIDStatusType.WIP,
            GisGUIDStatusType.UNKNOWN,
        } and self.saved > get_time(hours=-MAX_HOURS_TO_PROCESS)

    @property
    def is_true(self) -> bool:
        """Данные ГИС ЖКХ загружены?"""
        if self.tag in self.UNIQUE_TAGS:  # с уникальным номером?
            return self.unique is not None  # : str
        elif self.tag in self.VERSION_TAGS:  # с идентификатором версии?
            return self.version is not None  # : UUID

        return self.gis is not None or self.root is not None  # : UUID
    # endregion СВОЙСТВА ИДЕНТИФИКАТОРА

    def __str__(self):
        """Строковое представление идентификатора ГИС ЖКХ"""
        def id_or_not(_id) -> str:

            return str(_id) if _id is not None else 'БЕЗ идентификатора'

        return id_or_not(self.unique) if self.tag in self.UNIQUE_TAGS else \
            id_or_not(self.version) if self.tag in self.VERSION_TAGS else \
            id_or_not(self.gis)

    def __repr__(self) -> str:
        """Расширенное представление данных ГИС ЖКХ"""
        def _uuid_or_null(value) -> str:
            return f'UUID("{value}")' if value else "null"

        def _id_or_null(value) -> str:
            return f'ObjectId("{value}")' if value else "null"

        def _str_or_null(value) -> str:
            return f'"{value}"' if value else "null"

        return (f'<GUID _id={_id_or_null(self.id)},'
            f' provider_id={_id_or_null(self.provider_id)},'
            f' tag="{self.tag}", object_id=ObjectId("{self.object_id}"),'
            f' gis={_uuid_or_null(self.gis)},'
            f' root={_uuid_or_null(self.root)},'
            f' version={_uuid_or_null(self.version)},'
            f' unique={_str_or_null(self.unique)},'
            f' number={_str_or_null(self.number)},'
            f' transport={_uuid_or_null(self.transport)},'
            f' record_id={_id_or_null(self.record_id)},'
            f' status={self.status}, error={_str_or_null(self.error)}>')

    # TODO def __format__(self, key) -> str:

    def __eq__(self, other) -> bool:
        """
        Равенство двух идентификаторов ГИС ЖКХ

        Должны содержать данные одного и того же объекта

        WARN идентичность данных (идентификаторов) ГИС ЖКХ не проверяется!
        """
        assert isinstance(other, GUID)

        return self.object_id == other.object_id and self.tag == other.tag

    def __bool__(self):
        """
        Результат проверки объекта на "правдивость"

        bool(self) = False, если self существует, но self.gis=None

        __len__ используется в случае отсутствия __bool__
        """
        return self.is_true

    def clean(self):
        """
        Выполняется перед валидацией (validate) и сохранением (save) записи

        Вызывается из validate - должно выполнятся перед атомарными операциями!
        """
        if self.tag in self.DATED_TAGS:  # устаревший признак?
            self.tag = self.DATED_TAGS[self.tag]

        if self.tag in self.SHARED_TAGS and self.provider_id:  # общие данные?
            self.provider_id = None  # TODO заменяем по мере нахождения

        self.status = (GisGUIDStatusType.ERROR if self.error else
            GisGUIDStatusType.WIP if self.record_id else
            GisGUIDStatusType.CHANGED if self.transport else  # scheduled?
            GisGUIDStatusType.SAVED
                if self.gis or self.root or self.version or self.unique
        else GisGUIDStatusType.UNKNOWN)  # записываем статус идентификатора

        # region TODO удаляем по мере нахождения
        self._ack = None
        self.__data = None
        # endregion удаляем по мере нахождения

        self.saved = get_time()  # дата и время последнего сохранения

        self._changed_fields = []  # WARN очищаем измененные поля (Document)

    def delete(self, *args, **kwargs):
        """
        Удалить (без возможности восстановления) документ из БД

        Производится дополнительная проверка на наличие первичного ключа

        WARN КОЛЛЕКЦИЯ ОЧИЩАЕТСЯ ПРИ ПОПЫТКЕ УДАЛЕНИЯ НЕСОХРАНЕННОГО ДОКУМЕНТА!
        """
        if self.id:  # у несохраненных (новых) документов id = None
            super().delete()  # удаляем существующий документ

    def as_req(self, guid_element_name: str = None,
            or_none: bool = False, **element_data) -> Optional[dict]:
        """
        Данные для использования в элементе запроса ГИС ЖКХ

        :param guid_element_name: название поля с идентификатором ГИС ЖКХ
        :param or_none: False - всегда возвращать элемент (даже без ид. ГИС ЖКХ)
            True - None вместо элемента, если задано название поля, но нет ид.
        верно и обратное: None - если название поля не задано, а ид. имеется
        """
        assert self.transport or 'TransportGUID' in element_data, \
            "Элемент запроса должен иметь транспортный идентификатор"

        if 'TransportGUID' in element_data:  # идентификатор в данных запроса?
            self.transport = element_data['TransportGUID']
        elif 'transport' not in self._changed_fields:  # нет в измененных?
            self._mark_as_changed('transport')  # помечаем для сохранения

        if or_none and bool(guid_element_name) != bool(self.gis):  # нестыковка?
            return None
        elif guid_element_name and self.gis:  # TODO not self.deleted?
            # WARN аннулированные объекты могут вызывать ошибку при обновлении
            return {**element_data, 'TransportGUID': self.transport,  # : UUID
                guid_element_name: self.gis}  # : UUID
        else:
            return {**element_data, 'TransportGUID': self.transport}

    def unmap(self):
        """Отвязать идентификатор от последней операции"""
        # WARN self.provider_id в clean

        if self.record_id:
            self.record_id = None  # обнуляем идентификатор записи об операции
        if self.transport:
            self.transport = None  # обнуляем транспортный идентификатор

        if self.error is not None:
            self.error = None  # обнуляем (существующую) ошибку

    def reset(self):
        """Сбросить данные ГИС ЖКХ"""
        self.gis = None
        self.root = None
        self.version = None

        self.unique = None
        self.number = None

        self.updated = None
        self.deleted = None


if __name__ == '__main__':

    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()

    true = True; false = False; null = None

    g = GUID.insert_the({})
    print('INSERTED GUID ID', g.id, 'FOR', g.tag, ':', g.object_id)
