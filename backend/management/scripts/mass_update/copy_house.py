from bson import ObjectId

from app.accruals.models.accrual_document import AccrualDoc
from app.meters.models.meter import HouseMeter, AreaMeter
from app.offsets.core.run_offsets import run_house_offsets
from app.payment.models.denormalization.embedded_docs import \
    DenormalizedPaymentDoc
from app.permissions.tasks.binds_permissions import \
    process_provider_binds_models
from lib.type_convert import str_to_bool
from processing.models.billing.accrual import Accrual
from processing.models.billing.embeddeds.accrual_document import \
    DenormalizedAccrualDocument
from processing.models.billing.embeddeds.tenant import DenormalizedTenant
from app.house.models.house import House
from processing.models.billing.payment import Payment, PaymentDoc
from processing.models.billing.responsibility import Responsibility
from processing.models.billing.account import Tenant
from app.area.models.area import Area
from processing.models.billing.service_type import ServiceType
from processing.models.billing.tariff_plan import TariffPlan
from processing.models.billing.tenant_data import TenantData
from processing.models.logging.custom_scripts import CustomScriptData


def copy_house_data(logger, task, house_from, house_to, provider_from,
                    provider_to, delete_target_areas=False,
                    add_old_number=False, copy_tenants=True):
    """
    Скрипт копирует жителей, помещения и счетчики из дома источника
    в дома цель. Только в случае если дом цель является пустым от счетчиков и
    жителей.
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_from: дом источник
    :param house_to: дом цель
    :param provider_from: провайдер источник
    :param provider_to: провайдер цель
    :param delete_target_areas: по  умолчанию False, если True удаляет все
    помещения в доме источнике
    :param add_old_number: по умолчанию False, если True добавляет номер
    лицевого счета жителя-источника в поле old_numbers жителя цели
    :param copy_tenants: копировать ли жителей
    :param copy_coefficient: копировать все коэффиценты организации
    """
    if not house_from:
        raise Exception('Не задан дом-источник')
    house_from = House.objects(pk=ObjectId(house_from)).get()
    if not house_to:
        raise Exception('Не задан дом-цель')
    house_to = House.objects(pk=ObjectId(house_to)).get()
    if not provider_from:
        logger('Не задан провайдер-источник')
    provider_from = ObjectId(provider_from)
    if not provider_to:
        logger('Не задан провайдер-цель')
    provider_to = ObjectId(provider_to)
    if delete_target_areas:
        delete_target_areas = str_to_bool(delete_target_areas)
    if add_old_number:
        add_old_number = str_to_bool(add_old_number)

    if not delete_target_areas and Area.objects(house__id=house_to.pk).first():
        raise Exception('В доме есть помещения')
    if Tenant.objects(area__house__id=house_to.pk).first():
        raise Exception('В доме-цели есть жители')

    _copy_house_areas(logger, task, house_from, house_to, delete_target_areas)
    _copy_house_meters(logger, house_from, house_to)
    _copy_area_meters(logger, house_from, house_to)
    house_to.check_areas_binds()

    if copy_tenants:
        copy_tenants_between_houses(
            logger,
            house_from,
            house_to,
            provider_from,
            provider_to,
            add_old_number,
        )
    logger('Завершено')


def _copy_house_areas(logger, task, house_from, house_to, delete_target_areas):
    if delete_target_areas:
        areas = Area.objects(house__id=house_to.pk)
        CustomScriptData(
            task=task.id if task else None,
            coll='Area',
            data=list(areas.as_pymongo())
        ).save()
        areas.delete()
    areas_from = Area.objects(house__id=house_from.pk)
    logger('Нашла {} помещений'.format(areas_from.count()))
    for area in areas_from:
        area_exist = Area.objects(
            house__id=house_to.pk,
            str_number=area['str_number'],
            is_deleted__ne=True,
        ).as_pymongo().first()
        if area_exist:
            continue
        try:
            area.house.id = house_to.pk
            delattr(area, 'id')
            area._created = True
            area._binds = house_to._binds
            area.save(force_insert=True)
        except Exception as e:
            logger(
                'Ошибка  копирования помещения {} {}'.format(
                    area.number,
                    e,
                ),
            )


def _copy_house_meters(logger, house_from, house_to):
    meters = HouseMeter.objects(
        house__id=house_from.pk,
        _type='HouseMeter',
        is_deleted__ne=True,
    )
    logger('Нашла {} домовых счетчиков'.format(len(meters)))
    for meter in meters:
        try:
            meter.house.id = house_to.pk
            delattr(meter, 'id')
            meter._binds = house_to._binds
            meter._created = True
            meter.save(force_insert=True)
        except Exception as e:
            logger(
                'Ошибка в копировании {} {}'.format(
                    meter.house.address,
                    e,
                ),
            )


def _copy_area_meters(logger, house_from, house_to):
    meters = AreaMeter.objects(
        area__house__id=house_from.pk,
        _type='AreaMeter',
        is_deleted__ne=True,
    ).order_by('working_start_date')
    logger('Нашла {} счетчиков'.format(len(meters)))
    for meter in meters:
        area = Area.objects(
            house__id=house_to.pk,
            str_number=meter.area.str_number,
        ).as_pymongo().first()
        if area:
            try:
                meter.area.id = area['_id']
                delattr(meter, 'id')
                meter._binds = house_to._binds
                meter._created = True
                meter.save(force_insert=True, ignore_meter_validation=True)
            except Exception as e:
                logger(
                    'Ошибка копирования счетчика в квартире №{}. {}'.format(
                        area['number'],
                        e,
                    ),
                )


def copy_tenants_between_houses(logger, house_from, house_to,
                                provider_from, provider_to,
                                add_old_number, only_data=False,
                                copy_accruals=False):
    tenants_f = Tenant.objects(
        area__house__id=house_from.pk,
        _type__ne='OtherTenant',
        is_deleted__ne=True,
    ).order_by(
        'family.householder',
    )
    tenants_count = tenants_f.count()
    logger(f'Нашла {tenants_count} жителей')
    house_holders = {}
    tenants_hh = []
    tenants_not_hh = []
    for tenant in tenants_f:
        if tenant.family:
            if tenant.family.householder is None:
                tenants_hh.append(tenant)
            elif tenant.family.householder == tenant.id:
                tenants_hh.append(tenant)
            else:
                tenants_not_hh.append(tenant)
        else:
            tenants_hh.append(tenant)
    accrual_docs = {}
    payment_docs = {}
    tariff_plans = {}
    service_types = {}
    for tenants_list in (tenants_hh, tenants_not_hh):
        for i, tenant in enumerate(tenants_list, start=1):
            area = Area.objects(
                house__id=house_to.pk,
                str_number=tenant.area.str_number,
                is_deleted__ne=True,
            ).as_pymongo().first()
            if not area:
                continue
            tenant_id = tenant.id
            try:
                if not only_data:
                    _copy_tenant(
                        tenant, area, house_holders, add_old_number, house_to
                    )
                    responsibilities = Responsibility.objects(
                        account__id=tenant_id,
                        provider=provider_from,
                    )
                    for resp in responsibilities:
                        _copy_responsibility(resp, tenant, area, provider_to)
                tenant_data = TenantData.objects(tenant=tenant_id).first()
                if tenant_data:
                    _copy_tenant_data(tenant_data, tenant, house_to)
                if copy_accruals:
                    _copy_accruals(
                        logger,
                        tenant_id,
                        tenant,
                        house_to,
                        provider_from,
                        provider_to,
                        accrual_docs,
                        payment_docs,
                        tariff_plans,
                        service_types,
                    )
            except Exception as e:
                logger(
                    'Ошибка копирования жителя {}. {}'.format(
                        tenant_id,
                        e,
                    ),
                )
    _copy_tenant_family_relations(logger, house_holders)
    if copy_accruals:
        process_provider_binds_models(provider_to)
        run_house_offsets(provider_to, house_to.id)
        logger(f'Выполнение скрипта завершено')


def _copy_accruals(logger, tenant_from_id, tenant_to,
                   house_to,
                   provider_from_id, provider_to_id,
                   accrual_docs, payment_docs, tariff_plans, service_types):
    accruals = Accrual.objects(
        account__id=tenant_from_id,
        is_deleted__ne=True,
    ).as_pymongo()
    for accrual in accruals:
        _copy_accrual(
            logger,
            accrual,
            tenant_to,
            house_to,
            provider_from_id,
            provider_to_id,
            accrual_docs,
            tariff_plans,
            service_types,
        )
    payments = Payment.objects(
        account__id=tenant_from_id,
    ).as_pymongo()
    for payment in payments:
        _copy_payment(
            payment,
            tenant_to,
            provider_from_id,
            provider_to_id,
            payment_docs,
        )


def _copy_accrual(logger, accrual, tenant_to, house_to,
                  provider_from_id, provider_to_id,
                  accrual_docs, tariff_plans, service_types):
        accrual.pop('_id')
        accrual['account'] = DenormalizedTenant.from_ref(tenant_to)
        doc = accrual_docs.get(accrual['doc']['_id'])
        if not doc:
            doc = _copy_accrual_doc(
                accrual['doc']['_id'],
                provider_from_id,
                provider_to_id,
                house_to,
            )
            if not doc:
                logger(
                    f"Не смогла создать копию AccrualDoc "
                    f"{accrual['doc']['_id']}",
                )
                return
            doc = DenormalizedAccrualDocument.from_ref(doc)
            accrual_docs[accrual['doc']['_id']] = doc
        tp = tariff_plans.get(accrual['tariff_plan'])
        if not tp:
            tp = _copy_tariff_plan(
                accrual['tariff_plan'],
                provider_to_id,
                service_types,
            )
            tp = tp.id
            tariff_plans[accrual['tariff_plan']] = tp
        accrual['doc'] = doc
        if accrual['owner'] == provider_from_id:
            accrual['owner'] = provider_to_id
        accrual['tariff_plan'] = tp
        accrual['_binds'] = {'pr': [provider_to_id]}
        for service in accrual['services']:
            if service['service_type'] in service_types:
                service['service_type'] = service_types[service['service_type']]
        Accrual.objects.insert(Accrual(**accrual))


def _copy_accrual_doc(doc_id, provider_from_id, provider_to_id,
                      house_to):
    original_doc = \
        AccrualDoc.objects(pk=doc_id).as_pymongo().first()
    if not original_doc:
        return None
    original_doc.pop('_id')
    if original_doc['provider'] == provider_from_id:
        original_doc['provider'] = provider_to_id
    original_doc['house']['id'] = house_to.id
    original_doc['house'].pop('_id')
    original_doc['document_type'] = original_doc.pop('type')
    original_doc['_binds'] = {'pr': [provider_to_id],
                              'hg': house_to._binds.hg}
    for sector_bind in original_doc['sector_binds']:
        if sector_bind.get('_id'):
            sector_bind.pop('_id')
        if sector_bind['provider'] == provider_from_id:
            sector_bind['provider'] = provider_to_id
    return AccrualDoc.objects.insert(AccrualDoc(**original_doc))


def _copy_tariff_plan(tariff_plan_id, provider_to_id, service_types):
    original_tp = \
        TariffPlan.objects(pk=tariff_plan_id).as_pymongo().get()
    original_tp.pop('_id')
    original_tp['provider'] = provider_to_id
    for tariff in original_tp['tariffs']:
        service = service_types.get(tariff['service_type'])
        if service:
            tariff['service_type'] = service
            continue
        service = ServiceType.objects(
            pk=tariff['service_type'],
        ).as_pymongo().get()
        if service['is_system']:
            continue
        same_service = ServiceType.objects(
            provider=provider_to_id,
            title=service['title'],
        ).first()
        if same_service:
            service = same_service
        else:
            service.pop('_id')
            service['provider'] = provider_to_id
            service = ServiceType.objects.insert(ServiceType(**service))
        service_types[tariff['service_type']] = service.id
        tariff['service_type'] = service.id
    return TariffPlan.objects.insert(TariffPlan(**original_tp))


def _copy_payment(payment, tenant_to, provider_from_id, provider_to_id,
                  payment_docs):
    payment.pop('_id')
    payment['account'] = DenormalizedTenant.from_ref(tenant_to)
    payment['has_receipt'] = False
    payment['_binds'] = {'pr': [provider_to_id]}
    doc = payment_docs.get(payment['doc']['_id'])
    if not doc:
        original_doc = \
            PaymentDoc.objects(pk=payment['doc']['_id']).as_pymongo().get()
        original_doc.pop('_id')
        original_doc['bank_statement'] = None
        original_doc['bank_compared'] = False
        original_doc['_binds'] = {'pr': [provider_to_id]}
        if original_doc['provider'] == provider_from_id:
            original_doc['provider'] = provider_to_id
        doc = PaymentDoc.objects.insert(PaymentDoc(**original_doc))
        doc = DenormalizedPaymentDoc.from_ref(doc)
        if doc.bank:
            doc.bank = doc.bank.id
        payment_docs[payment['doc']['_id']] = doc
    payment['doc'] = doc
    Payment.objects.insert(Payment(**payment))


def _copy_tenant(tenant, area, house_holders, add_old_number, house_to):
    tenant_id = tenant.id
    tenant.area.id = area['_id']
    tenant.area.house.id = area['house']['_id']
    if tenant.family:
        if tenant.family.householder == tenant_id:
            tenant.family.householder = None
            tenant.family.relations = []
        elif tenant.family.householder:
            tenant.family.householder = \
                house_holders.get(tenant.family.householder)
            tenant.family.relations = []
    delattr(tenant, 'id')
    tenant.has_access = False
    tenant.password = ''
    old_number = tenant.number
    tenant.number = None
    tenant._binds = house_to._binds
    if add_old_number:
        tenant.old_numbers.append(old_number)
    tenant._created = True
    tenant.save(force_insert=True)
    house_holders[tenant_id] = tenant.id


def _copy_responsibility(resp, tenant, area, provider_to):
    resp.account.id = tenant.id
    resp.account.area.id = area['_id']
    resp.account.area.house.id = area['house']['_id']
    delattr(resp, 'id')
    resp.provider = provider_to
    resp._created = True
    resp.save(force_insert=True)


def _copy_tenant_data(tenant_data, tenant, house_to):
    tenant_data.tenant = tenant.id
    delattr(tenant_data, 'id')
    tenant_data._created = True
    tenant_data._binds = house_to._binds
    tenant_data.save(force_insert=True)


def _copy_tenant_family_relations(logger, house_holders):
    """
    После создания новых жителей, перезаполним семью у новых жителей, по данным
    старых жителей
    """
    logger(f'Копирую совместных жильцов жителя')
    for k, v in house_holders.items():
        tenant_old = Tenant.objects(pk=k).get()
        tenant_new = Tenant.objects(pk=v).get()
        try:
            relations = []
            if tenant_old.family.relations:
                for relation in tenant_old.family.relations:
                    relation.related_to = house_holders[relation.related_to]
                    relations.append(relation)
                tenant_new.family.relations = relations
                tenant_new.save()
        except Exception as e:
            logger(
                'Ошибка копирования совместных жильцов жителя {}. {}'.format(
                    tenant_new.id,
                    e,
                ),
            )
    logger(f'Копирование совместных жильцов жителя завершено')
