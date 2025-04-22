from mongoengine import Document, StringField, ListField
from mongoengine.base.fields import ObjectIdField
from mongoengine.document import EmbeddedDocument
from mongoengine.fields import EmbeddedDocumentField, DateTimeField


class BankAccountEmbeddedProcessingService(EmbeddedDocument):

    # TODO choices
    # ProcessingSource = Constants(
    #     ('trmn', 'Терминал'),
    #     ('cbnt', 'Личный кабинет'),
    # )
    #
    # ProcessingType = Constants(
    #     ('pskb', 'ПСКБ'),
    #     ('mcard', 'Мобильная карта'),
    # )

    type = StringField(required=True)  # Required(ProcessingType),
    code = StringField(required=True)  # Required(String),
    source = StringField(required=True)  # Required(ProcessingSource),


class BankAccount(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'BankAccount',
    }

    bic = ObjectIdField()  # Required(Ref('BankProvider')),  # ссылка на банк  # TODO ReferenceField
    name = StringField()  # String,  # Название счета
    number = StringField()  # BankAccountNumber,  # номер счета
    service_codes = ListField(StringField())  # [String],  # код услуги
    contract_number = StringField(required=True)  # Required(String, default=''),  # номер договора
    processing_service = StringField()  # NString,
    processing_services = ListField(EmbeddedDocumentField(BankAccountEmbeddedProcessingService))  # [ProcessingService],  # описания процессингов для
    date_from = DateTimeField()  # Optional(Date),  # дата открытия
    active_till = DateTimeField()  # срок дейтвия, после которого счёт считается "архивным"

