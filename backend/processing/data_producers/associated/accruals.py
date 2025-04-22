def import_settings_to_accruals(accrual_id, sector_code):
    from app.legal_entity.models.legal_entity_service import \
        EntityAgreementService
    from processing.models.billing.accrual import Accrual
    from app.accruals.models.accrual_document import AccrualDoc

    accrual_doc = AccrualDoc.objects(id=accrual_id).first()
    sector_binds = accrual_doc.sector_binds
    if not sector_binds:
        return
    providers = []
    for sector_bind in sector_binds:
        if sector_code == sector_bind.sector_code:
            providers.append(sector_bind.provider)
    contract_services = EntityAgreementService.objects(
        __raw__={
            'provider': {'$in': providers},
            'house': accrual_doc.house.id,
            'service': {'$exists': True}
        }
    ).as_pymongo()
    if not contract_services:
        raise Exception('Договора с этим провайдеров не существует')
    service_types = set()
    accruals = Accrual.objects(
        doc__id=accrual_id,
        sector_code=sector_code,
    ).as_pymongo()
    for accrual in accruals:
        for service in accrual.get('services'):
            service_types.add(service.get('service_type'))
    for service in contract_services:
        if service['service'] in service_types:
            services_dict = {
                'vendor': service['entity'],
                'service': service['service'],
                'contract': service['contract'],
            }
            save_accrual_doc(
                accrual_doc,
                sector_code,
                services_dict
            )


def save_accrual_doc(accrual_doc, sector_code, services_dict):
    from app.accruals.models.accrual_document import ServiceSettings
    for sector_bind in accrual_doc.sector_binds:
        if sector_bind.sector_code == sector_code:
            if ServiceSettings(
                    **services_dict
            ) not in sector_bind.settings.services:
                sector_bind.settings.services.append(ServiceSettings(
                    **services_dict
                ))
    accrual_doc.save()
