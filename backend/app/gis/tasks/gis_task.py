from bson import ObjectId

from mongoengine.document import Document
from mongoengine.fields import StringField, DateTimeField, \
    ListField, DictField
from mongoengine.base.fields import ObjectIdField

from app.gis.utils.common import get_time


class GisTask(Document):

    meta = dict(
        db_alias='queue-db',  # ~ task_queue WARN не legacy_db
        collection='gis_tasks',
        indexes=[
            'name', 'providers', 'houses', '-saved',
        ], index_background=True, auto_create_index=False,
    )

    # region ПОЛЯ МОДЕЛИ
    name = StringField(required=True, verbose_name="Название задачи")

    providers = ListField(  # default=[], required=False - пуст в случае error
        field=ObjectIdField(verbose_name="Идентификатор организации"),
    )
    houses = ListField(  # default=[], required=False,
        field=ObjectIdField(verbose_name="Идентификатор дома"),
    )
    operations = ListField(  # default=[], required=False,
        field=ObjectIdField(verbose_name="Идентификатор (записи об) операции"),
    )

    error = StringField(verbose_name="Ошибка в процессе выполнения")

    saved = DateTimeField(required=True, verbose_name="Дата и время сохранения")

    _dist_ = DictField(db_field='distributed', default=None)  # TODO УДАЛИТЬ
    # endregion ПОЛЯ МОДЕЛИ

    def clean(self):

        self._dist_ = None  # подлежит удалению

        self.saved = get_time()

    def save(self, **kwargs):

        if self.error or self.operations:  # ошибка или выполнены?
            super().save(**kwargs)  # сохраняем документ

    def add_provider(self, provider_id: ObjectId):

        assert provider_id, "Некорректный идентификатор дома задачи ГИС ЖКХ"

        if not self.providers:
            self.providers = [provider_id]
        elif provider_id not in self.providers:
            self.providers.append(provider_id)

    def add_house(self, house_id: ObjectId):

        assert house_id, "Некорректный идентификатор дома задачи ГИС ЖКХ"

        if not self.houses:
            self.houses = [house_id]
        elif house_id not in self.houses:
            self.houses.append(house_id)
