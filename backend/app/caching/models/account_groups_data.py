from datetime import datetime, timedelta

from mongoengine.base.fields import ObjectIdField
from mongoengine.document import Document, EmbeddedDocument
from mongoengine.fields import ReferenceField, FloatField, \
    IntField, StringField, EmbeddedDocumentListField, DateTimeField

from processing.models.billing.account import Account
from processing.models.billing.accrual import Accrual
from app.accruals.models.accrual_document import AccrualDoc
from processing.models.billing.provider.main import Provider
from processing.models.billing.service_type import ServiceType
from app.caching.models.account_groups import WorkersFIOGroup


class WorkerGroupInfo(EmbeddedDocument):
    id = ObjectIdField(db_field="_id")

    provider_str = StringField()
    position_name = StringField()
    position_code = StringField()
    worker_str = StringField()

    worker = ObjectIdField()
    provider = ObjectIdField()


class WorkersFIOGroupData(Document):
    meta = {
        'db_alias': 'cache-db',
        'collection': 'worker_fio_group_data_cache',
    }

    group = ReferenceField(
        'processing.models.cache.worker_group.WorkersFIOGroup')

    year = IntField(min_value=1900, max_value=3000)

    # recalculate_data()
    data_updated = DateTimeField()
    group_info = EmbeddedDocumentListField(WorkerGroupInfo)
    area_sum = FloatField(min_value=0)
    accounts_num = IntField(min_value=0)

    area_rating_position = None

    @staticmethod
    def is_outdated(year, group_code):

        return (

            WorkersFIOGroupData.objects(
                year=year,
                group__in=WorkersFIOGroup.objects(group_code=group_code),
            ).count() < 1

            or

            WorkersFIOGroupData.objects(
                year=year,
                group__in=WorkersFIOGroup.objects(group_code=group_code),
                data_updated__lt=datetime.utcnow() - timedelta(hours=1)
            ).count() > 0

        )

    @staticmethod
    def rebuild_groups_data(groups, year):

        return [
            WorkersFIOGroupData(
                group=group,
                year=year
            ).recalculate_data()
            for group in groups
        ]

    @staticmethod
    def get_groups_data(groups, year):

        groups_data = list(
            WorkersFIOGroupData.objects(
                group__in=groups,
                year=year
            )
        )

        groups_without_data = set(
            set((group.id for group in groups))
            -
            set((g_data.group.id for g_data in groups_data))
        )

        if groups_without_data:
            for group in groups_without_data:
                groups_data.append(
                    WorkersFIOGroupData(
                        group=group,
                        year=year
                    ).recalculate_data()
                )

        return groups_data

    def recalculate_data(self):

        self.area_sum = 0
        self.accounts_num = 0

        target_service_type = ServiceType.objects(code='housing').first()

        group_workers = [
            Account.objects.get(id=worker)
            for worker in self.group.workers
        ]

        group_providers = Provider.objects(
            id__in=[worker.provider.id for worker in group_workers]
        )

        accrual_docs = AccrualDoc.objects(
            date_from=datetime(self.year, 6, 1),
            provider__in=group_providers,
        )

        #
        accruals_area_sum = list(Accrual.objects.aggregate(
            *[
                {
                    '$match': {
                        'doc._id': {
                            '$in': [
                                accrual_doc.id
                                for accrual_doc in accrual_docs
                            ]
                        }
                    }
                },
                {
                    '$unwind': '$services'
                },
                {
                    '$match': {
                        'services.service_type': target_service_type.id,
                    }
                },
                {
                    '$group': {
                        '_id': None,
                        'accrual': {'$addToSet': '$_id'},
                        'area': {
                            '$sum': {
                                '$cond': {
                                    'if': {'$gt': ['$services.tariff', 0]},
                                    'then': {
                                        '$divide': [
                                            '$services.value',
                                            '$services.tariff',
                                        ],
                                    },
                                    'else': {'$literal': 0},
                                },
                            },
                        },
                        'count': {'$sum': 1},
                    }
                }
            ]
        ))

        if accruals_area_sum:
            self.area_sum = round(accruals_area_sum[0]['area'])
            not_null_providers = Accrual.objects(
                id__in=accruals_area_sum[0]['accrual'],
                services__value__gt=0
            ).distinct('doc.provider')

        else:
            self.area_sum = 0
            not_null_providers = []

        # Количество аккаунтов -
        # это количество Accrual во всех AccrualDoc за июнь
        self.accounts_num += Accrual.objects(
            doc__id__in=[accrual_doc.id for accrual_doc in accrual_docs]
        ).count()

        self.group_info = [
            WorkerGroupInfo(
                provider_str=worker.provider.str_name,
                provider=worker.provider.id,
                position_name=worker.position.name,
                position_code=worker.position.code,
                worker_str=worker.str_name,
                worker=worker.id
            )
            for worker in group_workers
            if worker.provider.id in not_null_providers
        ]

        self.data_updated = datetime.utcnow()

        WorkersFIOGroupData.objects(
            group=self.group,
            year=self.year
        ).delete()

        self.save()

        return self

    def get_area_rating_position(self, year, group_code):

        return WorkersFIOGroupData.objects(
            year=year,
            group__in=WorkersFIOGroup.objects(group_code=group_code),
            area_sum__gt=self.area_sum
        ).count() + 1

    def get_rating_position_by(self, field_name):

        if not hasattr(self, field_name):
            raise AttributeError('{} object has no attribute "{}"'.format(
                self,
                field_name
            ))

        return WorkersFIOGroupData.objects(
            **{
                field_name + '__gt': getattr(self, field_name)
            }
        ).count() + 1

    def serialize(self):

        return dict(
            group=str(self.group.id),
            data_updated=self.data_updated,
            area_sum=self.area_sum,
            accounts_num=self.accounts_num,
            group_info=[
                dict(
                    provider_str=group_info_entry.provider_str,
                    provider_id=str(group_info_entry.provider),
                    position_name=group_info_entry.position_name,
                    position_code=group_info_entry.position_code,
                    worker_str=group_info_entry.worker_str,
                    worker_id=str(group_info_entry.worker),
                )
                for group_info_entry in self.group_info
            ]
        )


