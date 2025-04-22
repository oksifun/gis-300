import datetime

from dateutil.relativedelta import relativedelta
from mongoengine import Document, EmbeddedDocumentField, ObjectIdField, \
    DateTimeField

from processing.models.billing.base import BindedModelMixin, ProviderBinds


class TenantRate(BindedModelMixin, Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'TenantRate',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('tenant', '_binds.pr', 'worker', 'created'),
        ],
    }
    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации',
    )
    provider = ObjectIdField()
    worker = ObjectIdField()
    tenant = ObjectIdField()
    created = DateTimeField(default=datetime.datetime.now)

    @classmethod
    def vote_up_tenant(cls, binds, worker_id, tenant_id, provider_id):
        return cls._vote_tenant(binds, worker_id, tenant_id, provider_id, 1)

    @classmethod
    def vote_down_tenant(cls, binds, worker_id, tenant_id, provider_id):
        return cls._vote_tenant(binds, worker_id, tenant_id, provider_id, -1)

    @classmethod
    def _vote_tenant(cls, binds, worker_id, tenant_id, provider_id, rate=1):
        from processing.models.billing.account import Tenant
        tenant_queryset = Tenant.objects(
            Tenant.get_binds_query(binds),
            pk=tenant_id,
        )
        tenant = tenant_queryset.only('rating').as_pymongo().first()
        if not tenant:
            return None
        if 'rating' not in tenant:
            tenant_queryset.update(rating=0)
            tenant['rating'] = 0
        if not cls.worker_can_rate_tenant(worker_id, tenant_id, binds):
            return None
        cls(
            worker=worker_id,
            tenant=tenant_id,
            provider=provider_id,
        ).save()
        tenant_queryset.update(
            inc__rating=rate,
        )
        return tenant['rating'] + rate

    @classmethod
    def worker_can_rate_tenant(cls, worker_id, tenant_id, binds):
        result = cls._get_worker_queryset(
            worker_id,
            tenant_id,
            binds,
        ).filter(
            created__gt=datetime.datetime.now() - relativedelta(hours=24),
        ).only(
            'id',
        ).as_pymongo().first()
        return not bool(result)

    @classmethod
    def _get_worker_queryset(cls, worker_id, tenant_id, binds):
        return cls.objects(
            cls.get_binds_query(binds),
            worker=worker_id,
            tenant=tenant_id,
        )
