from mongoengine import Document, StringField, ListField, ObjectIdField

from processing.models.billing.account import Tenant
from processing.models.choices import GenderType, GENDER_TYPE_CHOICES


class FamilyRoleCatalogue(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'FamilyRoleCatalogue',
    }
    title = StringField()
    reverse_links = ListField(ObjectIdField())
    sex = StringField(choices=GENDER_TYPE_CHOICES, default=GenderType.MALE)

    @classmethod
    def get_family_roles(cls, tenants):
        """
        Получение родственных связей для переданных жителей
        :param tenants: [ObjectId, ...] - список ID жителей
        :return dict: ключи - ID жителей, в которых указаны ID родственников
                      и их роль.
        Пример:
        {
            ID переданного жителя: {
                ID сожителя: {
                    'role': ID роли,
                    'title': 'Название роли'
                    },
                ID сожителя: {
                    'role': ID роли,
                    'title': 'Название роли'
                    },
            },
            ID переданного жителя: {
                ID сожителя: {
                    'role': ID роли,
                    'title': 'Название роли'
                    },
            }
        }
        """
        fields = 'family', 'id'
        tenants = Tenant.objects(id__in=tenants).only(*fields).as_pymongo()
        tenants = [
            tenant
            for tenant in tenants
            if tenant.get('family', {}).get('relations')
        ]
        roles_ids = [
            x['role']
            for tenant in tenants
            for x in tenant['family']['relations']
            if x.get('role')
        ]
        fields = 'title', 'id'
        family_roles = cls.objects(id__in=roles_ids).only(*fields).as_pymongo()
        family_roles = {x['_id']: x for x in family_roles}
        results = {}
        for tenant in tenants:
            roles = {
                x['related_to']: dict(
                    title=family_roles[x['role']]['title'],
                    role=family_roles[x['role']]['_id']
                )
                for x in tenant['family']['relations']
                if x.get('role')
            }
            results.update({tenant['_id']: roles})
        return results

