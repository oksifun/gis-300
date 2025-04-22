import datetime

from bson import ObjectId

from mongoengine import Document, ObjectIdField, StringField, ListField, \
    BooleanField

# from app.rosreestr.tasks.compraison_params import statistic_for_house_in_cache


class HouseGroup(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'HouseGroup',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            'provider',
            'houses'
        ]
    }
    provider = ObjectIdField()
    title = StringField()
    houses = ListField(ObjectIdField())
    hidden = BooleanField()
    is_total = BooleanField(default=False)
    is_deleted = BooleanField()

    def save(self, *args, **kwargs):
        if self.hidden is None:
            self.hidden = True
        if self.title is None:
            self.title = f"Домов: {len(self.houses)}"
        super().save(*args, **kwargs)
        # if self.is_total:
        #     statistic_for_house_in_cache.delay(
        #         self.houses, deleted=True, provider_id=self.provider
        #     )

    @staticmethod
    def clean_group_from_data(hg_id, logger=None):
        from processing.models.billing.account import Tenant
        from app.area.models.area import Area
        from processing.models.billing.tenant_data import TenantData
        from app.meters.models.meter import AreaMeter, HouseMeter
        from app.house.models.house import House
        from app.accruals.models.accrual_document import AccrualDoc
        from app.requests.models.request import Request
        models = (
            Tenant,
            Area,
            TenantData,
            AreaMeter,
            HouseMeter,
            House,
            AccrualDoc,
            Request,
        )
        updated_number = 0
        for model in models:
            if logger:
                logger(datetime.datetime.now(), model.__name__)
            updated_number += model.objects(
                _binds__hg=hg_id,
            ).update(
                __raw__={
                    '$pull': {
                        '_binds.hg': hg_id,
                    },
                },
            )
        return updated_number

    @classmethod
    def get_or_create(cls, provider_id: ObjectId, *house_id_s: ObjectId,
            is_total: bool = None) -> ObjectId or None:

        if not house_id_s:  # список домов пуст?
            return None  # TODO не создаем пустые группы домов?

        sorted_houses: list = sorted(house_id_s)  # порядок важен при поиске

        query: dict = {
            'provider': provider_id,  # индекс
            'houses': sorted_houses,  # индекс
            'hidden': True,
        }
        if is_total is not None:
            query['is_total'] = is_total

        house_group: HouseGroup = cls.objects(__raw__=query).first()
        if house_group is None:
            house_group = cls(**query)
            if is_total is True:
                house_group.title = "Все дома"
            house_group.save()

        return house_group.id
