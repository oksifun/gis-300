from config import jinja2
from mongoengine import Document, StringField, BooleanField, FloatField, \
    IntField, DictField, DynamicField

from processing.models.logging.acquiring_error_log import AcquiringErrorLog


class ReceiptTemplate(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'ReceiptTemplate'
    }
    JINJA_ENV = jinja2.Environment()
    JINJA_TEMPLATES = {}

    name = StringField()
    is_loner = BooleanField()
    layout = StringField(
        choices=('portrait', 'landscape'),
        verbose_name='Ориентация листа',
        default='portrait',
    )
    table = DictField(verbose_name='Шаблон (JSON для таблицы Handsontable)')
    is_published = BooleanField(verbose_name='Опубликовано', default=True)
    per_page = IntField(verbose_name='Количество на листе', default=1)
    scale = FloatField(default=1.0, verbose_name='Масштаб')
    use_default = BooleanField(default=False)

    # ненужные поля
    file = DynamicField()

    def evaluate(self, params, provider=None):
        data = []

        for template_row in self.table['data']:
            row = []
            data.append(row)
            for cell in template_row:
                if cell:
                    try:
                        if cell not in self.JINJA_TEMPLATES:
                            self.JINJA_TEMPLATES[cell] = \
                                self.JINJA_ENV.from_string(cell)

                        value = self.JINJA_TEMPLATES[cell].render(**params)
                    except Exception as error:
                        print(error)
                        if provider:
                            error_log = AcquiringErrorLog.objects(
                                provider=provider,
                                template=self.id,
                                error_message=str(error)
                            ).first()
                            if not error_log:
                                AcquiringErrorLog(
                                    provider=provider,
                                    template=self.id,
                                    error_message=str(error)
                                ).save()
                        value = None
                else:
                    value = None

                row.append(value)
        return data
