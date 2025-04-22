from mongoengine import EmbeddedDocument, StringField, ListField, FloatField, \
    ObjectIdField


class GeoPoint(EmbeddedDocument):
    DEFAULT_COORDINATES = [59.9386, 30.3141]
    API_KEY = '818f77f0-598a-4112-b5d7-fcf014a5fc49'

    id = ObjectIdField(db_field="_id", null=True)
    geo_point_type = StringField(db_field='type', default='Point', required=True)
    coordinates = ListField(
        FloatField(),
        null=True,
        verbose_name="Долгота, Широта"
    )

    @staticmethod
    def get_geocode(address):
        from requests import get as requests_get

        url = 'https://geocode-maps.yandex.ru/1.x/'
        params = {
            'apikey': GeoPoint.API_KEY,
            'geocode': address,
            'format': 'json',
            'results': 1,
        }
        response = requests_get(url=url, params=params, timeout=10).json()
        if not response.get('response'):
            return GeoPoint.DEFAULT_COORDINATES
        geo_point = (
            response['response']['GeoObjectCollection']
            ['featureMember'][0]['GeoObject']['Point']['pos'].split(' ')
        )
        return list(map(float, geo_point))

    @classmethod
    def create_by_address_str(cls, address_str):
        try:
            return cls(coordinates=cls.get_geocode(address_str))
        except Exception:
            return cls(coordinates=GeoPoint.DEFAULT_COORDINATES)
