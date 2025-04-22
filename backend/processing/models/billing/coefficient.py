from mongoengine import Document, StringField, DynamicField, \
    BooleanField, ListField, EmbeddedDocumentField, ObjectIdField

from processing.models.billing.base import ProviderBinds, BindedModelMixin, \
    CustomQueryMixin, RelationsProviderBindsProcessingMixin


class Coefficient(RelationsProviderBindsProcessingMixin,
                  BindedModelMixin,
                  Document,
                  CustomQueryMixin):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Coefficient',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('_binds.pr', 'title'),
        ],
    }
    title = StringField(required=True, verbose_name="Заголовок коэффициента")
    provider = ObjectIdField(
        required=True,
        verbose_name="Организация-владелец"
    )
    group = ObjectIdField(
        null=True,
        verbose_name="Входит в группу коэффициентов"
    )
    default = DynamicField(verbose_name="значение по-умолчанию")
    is_once = BooleanField(
        required=True,
        default=False,
        verbose_name="Распространяется только в пределах указанного месяца"
    )
    is_feat = BooleanField(
        required=True,
        default=False,
        verbose_name="Коэффициент является признаком"
    )
    is_deleted = BooleanField()
    _type = ListField(StringField())
    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации и группе домов (P)'
    )

    def delete(self, **write_concern):
        if not self.is_deleted:
            self.is_deleted = True
            self.save()
