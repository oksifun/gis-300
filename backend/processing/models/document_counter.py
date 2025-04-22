from datetime import datetime

from bson import ObjectId
from mongoengine import Document, ObjectIdField, IntField, StringField, \
    EmbeddedDocumentListField, EmbeddedDocument, DateTimeField

from lib.helpfull_tools import DateHelpFulls as DateHF


class CountersEmbedded(EmbeddedDocument):
    counter = IntField(verbose_name='Счетчик документов')
    year = DateTimeField(verbose_name='Год, за который ведется счет')


class DocumentCounter(Document):
    """Модель для ведения счета документов"""
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'DocumentCounter',
    }

    provider = ObjectIdField(
        verbose_name='Организация к который принадлежит документ'
    )
    document_name = StringField(
        verbose_name='Название документа подсчета'
    )
    counters = EmbeddedDocumentListField(
        CountersEmbedded,
        verbose_name='Список счетчиков документа по годам'
    )

    def get_document_count(self, date=None):
        """
        Получение счетчика за определенный год
        По умолчанию - текущий
        :param date: datetime
        """
        if not self.counters:
            return 0

        if not date:
            search_year = datetime.now().year
        else:
            search_year = date.year

        for elem in self.counters:
            if elem.year.year == search_year:
                return elem.counter
        # Если не нашлось совпадений
        return 0
    
    def increase_count(self, date=None, count=1):
        """
        Увеличить счетчик документа за определенный год.
        Если такого счетчика нет, то создать его
        :param date: datetime: год
        :param count: int: кол-во на которое нужно увеличить счетчик
        """
        if not date:
            date = datetime.now()
        if self.counters:
            for counter in self.counters:
                if DateHF.start_of_year(date) == counter.year:
                    counter.counter += count
                    return
            # Если не оказалось счетчика переданного года, то его нужно добавить
            self.counters.append(
                CountersEmbedded(counter=count,
                                 year=DateHF.start_of_year(date))
            )
        # Если счетчиков не было вовсе
        else:
            self.counters = [CountersEmbedded(counter=count,
                                              year=DateHF.start_of_year(date))]

    def save(self, *args, **kwargs):
        if self.counters:
            for counter in self.counters:
                counter.year = DateHF.start_of_year(counter.year)
        super().save(*args, **kwargs)


def get_document_counter(provider_id: ObjectId, report_name: str):
    """Получение счетчика документа (общий порядковый номер)"""
    document = DocumentCounter.objects(
        provider=provider_id, document_name=report_name)
    # Если документа нет, создаем новый
    if not document:
        dc = DocumentCounter(
            provider=provider_id, document_name=report_name
        )
        dc.increase_count()
        dc.save()
        return 1
    else:
        # Верменм счетчик и увеличим значения в базе на 1
        document = document.get()
        counter = document.get_document_count() + 1
        document.increase_count()
        document.save()
        return counter
