from datetime import datetime

from bson import ObjectId
from mongoengine import Document, StringField, DateTimeField, \
    ObjectIdField, EmbeddedDocumentField, \
    EmbeddedDocument, EmbeddedDocumentListField, FloatField, BooleanField, \
    IntField, ListField, DynamicDocument

from processing.models.billing.base import BindedModelMixin, ProviderBinds


class Operation(EmbeddedDocument):
    """ Модель по операциям на складе """

    id = ObjectIdField(db_field='_id', default=ObjectId)
    declared = FloatField(verbose_name='Заявленное кол-во материала')
    accepted = FloatField(verbose_name='Подтвержденное кол-во материала')
    quantity = FloatField(verbose_name='Кол-во поступившего материала')
    price = IntField(verbose_name='Цена, установленная за единицу материала')
    position = ObjectIdField(verbose_name='Материал из справочника')
    nds = FloatField(verbose_name='Сумма НДС', null=True)
    sum = IntField(
        verbose_name='Подтвержденное количество умноженное на цену'
    )
    total = IntField(verbose_name='Сумма итого с учетом НДС')


class StorageMixin:
    """ Миксин полей, которые нужны документу типа Storage """

    provider = ObjectIdField()
    operations = EmbeddedDocumentListField(
        Operation,
        verbose_name='Список материалов на поступление'
    )
    use_nds = BooleanField(
        required=True,
        default=False,
        verbose_name='в т.ч. НДС 18%'
    )
    calculation_method = StringField(
        choices=(
            ('cost', 'от цены за единицу'),
            ('sum', 'от суммы итого')
        ),
        default='cost')


class StorageEmbeddedMixin:
    """ Миксин полей, которые нужны ВЛОЖЕННОМУ документу типа Storage """

    positions_count = IntField(verbose_name='Количество позиций в документе')
    date = DateTimeField(
        default=datetime.now,
        verbose_name='Дата документа'
    )
    warehouse = ObjectIdField(
        verbose_name='Склад, на котором осуществляется операция'
    )
    number = StringField(verbose_name='Номер складского документа')


class StorageDocInEmbedded(EmbeddedDocument, StorageEmbeddedMixin):
    id = ObjectIdField(db_field='_id', default=ObjectId)
    _type = ListField(StringField(), default=["StorageDocIn", "StorageDoc"])
    doc_type = StringField(
        choices=(
            ('invoucher', 'приходный ордер'),
        ),
        default='invoucher',
        verbose_name='Тип документа'
    )


class StorageDocOutEmbedded(EmbeddedDocument, StorageEmbeddedMixin):
    id = ObjectIdField(db_field='_id', default=ObjectId)
    _type = ListField(StringField(), default=["StorageDocOut", "StorageDoc"])
    request = ObjectIdField(
        verbose_name='Если тип документа «заявка», ссылка на нее'
    )
    doc_type = StringField(
        choices=(
            ('request', 'заявка'),
            ('voucher', 'расходный ордер')
        ),
        verbose_name='Тип документа'
    )


class StorageDocOut(
    Document,
    StorageEmbeddedMixin,
    StorageMixin,
    BindedModelMixin
):
    """ Складской документ на выбытие материалов """

    meta = {
        'db_alias': 'legacy-db',
        'collection': 'AccountingDocument',
    }
    _type = ListField(StringField(), default=["StorageDocOut", "StorageDoc"])
    request = ObjectIdField(
        verbose_name='Если тип документа «заявка», ссылка на нее'
    )
    doc_type = StringField(
        choices=(
            ('request', 'заявка'),
            ('voucher', 'расходный ордер')
        ),
        verbose_name='Тип документа'
    )
    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации'
    )

    def _get_providers_binds(self):
        return [self.provider]

    def save(self, *args, **kwargs):
        self._denormalize_fields()
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        super().save(*args, **kwargs)

    def _denormalize_fields(self):
        """
        Денормализация полей
        operations
        """
        from app.requests.models.request import Request

        # Общее количество позиций в документе
        self.positions_count = len(self.operations)
        if not self.doc_type:
            self.doc_type = 'request' if self.request else 'voucher'
        if self.request:
            request = Request.objects(pk=self.request).first()
            if request:
                request.storage_docs = True
                request.save()

    def delete(self, signal_kwargs=None, **write_concern):
        from app.requests.models.request import Request
        if self.request:
            storage_doc = StorageDocOut.objects(request=self.request).first()
            if not storage_doc:
                request = Request.objects(pk=self.request).first()
                request.storage_docs = False
                request.save()
        return super().delete(signal_kwargs=None, **write_concern)


class StorageDocIn(
    BindedModelMixin,
    StorageEmbeddedMixin,
    StorageMixin,
    Document,
):
    """ Складской документ на выбытие материалов """

    meta = {
        'db_alias': 'legacy-db',
        'collection': 'AccountingDocument',
    }
    _type = ListField(StringField(), default=["StorageDocIn", "StorageDoc"])
    doc_type = StringField(
        choices=(
            ('invoucher', 'приходный ордер'),
        ),
        verbose_name='Тип документа',
        default='invoucher',
    )
    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации'
    )

    def _get_providers_binds(self):
        return [self.provider]

    def save(self, *args, **kwargs):
        self._denormalize_fields()
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        super().save(*args, **kwargs)

    def _denormalize_fields(self):
        self.positions_count = len(self.operations)


class ServicePositionEmbedded(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    nds = FloatField(verbose_name='Сумма НДС', null=True)
    sum = IntField(
        verbose_name='Подтвержденное количество умноженное на цену'
    )
    total = IntField(verbose_name='Сумма итого с учетом НДС')
    price = IntField(verbose_name='Цена, установленная за единицу материала')
    amount = FloatField(verbose_name='Объем выполненных работ')
    service = ObjectIdField(verbose_name='Материал из справочника')


class CompletionAct(StorageMixin, BindedModelMixin, Document):
    """ Акт о выполненных работах """

    meta = {
        'db_alias': 'legacy-db',
        'collection': 'AccountingDocument',
    }

    _type = ListField(StringField(), default=["CompletionAct"])
    date = DateTimeField(default=datetime.now, verbose_name='Дата документа')
    number = StringField(verbose_name='Номер складского документа')
    request = ObjectIdField(
        verbose_name='Ссылка на заявку, на основании которой формировался акт'
    )
    use_nds = BooleanField(
        required=True,
        default=False,
        verbose_name='в т.ч. НДС 18%'
    )
    positions = EmbeddedDocumentListField(
        ServicePositionEmbedded,
        verbose_name='Операции над позициями документа'
    )
    positions_count = IntField(verbose_name='Количество позиций в документе')
    run = BooleanField(verbose_name="Проведён", default=True)

    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации'
    )

    def _get_providers_binds(self):
        return [self.provider]

    def save(self, *args, **kwargs):
        self._denormalize_fields()
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        super().save(*args, **kwargs)

    def delete(self, signal_kwargs=None, **write_concern):
        from app.requests.models.request import Request
        if self.request:
            service_doc = CompletionAct.objects(request=self.request).first()
            if not service_doc:
                request = Request.objects(pk=self.request).first()
                request.service_doc = False
                request.save()
        return super().delete(signal_kwargs=None, **write_concern)

    def _denormalize_fields(self):
        """
        Денормализация полей
        operations
        """
        from app.requests.models.request import Request

        # Общее количество позиций в документе
        self.positions_count = len(self.positions)
        if self.request:
            request = Request.objects(pk=self.request).first()
            request.service_doc = True
            request.save()


class StorageMovement(Document):
    """
    Перемещение материала между складами
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'StorageMovement',
    }

    number = StringField(verbose_name='Номер транзакции')
    doc_in = EmbeddedDocumentField(
        StorageDocInEmbedded,
        verbose_name='Документ на поступление материала'
    )
    doc_out = EmbeddedDocumentField(
        StorageDocOutEmbedded,
        verbose_name='Документ на выбытие материала'
    )
    comment = StringField(verbose_name='Комментарий к транзакции')
    account = ObjectIdField(verbose_name='Работник, создавший документ')
    provider = ObjectIdField(verbose_name='Организация-владелец')
    datetime = DateTimeField(
        default=datetime.now,
        verbose_name='Дата/время создания транзакции'
    )

    def save(self, *args, **kwargs):
        self._denormalize_fields()
        super().save(*args, **kwargs)

    def _denormalize_fields(self):
        """
        Денормализация полей
        date, number, warehouse, positions_count
        """
        pass


class Catalogue(DynamicDocument):
    """
    Метериалы
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Catalogue',
    }
