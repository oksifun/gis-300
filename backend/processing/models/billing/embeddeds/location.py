from mongoengine import EmbeddedDocument, StringField, EmbeddedDocumentField, \
    ObjectIdField, DynamicField, ListField, DictField
from .geo_point import GeoPoint


class Location(EmbeddedDocument):
    location = StringField()
    house_number = StringField()
    area_number = StringField(null=True,
                              default=None)
    postal_code = StringField(regex='\d{6,6}')
    fias_addrobjs = ListField(StringField())
    fias_house_guid = StringField(verbose_name="Ссылка на HOUSEGUID в ФИАС",
                                  null=True,
                                  default=None)
    fias_street_guid = StringField(verbose_name="Ссылка на AOGUID в ФИАС")
    point = EmbeddedDocumentField(GeoPoint, verbose_name="Гео-координата")
    extra = DictField()

    # ненужные поля
    id = ObjectIdField(db_field="_id")

    @property
    def full(self) -> str:

        return ', '.join(part.strip() for part in [
            self.postal_code, self.location,
            self.house_number, self.area_number
        ] if isinstance(part, str) and len(part.strip()) > 0)
