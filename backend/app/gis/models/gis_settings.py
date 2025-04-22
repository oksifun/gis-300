from mongoengine import Document, EmbeddedDocument, ValidationError, \
    IntField, StringField, ObjectIdField, BooleanField, EmbeddedDocumentField

from app.gis.models.guid import GUID
from app.gis.models.nsi_ref import nsiRef

from app.gis.utils.nsi import NSI_GROUP

from processing.models.billing.service_type import \
    ServiceTypeGisBind, ServiceTypeGisName


class StatusField(EmbeddedDocument):
    status = StringField(default='new')
    identifier = BooleanField(default=False)

    def get_identifier(self):
        return self.identifier


class GisSettings(Document):

    meta = {
        'db_alias': 'legacy-db',
        'collection': 'GisSettings',
        'auto_create_index': False,
        'index_background': True,
        'indexes': [
            'provider',
        ]
    }

    provider = ObjectIdField(required=True)

    service_comparison = BooleanField(
        verbose_name='Сопоставлена ли хоть одна услуга',
    )
    import_org_registry = EmbeddedDocumentField(
        StatusField,
        verbose_name="Импорт идентификатора организации из ГИС ЖКХ",
    )
    import_group_nsi = EmbeddedDocumentField(
        StatusField,
        verbose_name='Импорт общих справочников из ГИС ЖКХ',
    )
    import_provider_nsi = EmbeddedDocumentField(
        StatusField,
        default=StatusField(),
        verbose_name='Импорт частных справочников из ГИС ЖКХ',
    )

    export_house = StringField(
        default='new',
        verbose_name='Экспорт домов в ГИС ЖКХ'
    )
    export_pd = StringField(
        default='new',
        verbose_name='Экспорт ПД в ГИС ЖКХ'
    )

    import_provider_documents = StringField(
        default='new',
        verbose_name='Импорт документов провайдера из ГИС ЖКХ'
    )
    import_houses = StringField(
        default='new',
        verbose_name='Импорт данных домов из ГИС ЖКХ'
    )

    export_provider_nsi = StringField(
        default='new',
        verbose_name='Экспорт справочников организации в ГИС ЖКХ'
    )

    import_provider_tenants = StringField(
        default='new',
        verbose_name='Импорт лицевых счетов из ГИС ЖКХ'
    )

    export_only_tenants = StringField(
        default='new',
        verbose_name='Экспорт лицевых счетов в ГИС ЖКХ'
    )

    import_house_meters = StringField(
        default='new',
        verbose_name='Импорт ПУ из ГИС ЖКХ'
    )
    export_provider_meters = StringField(
        default='new',
        verbose_name='Экспорт ПУ в ГИС ЖКХ'
    )
    import_readings = StringField(
        default='new',
        verbose_name='Импорт показаний ПУ из ГИС'
    )

    export_readings = StringField(
        default='new',
        verbise_name='Экспорт показаний ПУ в ГИС ЖКХ'
    )

    progress_bar = IntField()

    @classmethod
    def set_status(cls, provider, status, method):
        update_request = {
            method: status
        }
        query = dict(provider=provider) if provider else {}
        cls.objects(**query).update(**update_request)

    def save(self, *args, **kwargs):
        if self._created:
            GisSettings.check_duplicated(self.provider)
        if not kwargs.get('hard_save'):
            self.fill_provider_identifier()
            self.set_general()
            self.check_service_comparison()
            self.update_progress_bar()
            self.check_personal_directories()
        return super().save(*args, **kwargs)

    @classmethod
    def check_duplicated(cls, provider_id):
        if cls.objects(provider=provider_id).as_pymongo().first():
            raise ValidationError(
                f'Настройка с оранизацией {provider_id} уже сущесвует'
            )

    def check_service_comparison(self):
        service_bind = ServiceTypeGisBind.objects(
            provider=self.provider,
            closed=None,
        ).as_pymongo().only('id').first()
        self.service_comparison = True if service_bind else False

    def fill_provider_identifier(self):
        gis = GUID.objects(object_id=self.provider).as_pymongo().first()

        self.import_org_registry = StatusField(
            identifier=bool(gis),
            status='finished' if bool(gis) else 'new'
        )

    def set_general(self):
        if not self._created:
            return
        identifier = False
        status = 'new'
        if GisSettings.check_nsi():
            identifier = True,
            status = 'finished',
        self.import_group_nsi = StatusField(
            identifier=identifier,
            status=status,
        )

    def check_personal_directories(self):

        if ServiceTypeGisName.references(self.provider):
            status = 'finished'
            identifier = True
        else:
            status = 'new'
            identifier = False
        self.import_provider_nsi.status = status
        self.import_provider_nsi.identifier = identifier

    @classmethod
    def check_nsi(cls):
        aggregation_pipeline = [
            {'$match': {
                'reg_num': {'$in': [*NSI_GROUP]}
            }},
            {'$group': {
               '_id': '$reg_num'
            }}
        ]
        count = list(nsiRef.objects.aggregate(*aggregation_pipeline))
        return len(NSI_GROUP) == len(count)

    def update_progress_bar(self):
        fields = ['service_comparison', 'import_group_nsi',
                  'import_provider_nsi', 'import_org_registry']

        fill_fields = []
        for field in fields:
            field = getattr(self, field, None)
            if not field:
                continue
            if (
                not isinstance(field, EmbeddedDocument)
                or (isinstance(field, EmbeddedDocument)
                    and field.get_identifier())
            ):
                fill_fields.append(field)

        self.progress_bar = len(fill_fields) / (len(fields)) * 100
        print(self.progress_bar)
