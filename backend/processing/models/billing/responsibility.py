from datetime import datetime
from dateutil.relativedelta import relativedelta

from mongoengine import Document, EmbeddedDocumentField, \
    DateTimeField, ObjectIdField

from processing.data_producers.associated.tenants import \
    sync_responsibility_to_providers
from processing.models.billing.base import ModelMixin
from processing.models.billing.embeddeds.tenant import \
    DenormalizedTenantWithName


class Responsibility(Document, ModelMixin):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Responsibility',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            ('account.area.id', 'provider', 'date_from'),
        ],
    }

    account = EmbeddedDocumentField(
        DenormalizedTenantWithName,
        verbose_name="Житель",
    )
    provider = ObjectIdField(verbose_name="Организация")
    date_from = DateTimeField()
    date_till = DateTimeField(null=True)

    @property
    def is_actual(self) -> bool:
        """Актуальная запись об ответственности?"""
        return self.date_till is None or self.date_till < datetime.now()

    def save(self, *args, **kwargs):
        if self._is_triggers(['account']):
            self._account_denormalize()

        if self._is_triggers(['date_from', 'date_till']):  # включая _created
            from app.gis.models.gis_queued import GisQueued, QueuedType
            # ставим ЛС в очередь на выгрузку в ГИС ЖКХ
            GisQueued.export(QueuedType.TENANT,
                self.account.id, self.account.area.house.id)

        is_new = self._created
        result = super().save(*args, **kwargs)
        sync_responsibility_to_providers(
            self,
            only_from_udo=True,
            by_id=not is_new,
        )
        self.post_in_setl_home()

        return result

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        sync_responsibility_to_providers(self, only_from_udo=True)
        return result

    @classmethod
    def get_accounts(cls, provider_id, house_id=None,
            date_from: datetime = None, date_till: datetime = None) -> list:
        """
        Получить идентификаторы (ЛС) ответственных квартиросъемщиков
        """
        if not date_from:  # без даты начала ~ до текущего дня
            date_from = datetime.now() \
                .replace(hour=0, minute=0, second=0, microsecond=0)

        if not date_till:  # без даты окончания ~ TODO еще один месяц?
            date_till = date_from + relativedelta(months=1)

        query: dict = {'provider': provider_id}  # формируем запрос

        if house_id:  # определенный дом?
            query['account.area.house._id'] = house_id

        query['$and'] = [
            {'$or': [
                {'date_from': None},
                {'date_from': {'$lte': date_from}}
            ]},
            {'$or': [
                {'date_till': None},
                {'date_till': {'$gte': date_till}}
            ]}
        ]  # временной интервал ответственности

        return cls.objects(__raw__=query).distinct('account._id')  # ид. ЛС

    def _account_denormalize(self):
        from processing.models.billing.account import Tenant
        tenant = Tenant.objects(pk=self.account.id).get()
        self.account = DenormalizedTenantWithName.from_ref(tenant)

    def sync_responsibility(self, providers_to):
        actual_resp = Responsibility.objects(
            account__id=self.account.id,
            provider=self.provider,
        ).fields(
            id=0,
            date_from=1,
            date_till=1,
        ).as_pymongo()
        sync_resp = Responsibility.objects(
            account__id=self.account.id,
            provider__in=providers_to,
        )
        resp_for_update = {p: [] for p in providers_to}
        for resp in sync_resp:
            provider_resp = resp_for_update.setdefault(resp.provider, [])
            provider_resp.append(resp)
        for provider, responsibilities in resp_for_update.items():
            if len(responsibilities) < len(actual_resp):
                for ix, resp in enumerate(responsibilities):
                    resp_dict = actual_resp[ix]
                    Responsibility.objects(
                        pk=resp.id,
                    ).update(
                        __raw__={'$set': resp_dict},
                    )
                for resp in actual_resp[len(responsibilities):]:
                    resp['account'] = {'id': self.account.id}
                    resp['provider'] = provider
                    new_resp = Responsibility(**resp)
                    new_resp.save()
            else:
                for ix, resp in enumerate(actual_resp):
                    if 'provider' in resp:
                        resp.pop('provider')
                    if 'account' in resp:
                        resp.pop('account')
                    if 'date_from' not in resp:
                        resp['date_from'] = None
                    if 'date_till' not in resp:
                        resp['date_till'] = None
                    Responsibility.objects(
                        pk=responsibilities[ix].id
                    ).update(
                        __raw__={'$set': resp},
                    )
            if len(responsibilities) > len(actual_resp):
                Responsibility.objects(
                    pk__in=[r.id for r in responsibilities[len(actual_resp):]],
                ).delete()

    @classmethod
    def of(cls, tenant_id,
            date_from: datetime = None, date_till: datetime = None,
            provider_id = None) -> 'Responsibility' or None:
        """Ответственность жильца"""
        assert tenant_id, "Отсутствует идентификатор ответственного жильца"

        assert date_from is None or date_till is None \
            or date_from <= date_till, "Некорректные даты ответственности"

        query: dict = {
            'account._id': tenant_id,  # индекс
            'date_till': None,  # незавершенная
        }
        if provider_id:  # управляющая домом жильца организация?
            query['provider'] = provider_id  # не None

        responsibility: Responsibility = cls.objects(
            __raw__=query
        ).order_by('-date_from').first()  # первая с конца - последняя запись
        if responsibility is None:  # начало ответственности?
            if date_from is None:
                return responsibility  # None

            responsibility = cls(
                account=DenormalizedTenantWithName(id=tenant_id),  # ДН
                provider=provider_id,  # необязательное поле
                date_from=date_from,
                date_till=date_till,  # null=True
            )  # подлежит сохранению
        elif date_till and responsibility.date_till != date_till:
            responsibility.date_till = date_till  # не None

        if date_from and responsibility.date_from != date_from:
            responsibility.date_from = date_from  # не None

        return responsibility.save()  # сохраняем и синхронизируем

    @classmethod
    def sync_by_areas(cls, areas, provider_from, provider_to, forced=True):
        areas_ids = [a.id for a in areas]
        resp_from = list(
            cls.objects(
                provider=provider_from.id,
                account__area__id__in=areas_ids,
            ).as_pymongo(),
        )
        resp_to = list(
            cls.objects(
                provider=provider_to.id,
                account__area__id__in=areas_ids,
            ).as_pymongo(),
        )
        if not resp_from:
            if not forced and resp_to:
                return {
                    'status': 'warning',
                    'message': '{0} не имеет ответственных, а {1} имеет. '
                               'Операция приведёт к очистке ответственных '
                               'в {0}'.format(
                        provider_from.str_name,
                        provider_to.str_name,
                    ),
                }
            elif not resp_to:
                return {'status': 'error', 'message': 'Синхронизировать нечего'}
        elif not forced and resp_to:
            max_date_from_from = max(
                [r.get('date_from') or datetime.min for r in resp_from],
            )
            max_date_from_to = max(
                [r.get('date_from') or datetime.min for r in resp_to],
            )
            max_date_till_from = max(
                [r.get('date_till') or datetime.min for r in resp_from],
            )
            max_date_till_to = max(
                [r.get('date_till') or datetime.min for r in resp_to],
            )
            if (
                    max_date_from_from < max_date_from_to
                    or max_date_till_from < max_date_till_to
            ):
                return {
                    'status': 'warning',
                    'message': '{0} имеет данные о более новых ответственных, '
                               'чем {1}'.format(
                        provider_from.str_name,
                        provider_to.str_name,
                    ),
                }
        for x in resp_from:
            x.pop('_id')
            x['provider'] = provider_to.id
        cls.objects(pk__in=[r['_id'] for r in resp_to]).delete()
        if resp_from:
            docs = [cls(**r) for r in resp_from]
            cls.objects.insert(docs)
        return {'status': 'success', 'message': 'Синхронизировано'}

    def post_in_setl_home(self):
        from app.house.models.house import House
        if self._is_triggers(['account']):
            house = House.objects(
                pk=self.account.area.house.id,
                setl_home_address__ne=None,
            ).first()
            if house and house.get_developer_from_setl_home():
                from app.setl_home.task.post_data import post_import_home_r2f
                provider = house.get_provider_by_business_type(
                    'udo', date_on=None
                )
                post_import_home_r2f.delay(
                    setl_homes_address=[house.setl_home_address],
                    provider=provider,
                    tenants_id=[self.account.id],
                    mail=False,
                    phone=True,
                )
