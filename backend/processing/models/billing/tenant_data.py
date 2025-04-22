from mongoengine import Document, \
    EmbeddedDocumentListField, EmbeddedDocumentField, \
    StringField, EmbeddedDocument, IntField, DateTimeField, ObjectIdField

from processing.models.billing.account import Tenant
from processing.models.billing.base import BindedModelMixin, HouseGroupBinds
from processing.models.billing.files import Files
from processing.models.choice.privilege import PRIVILEGE_DOCUMENT_TYPES_CHOICES


class TenantPassport(EmbeddedDocument):
    series = StringField(default='')
    number = StringField(default=None, null=True)
    date = DateTimeField(default=None, null=True)
    issuer = StringField(default='')
    issuer_code = StringField(default='')


class TenantIdDocument(EmbeddedDocument):
    id = ObjectIdField(db_field='_id')
    doc_type = StringField()
    custom_name = StringField()
    series = StringField()
    number = StringField()
    date = DateTimeField()
    date_till = DateTimeField(null=True)
    issuer = StringField()


class TenantPrivilegeDocument(EmbeddedDocument):
    privilege = ObjectIdField()
    doc_type = StringField(choises=PRIVILEGE_DOCUMENT_TYPES_CHOICES)
    custom_name = StringField(null=True)
    series = StringField()
    number = StringField()
    date_from = DateTimeField()
    date_till = DateTimeField()
    issuer = StringField()
    file = EmbeddedDocumentField(Files, null=True)


class TenantData(Document, BindedModelMixin):
    """
    Подробные данные жителя
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'TenantData',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.hg',
        ],
    }

    tenant = ObjectIdField(verbose_name='Житель')
    passport = EmbeddedDocumentField(
        TenantPassport,
        required=True,
        default=None,
    )
    id_docs = EmbeddedDocumentListField(TenantIdDocument)
    privilege_docs = EmbeddedDocumentListField(TenantPrivilegeDocument)
    _binds = EmbeddedDocumentField(
        HouseGroupBinds,
        verbose_name='Привязки к организации и группе домов (P,HG и D)'
    )

    def save(self, *args, **kwargs):
        if self._created:
            tenant = Tenant.objects(pk=self.tenant).get()
            self._binds = tenant._binds
        return super().save(*args, **kwargs)

    @classmethod
    def process_house_binds(cls, house_id):
        query = dict(area__house__id=house_id)
        accounts = Tenant.objects(**query).only('id', '_binds').as_pymongo()
        # Сгруппируем аккаунты по группам домов
        groups = {}
        for acc in accounts:
            default = dict(accounts=[], hg=acc['_binds'])
            group = groups.setdefault(tuple(acc['_binds']['hg']), default)
            group['accounts'].append(acc['_id'])
        # Проапдейтим группы
        for group in groups.values():
            query = dict(tenant__in=group['accounts'])
            updater = dict(set___binds=group['hg'])
            cls.objects(**query).update(**updater)


