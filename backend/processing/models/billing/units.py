from mongoengine.document import Document, EmbeddedDocument
from mongoengine.fields import StringField, EmbeddedDocumentField, \
    BooleanField, ListField

from processing.models.billing.base import BindedModelMixin, ModelMixin


class OkeiUnitLocalization(EmbeddedDocument):
    ru = StringField()
    int = StringField()


class OkeiUnit(Document, ModelMixin):  # BindedModelMixin
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'OkeiUnit',
    }

    # Код
    code = StringField('\d*')

    # Полное наименование еденицы измерения
    title = StringField(min_length=1)

    # Условные обозначения
    cond_name = EmbeddedDocumentField(OkeiUnitLocalization)

    # Кодовые обозначения
    code_name = EmbeddedDocumentField(OkeiUnitLocalization)
    _type = ListField()
    is_deleted = BooleanField(required=False)

    def save(self, *args, **kwargs):
        changed_fields = self._is_triggers(['code', 'cond_name', '_type'])
        result = super().save(*args, **kwargs)
        if not changed_fields:
            return result
        for field in changed_fields:
            self.foreign_denormalize(field)
        return result

    def foreign_denormalize(self, changed_field):
        from app.caching.tasks.denormalization import \
            foreign_denormalize_data
        foreign_denormalize_data(
            model_from=OkeiUnit,
            field_name=changed_field,
            object_id=self.pk,
        )


if __name__ == '__main__':
    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()
    ou = OkeiUnit.objects.all()
    print(ou)
