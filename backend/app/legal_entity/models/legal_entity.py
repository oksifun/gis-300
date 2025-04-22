from datetime import datetime

from mongoengine import Document, DateTimeField, StringField, EmbeddedDocument,\
    EmbeddedDocumentListField, EmbeddedDocumentField

from processing.models.billing.embeddeds.phone import DenormalizedPhone

from .core import LegalEntityBankAccountEmbedded, \
    LegalEntityDetailsEmbedded


class CurrentDetails(EmbeddedDocument):
    current_name = StringField(verbose_name='Текущее наименование')
    current_inn = StringField(verbose_name='Текущий ИНН')
    created = DateTimeField()
    closed = DateTimeField()


class LegalEntity(Document):
    """
    Юридичесие лица
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntity',
    }
    bank_account = EmbeddedDocumentListField(
        LegalEntityBankAccountEmbedded,
        verbose_name='Расчётные счета'
    )
    details = EmbeddedDocumentListField(
        LegalEntityDetailsEmbedded,
        required=True,
        verbose_name='Реквизиты',
    )
    phones = EmbeddedDocumentListField(
        DenormalizedPhone, verbose_name="Список телефонов")
    ogrn = StringField(required=True, verbose_name='ОГРН')
    current_details = EmbeddedDocumentField(
        CurrentDetails,
        verbose_name='Текущие реквизиты'
    )
    created = DateTimeField(default=datetime.now)

    def save(self, *args, **kwargs):
        self.get_current_details()
        super().save(*args, **kwargs)

    def update(self, **kwargs):
        super().update(
            current_details=self.get_current_details(),
            **kwargs
        )

    def get_current_details(self):
        current_details = CurrentDetails(
            current_name=self.details[-1].full_name,
            current_inn=self.details[-1].inn,
            created=self.details[-1].created,
            closed=self.details[-1].closed,
        )
        if self._created:
            current_details.date_from = self.details[-1].created
        self.current_details = current_details
        return self.current_details

    @classmethod
    def create_new_by_inn(cls, inn, name, date_from=None):
        entity = cls(
            ogrn='',
            created=datetime.now(),
            details=[LegalEntityDetailsEmbedded(
                date_from=datetime.now() if not date_from else date_from,
                full_name=name,
                short_name=name,
                legal_form='',
                inn=inn,
                created=datetime.now(),
            )]
        )
        entity.save()
        return entity

    @classmethod
    def get_or_create(cls, tenant) -> 'LegalEntity':

        from processing.models.billing.account import Tenant
        assert isinstance(tenant, Tenant)

        now = datetime.now()

        entity = LegalEntity.objects(id=tenant.entity).first() \
            if tenant.entity else None
        if entity is None:
            if tenant.ogrn:
                entity = LegalEntity.objects(ogrn=tenant.ogrn).first()
            if entity is None and tenant.inn:
                entity = LegalEntity.objects(details__inn=tenant.inn).first()

        if entity is None:
            entity = cls(
                ogrn=tenant.ogrn or '',  # required
                created=now,
                details=[]
            )
        elif tenant.ogrn and entity.ogrn != tenant.ogrn:  # ОГРН?
            entity.ogrn = tenant.ogrn

        details = next((d for d in entity.details if not d.closed), None)
        if details and (not tenant.inn or details.inn != tenant.inn):  # ИНН?
            details.closed = now  # неактуальные реквизиты
            details = None  # будет создан новый элемент

        if not details:
            details = LegalEntityDetailsEmbedded(
                date_from=now,
                full_name=tenant.str_name,
                short_name=tenant.name,  # short_name = str_name
                legal_form=tenant.legal_form,
                inn=tenant.inn or '',  # required
                created=now,
            )
            entity.details.append(details)  # добавляем в конец

        entity.save()
        return entity
