from mongoengine import Document, DateTimeField, ObjectIdField, StringField


class AccountingLog(Document):
    """
    Модель лога организаций запросивших изменения лицевых счетов
    и время запроса
    """
    meta = {
        "db_alias": "logs-db"
    }

    # Организация
    provider = ObjectIdField(verbose_name="Организация запросившая изменения")
    # Дата получения изменений по лицевым счетам
    date = DateTimeField(verbose_name="Дата получения изменений")
    # Данные какой коллекции запросили
    query_collection = StringField(verbose_name="К какой коллекции относятся запрошенные данные")
