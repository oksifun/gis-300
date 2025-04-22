import datetime

from bson import ObjectId
from mongoengine import DoesNotExist

from processing.data_producers.export.privilege import PRIVILEGE_DOC_TYPE_CODE, \
    ID_DOC_CODE
from processing.models.billing.account import PrivilegeBind, Tenant
from processing.models.billing.tenant_data import TenantData, TenantPassport, \
    TenantIdDocument, TenantPrivilegeDocument
from processing.models.choice.privilege import PRIVILEGE_DOCUMENT_TYPES_CHOICES


SEX = {
    'М': 'male',
    'Ж': 'female',
}
_DOC_TYPE = {
    'Свидетельство о рождении': 'birth',
    '2': 'birth',
    '3': 'other',
    'Загранпаспорт гражданина РФ': 'travel',
    'Паспорт иностранного гражданина': 'alien_passport',
    'Паспорт гражданина СССР': 'ussr',
    'Иностранный паспорт': 'alien_passport',
    'Свидетельство о рождении, выданное уполномоченным '
    'органом иностранного государства': 'alien_birth',
    'Загранпаспорт гражданина Российской Федерации': 'travel',
}
_OTHER_DOCS = (
    'Иные документы, выдаваемые органами МВД',
)
_PASSPORT = (
    'Паспорт гражданина Российской Федерации',
    'Паспорт гражданина РФ',
    '1',
)
__REQUIRED_FIELDS = {
    'ls',
}


def extract_privilegers_from_gcjs(file):
    errors = []
    data_lines = [d for d in file.decode('cp1251').split('\r\n')]
    names = [x for x in data_lines[0].replace('\n', '').split(';')]
    if __REQUIRED_FIELDS - set(names):
        raise ValueError('Required fields not found')
    lines = [
        {names[ix]: y for ix, y in enumerate(x.replace('\n', '').split(';'))}
        for x in data_lines[1:]
    ]
    for ix, l in enumerate(lines):
        if not l.get('ls'):
            continue
        try:
            try:
                tenant = Tenant.objects(number=l['ls']).get()
            except DoesNotExist:
                errors.append('не найден житель {}'.format(l['ls']))
                continue
            t_data = TenantData.objects(tenant=tenant.pk).first()
            if not t_data:
                t_data = TenantData(
                    tenant=tenant.pk,
                    id_docs=[],
                    privilege_docs=[],
                    passport=TenantPassport(
                        series='',
                        number=None,
                        date=None,
                        issuer='',
                    ),
                )
            # основные данные жителя
            changed = _update_tenant(tenant, l)
            if changed:
                tenant.save()
            # паспортные данные
            changed_p, ee = _update_id_doc(t_data, l)
            if ee:
                errors.extend(ee)
            # документ льгот
            changed_pr, ee = _update_privilege_docs(t_data, l)
            if ee:
                errors.extend(ee)
            if changed_p or changed_pr:
                t_data.save()
        except Exception as e:
            errors.append('Ошибка в строке {}: {}'.format(
                ix,
                e.__class__.__name__
            ))
            raise e
    return errors


def _update_tenant(tenant, data):
    """
    Обновление основных данных жителя, которые хранятся в самом жителе
    """
    changed = False
    if data.get('b_date'):
        tenant.birth_date = datetime.datetime.strptime(
            data['b_date'],
            '%d.%m.%Y',
        )
        changed = True
    if data.get('pol'):
        tenant.sex = SEX[data['pol'].upper()]
        changed = True
    if data.get('snils'):
        tenant.snils = data['snils']
        changed = True
    if data.get('f') and data.get('i') and data.get('o'):
        tenant.last_name = data['f'].strip().capitalize()
        tenant.first_name = data['i'].strip().capitalize()
        tenant.patronymic_name = data['o'].strip().capitalize()
        changed = True
    if data.get('lg_cat'):
        tenant.is_privileged = True
        tenant.privileges.append(PrivilegeBind(
            accounts=[],
            privilege=ObjectId(data['lg_cat']),
            date_from=datetime.datetime.strptime(
                data['d_from'],
                '%d.%m.%Y',
            ) if data.get('d_from') else datetime.datetime.now(),
        ))
        changed = True
    return changed


def _update_id_doc(t_data, data):
    """
    Обновление TenantData - добавление/обновление паспорта или другого
    удостоверяющего документа
    """
    if 'ud_tip' not in data:
        return False, []
    errors = []
    doc_type = None
    changed = False
    if data['ud_tip'].isdigit():
        code = int(data['ud_tip'])
        if code in ID_DOC_CODE:
            doc_type = ID_DOC_CODE[code]
    if data['ud_tip'] in _PASSPORT or doc_type == 'passport':
        t_data.passport.series = data['ud_seria']
        nom = data['ud_nom'].replace('-', '').replace(',', '')
        if nom.isdigit():
            t_data.passport.number = nom
        else:
            errors.append(
                'ошибка номера паспорта {}'.format(
                    data['ud_nom'],
                ),
            )
        t_data.passport.date = datetime.datetime.strptime(
            data['ud_data'],
            '%d.%m.%Y',
        )
        t_data.passport.issuer = data['ud_kem']
        changed = True
    elif doc_type:
        t_data.id_docs.append(TenantIdDocument(
            doc_type=doc_type,
            series=data['ud_seria'],
            number=data['ud_nom'],
            date=datetime.datetime.strptime(
                data['ud_data'],
                '%d.%m.%Y',
            ),
            issuer=data['ud_kem'],
        ))
        changed = True
    elif data['ud_tip'] in _OTHER_DOCS:
        t_data.id_docs.append(TenantIdDocument(
            doc_type='other',
            custom_name=data['ud_tip'],
            series=data['ud_seria'],
            number=data['ud_nom'],
            date=datetime.datetime.strptime(
                data['ud_data'],
                '%d.%m.%Y',
            ),
            issuer=data['ud_kem'],
        ))
        changed = True
    elif data['ud_tip'] not in ('', '0'):
        t_data.id_docs.append(TenantIdDocument(
            doc_type=_DOC_TYPE[data['ud_tip']],
            series=data['ud_seria'],
            number=data['ud_nom'],
            date=datetime.datetime.strptime(
                data['ud_data'],
                '%d.%m.%Y',
            ),
            issuer=data['ud_kem'],
        ))
        changed = True
    return changed, errors


def _update_privilege_docs(t_data, data):
    """
    Обновление документов о льготах
    """
    if 'lg_doc_type' not in data:
        return False, []
    errors = []
    doc_type = None
    changed = False
    if data['lg_doc_type'].isdigit():
        code = int(data['lg_doc_type'])
        if code in PRIVILEGE_DOC_TYPE_CODE:
            doc_type = PRIVILEGE_DOC_TYPE_CODE[code]
    if not doc_type:
        for d_type in PRIVILEGE_DOCUMENT_TYPES_CHOICES:
            if d_type[1] == data['lg_doc_type']:
                doc_type = d_type[0]
                break
    if not doc_type:
        errors.append(
            'Неизвестный тип документа "{}"'.format(
                data['lg_doc_type'],
            ),
        )
    else:
        t_data.privilege_docs.append(TenantPrivilegeDocument(
            privilege=ObjectId(data['lg_cat']),
            doc_type=doc_type,
            series=data['ld_doc_seria'],
            number=data['lg_doc_num'],
            date_from=datetime.datetime.strptime(
                data['lg_doc_data'],
                '%d.%m.%Y',
            ),
            date_till=None,
            issuer=data['lg_doc_kem'],
        ))
        changed = True
    return changed, errors
