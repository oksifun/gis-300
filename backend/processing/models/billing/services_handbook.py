from mongoengine import Document, StringField, ListField, \
    EmbeddedDocumentListField, EmbeddedDocument, IntField, ObjectIdField

from processing.models.billing.own_contract import AGREEMENT_SERVICE_OBJECTS, \
    CONTRACT_OWNERS


class DefaultCostEmbedded(EmbeddedDocument):
    region_codes = ListField(StringField(), verbose_name='Коды регионов')
    price = IntField(verbose_name='Цена (копейки)')
    obj = StringField(
        verbose_name='Объект применения цены',
        choices=AGREEMENT_SERVICE_OBJECTS
    )


class OwnServiceHandbook(Document):
    """Справочник услуг"""
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'OwnServiceHandbook'
    }
    owner = ObjectIdField(verbose_name='ID организации хозяина')
    name = StringField(verbose_name='Наименование')
    description = StringField(verbose_name='Описание')
    default_cost = EmbeddedDocumentListField(
        DefaultCostEmbedded,
        verbose_name='Цена по умолчанию для регионов',
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        need_send = self.set_send_flag()
        result = super().save(*args, **kwargs)
        if need_send:
            self.send_handbook()
        return result

    def set_send_flag(self):
        """
        Установка флага потребности сопоставления номенклатуры после сохранения
        """
        if (
                self._created
                or 'name' in self._changed_fields
                or 'description' in self._changed_fields
        ):
            return True
        return False

    def send_handbook(self):
        """Передача справочника номенклатуры в 1C для двух организаций"""
        from processing.celery.tasks.swamp_thing.accounting_exchange import \
            send_nomenclatures

        owners = [o[0] for o in CONTRACT_OWNERS]
        for owner in owners:
            send_nomenclatures.delay(
                owner=owner,
                service_id=str(self.id),
                service_name=self.name,
                service_name_full=self.description,
            )

    def delete(self, *args, **kwargs):
        raise PermissionError("You shall not pass!!")
