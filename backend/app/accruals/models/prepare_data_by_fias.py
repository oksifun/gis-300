from mongoengine import Document, ObjectIdField, StringField, ListField, \
    DictField, DateTimeField


class AccrualsByFiasPrepareTask(Document):
    meta = {
        'db_alias': 'queue-db',
        'collection': 'accruals_by_fias',
        'index_background': True,
        'auto_create_index': False,
        'indexes': [
            {
                'fields': [
                    'provider',
                    'fias',
                ],
                'unique': True,
            },
        ],
    }

    provider = ObjectIdField()
    fias = StringField()
    month = DateTimeField()
    state = StringField(choices=('wip', 'finished', 'error'))
    data = ListField(DictField())

    @classmethod
    def create_task(cls, provider_id, month, fias):
        return cls.objects(
            provider=provider_id,
            month=month,
            fias=fias,
        ).upsert_one(
            data=None,
            state='wip',
        )

    @classmethod
    def update_task_state(cls, provider_id, month, fias, state, data):
        return cls.objects(
            provider=provider_id,
            month=month,
            fias=fias,
        ).upsert_one(
            data=data,
            state=state,
        )
