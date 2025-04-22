from datetime import datetime
from mongoengine import Document, DateTimeField, \
    ObjectIdField, EmbeddedDocumentListField, EmbeddedDocumentField, Q

from processing.models.billing.base import BindedModelMixin
from processing.models.billing.embeddeds.phone import DenormalizedPhone
from processing.models.billing.provider.main import BankProvider
from processing.models.choices import LegalFormType

from .core import LegalEntityBankAccountEmbedded, LegalEntityDetailsEmbedded, \
    ProviderBinds
from .legal_entity import LegalEntity


class LegalEntityProviderBind(Document, BindedModelMixin):
    """
    Привязки провайдеров и юр.лиц. Клиенты не обращаются в LegalEntity напрямую,
    а только через эти привязки.
    """
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'LegalEntityProviderBind',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            '_binds.pr',
            'provider',
        ],
    }

    provider = ObjectIdField(
        required=True,
        verbose_name='Провайдер (организация-клиент)'
    )

    entity = ObjectIdField(
        required=True,
        verbose_name='Организация'
    )
    entity_details = EmbeddedDocumentListField(
        LegalEntityDetailsEmbedded,
        required=True,
        verbose_name='Реквизиты',
    )
    phones = EmbeddedDocumentListField(
        DenormalizedPhone, verbose_name="Список телефонов")
    entity_bank_accounts = EmbeddedDocumentListField(
        LegalEntityBankAccountEmbedded,
        verbose_name='Расчётные счета'
    )

    created = DateTimeField()
    closed = DateTimeField()

    _binds = EmbeddedDocumentField(
        ProviderBinds,
        verbose_name='Привязки к организации'
    )

    @classmethod
    def get_or_create(cls, entity, provider):
        if not (bool(entity) & bool(provider)):
            return
        entity = entity if isinstance(entity,
                                      Document) else LegalEntity.objects(
            id=entity).first()
        provider_pk = provider.id if isinstance(provider,
                                                Document) else provider
        if not (bool(entity) & bool(provider_pk)):
            return
        bind = cls.objects(
            entity=entity.id,
            provider=provider_pk,
        ).first()
        if not bind:
            bind = cls(
                entity=entity.id,
                provider=provider_pk,
                entity_details=entity.details,
            )
            bind.save()
        return bind

    @classmethod
    def get_binds_query(cls, binds_permissions, raw: bool = False):
        """
        Метод для преобразования переданной привязки в нужный для модели вид
        :param raw: если нужен в виде словоря
        :param binds_permissions: переданные привязки
        :return: dict, Q
        """
        result = super().get_binds_query(binds_permissions, raw)
        if raw:
            return result
        else:
            return result & Q()

    def _get_providers_binds(self):
        return [self.provider]

    def denormalize_legal_entity(self):
        legal_entity = LegalEntity.objects(id=self.entity).first()
        if legal_entity:
            legal_entity.phones = self.phones
            legal_entity.details = self.entity_details
            legal_entity.save()

    def save(self, *args, **kwargs):
        if not self._binds:
            self._binds = ProviderBinds(pr=self._get_providers_binds())
        super_save = super().save(*args, **kwargs)
        self.denormalize_legal_entity()
        return super_save

    @classmethod
    def create_new_legal_binds(
            cls,
            legal_provider,
            legal_inn,
            legal_name,
            short_name=None,
            legal_form='',
            ogrn='',
            phones=None,
            bank_accounts=None
    ):
        """
        Функция создает новые привязки у юр. лица, елси юр. лица не существует то,

        создает и юр лицо
        :param legal_provider: id провайдера с которым у Юр лица составлен договор
        :param legal_inn: ИНН юридического лица
        :param legal_name: Название Юр. лица
        :param short_name: Коротое название организации если есть, по умолчанию None
        :param legal_form: Форма юр. лица по умолчанию ''
        :param ogrn: ОГРН по умолчанию ''
        :param phones: список телефонный номеров юр лица
        :param bank_accounts список банквоский реквизитов
        """
        if not phones:
            phones = []
        if not bank_accounts:
            bank_accounts = []
        legal_form_list = [e for _, e in LegalFormType.__dict__.items()]
        if legal_form not in legal_form_list:
            return f'Такой "{legal_form}" формы организации не существует'
        legal_entity = LegalEntity.objects(
            current_details__current_inn=legal_inn
        ).first()
        if not legal_entity:
            legal_entity = cls.create_new_legal_entity(
                legal_inn,
                legal_name,
                legal_form,
                short_name,
                ogrn,
                phones,
                bank_accounts
            )
        if not LegalEntityProviderBind.objects(entity=legal_entity.id).first():
            provider_bind = LegalEntityProviderBind(
                entity=legal_entity.id,
                provider=legal_provider,
                created=datetime.now(),
                entity_details=legal_entity.details,
                entity_bank_accounts=legal_entity.bank_account,
                phones=[DenormalizedPhone(**phone) for phone in phones]
            )
            try:
                provider_bind.save()
            except:
                return 'Параметры переданы неверно'
        else:
            return 'Привязки для этой организации существуют'

    @staticmethod
    def create_new_legal_entity(
            legal_inn,
            legal_name,
            legal_form,
            short_name,
            ogrn,
            phones,
            bank_accounts
    ):
        legal_entity = LegalEntity(
            ogrn=ogrn,
            phones=[DenormalizedPhone(**phone) for phone in phones]
        )
        details = LegalEntityDetailsEmbedded(
            inn=legal_inn,
            full_name=legal_name,
            short_name=short_name if short_name else legal_name,
            date_from=datetime.now(),
            legal_form=legal_form,
            created=datetime.now(),
        )
        if bank_accounts:
            for bank_account in bank_accounts:
                bank = BankProvider.objects(
                    bic_body__BIC=bank_account['bic']
                ).as_pymongo().first()
                if bank and bank.get('_id'):
                    bank_account['bank'] = bank['_id']
                    bank_account['date_from'] = bank.get('bic_body')[-1].get(
                        'DateIn')

        bank_accounts = [
            LegalEntityBankAccountEmbedded(**bank_account)
            for bank_account in bank_accounts
        ]
        legal_entity.details = [details]
        legal_entity.bank_account = bank_accounts

        legal_entity.save()
        # except:
        #     raise ValidationError('Неверные параметры')
        return legal_entity
