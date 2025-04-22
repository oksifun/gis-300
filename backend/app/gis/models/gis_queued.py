from settings import GIS

from bson import ObjectId

from mongoengine.document import Document
from mongoengine.fields import ObjectIdField, StringField, DateTimeField

from app.gis.models.choices import GisObjectType

from app.gis.utils.common import sb, get_time, local_time


class QueuedType:
    HOUSE = 'House'
    AREA = 'Area'
    TENANT = 'Tenant'
    HOUSE_METER = 'HouseMeter'
    AREA_METER = 'AreaMeter'
    METER_READINGS = 'Readings'
    ACCRUAL_DOC = 'AccrualDoc'
    ACCRUAL = 'Accrual'


class GisQueued(Document):
    """Запись о планируемой выгрузке в ГИС ЖКХ"""

    ORDERED_TYPES: tuple = (
        QueuedType.TENANT,
        QueuedType.HOUSE_METER,
        QueuedType.AREA_METER,
    )  # поддерживаемые типы объектов в порядке выгрузки

    _DELETE_RECYCLED: bool = True  # удалять распределенные записи?
    _DEFAULT_MIN_DELAY = 10  # задержка в минутах по умолчанию перед выгрузкой

    meta = dict(
        db_alias='queue-db',  # WARN не legacy_db! bd='task_queue'
        collection='gis_scheduled',  # TODO gis_queued
        indexes=[
            {'fields': ('object_id', 'house_id'), 'unique': True},
            'object_type', 'scheduled',
        ], index_background=True, auto_create_index=False,
    )

    # region ПОЛЯ МОДЕЛИ
    object_type = StringField(required=True,  # TODO _type?
        verbose_name="Тип (название класса) объекта")

    object_id = ObjectIdField(required=True,  # не primary_key
        verbose_name="Идентификатор объекта")

    house_id = ObjectIdField(  # не всегда необходим
        verbose_name="Идентификатор дома")

    _record_id = ObjectIdField(db_field='record_id',
        verbose_name="Ид. записи о планирующей операции")

    scheduled = DateTimeField(  # default=None,
        verbose_name="Планируемые дата и время выгрузки")

    saved = DateTimeField(default=get_time,
        verbose_name="Дата и время постановки в очередь")
    # endregion ПОЛЯ МОДЕЛИ

    @property
    def created(self):  # WARN Document._created
        """
        Дата и время генерации идентификатора документа

        ObjectId содержит отпечаток времени в UTC
        """
        # return timezone('Europe/Moscow').localize(self.pk.generation_time)
        return local_time(self.pk.generation_time)

    @classmethod
    def export(cls, object_type: str, object_id: ObjectId,
               house_id: ObjectId = None, **time_delta) -> int:
        """
        Поставить объект в очередь на выгрузку в ГИС ЖКХ

        Выгрузка очереди выполняется каждые 14 минут (gis.scheduled)
        """
        # WARN export_changes проверяется при выполнении запланированной задачи

        if not time_delta:
            time_delta = {'minutes': cls._DEFAULT_MIN_DELAY}

        return cls.objects(__raw__={
            'object_id': object_id, 'house_id': house_id,  # индекс
            'object_type': object_type,  # индекс
        }).update_one(
            set__saved=get_time(),  # обновляем время постановки в очередь
            set__scheduled=get_time(**time_delta),  # планируемое время выгрузки
            upsert=True,  # WARN создаваем отсутствующие документы
        )  # возвращает кол-во созданных и/или обновленных записей

    @classmethod
    def put(cls, document: Document, **time_delta):
        """
        Поставить документ в очередь на выгрузку в ГИС ЖКХ
        """
        class_name: str = document.__class__.__name__

        from app.house.models.house import House
        from app.area.models.area import Area
        from processing.models.billing.account import Tenant
        from app.meters.models.meter import AreaMeter, HouseMeter
        from app.accruals.models.accrual_document import AccrualDoc
        from processing.models.billing.accrual import Accrual

        if isinstance(document, House):  # включая подъезды и лифты
            house_id = document.id  # house_id = object_id
        elif isinstance(document, Area):  # включая комнаты
            house_id = document.house.id
        elif isinstance(document, Tenant):
            house_id = document.area.house.id
        elif isinstance(document, AreaMeter):
            house_id = document.area.house.id
        elif isinstance(document, HouseMeter):
            house_id = document.house.id
        elif isinstance(document, AccrualDoc):
            house_id = document.house.id  # из ЛС
        elif isinstance(document, Accrual):
            house_id = document.account.house.id  # из ЛС
        else:  # неизвестный тип объекта?
            raise NotImplementedError("Выгрузка в ГИС ЖКХ объекта"
                f" типа {sb(class_name)} не поддерживается")

        return cls.export(class_name, document.id, house_id, **time_delta)

    @classmethod
    def distributed(cls, *type_s: str) -> dict:
        """
        Распределить подлежащие выгрузке объекты по домам и организациям

        :returns: '_type': ProviderId: HouseId: ObjectId: saved
        """
        from app.gis.utils.houses import get_provider_house_ids  # WARN x House

        recycled_ids: list = []
        typed_housed: dict = {}

        if not type_s:  # признаки объектов не указаны?
            type_s = cls.ORDERED_TYPES  # все признаки объектов

        for queued in cls.objects(__raw__={  # подлежащие выгрузке
            'object_type': {'$in': type_s},  # индекс
            'scheduled': {'$not': {'$gt': get_time()}},  # null (вряд ли) or lte
        }).as_pymongo():
            assert isinstance(queued, dict)
            if queued.get('house_id') is None:
                assert queued['object_type'] in {GisObjectType.HOUSE}, \
                    "Отсутствует идентификатор дома выгружаемого объекта"
                queued['house_id'] = queued['object_id']
            scheduled: dict = typed_housed \
                .setdefault(queued['object_type'], {}) \
                .setdefault(queued['house_id'], {})
            scheduled[queued['object_id']] = queued['saved']  # дата постановки

            if cls._DELETE_RECYCLED:  # удалять после использования?
                recycled_ids.append(queued['_id'])  # подлежит удалению

        transportable: dict = {}

        for object_type, house_objects in typed_housed.items():
            provider_houses: dict = get_provider_house_ids(*house_objects)

            for provider_id, house_ids in provider_houses.items():
                for house_id in house_ids:
                    transportable \
                        .setdefault(object_type, {}) \
                        .setdefault(provider_id, {}) \
                        .setdefault(house_id, {}) \
                        .update(house_objects[house_id])  # обновляем словарь

        if recycled_ids:  # подлежащие удалению записи?
            cls.objects(id__in=recycled_ids).delete()

        return {_type: transportable[_type]  # сортированный словарь
            for _type in sorted(transportable,  # keys
                key=lambda t: cls.ORDERED_TYPES.index(t)  # порядок сортировки
                    if t in cls.ORDERED_TYPES else 9999)}  # иначе в конце


class GisQueuedMixin:

    def export_to_gis(self, house_id: ObjectId = None) -> int:

        assert isinstance(self, Document)
        model_name: str = self.__class__.__name__  # TODO Document.name?

        if not house_id:
            if hasattr(self, 'house') and getattr(self.house, 'id', None):
                house_id = self.house.id
            elif hasattr(self, 'area') and hasattr(self.area, 'house') \
                    and getattr(self.area.house, 'id', None):  # дом помещения?
                house_id = self.area.house.id
            else:  # идентификатор дома не определен!
                raise NotImplementedError(f"Для выгрузки в ГИС ЖКХ {model_name}"
                    " необходимо определить идентификатор дома")

        return GisQueued.export(model_name, self.id, house_id)
