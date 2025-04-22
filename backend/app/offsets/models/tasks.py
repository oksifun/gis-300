from mongoengine import DateTimeField, ListField, StringField, ReferenceField, \
    ObjectIdField

from processing.data_producers.associated.base import get_binded_houses
from processing.models.billing.account import Tenant
from processing.models.choices import ACCRUAL_SECTOR_TYPE_CHOICES, \
    AccrualsSectorType
from processing.models.tasks.base import RequestTask, TaskStatus
from app.offsets.core.run_tasks import run_calculator


class OffsetRequestTask(RequestTask):
    """
    Задача оставлена для того, что бы была возможность создавать задачи на
    пересчет через админку которую делал Богдан. Офсеты считаются на celery
    """

    on_date = DateTimeField()
    sectors = ListField(
        StringField(choices=ACCRUAL_SECTOR_TYPE_CHOICES,
                    default=AccrualsSectorType.RENT, required=True)
    )

    provider = ReferenceField('processing.models.billing.Provider',
                              verbose_name="Организация", required=True)

    houses = ListField(ObjectIdField(), verbose_name="Список домов")

    tenants = ListField(ObjectIdField(), verbose_name="Житель")

    def process(self, *args, **kwargs):
        self.save()

    def _run_celery(self):
        if len(self.tenants) > 0:
            tenants = self.tenants
        elif self.houses and len(self.houses) > 0:
            tenants = Tenant.objects(
                area__house__id__in=self.houses,
            ).distinct('id')
        else:
            provider_houses = get_binded_houses(self.provider.id)
            tenants = Tenant.objects(
                area__house__id__in=provider_houses,
            ).distinct('id')

        pairs = []

        for tenant in tenants:
            for sector in self.sectors:
                pair = [
                    tenant,
                    sector,
                    self.provider.id if self.provider else None
                ]
                pairs.append(pair)

        for pair in pairs:
            run_calculator(pair)

    def save(self, *args, **kwargs):
        self.status = TaskStatus.DONE

        self._run_celery()
        return super().save(*args, **kwargs)