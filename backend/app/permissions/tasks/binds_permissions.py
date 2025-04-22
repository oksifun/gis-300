from bson import ObjectId
from mongoengine import Document, EmbeddedDocumentField

from app.permissions.workers.config import joker_app
from processing.models.billing.provider.main import ProviderRelations
from processing.models.permissions import Permissions


@joker_app.task(
    soft_time_limit=60,
    rate_limit='100/s',
    bind=True
)
def process_house_binds_models(self, house_id, instantly=False):
    # импортируем все модели, чтобы определить сабклассы Document
    import processing.models.billing

    models = [
        x
        for x in Document.__subclasses__()
        if (
            hasattr(x, '_binds')
            and isinstance(x._binds, EmbeddedDocumentField)
            and hasattr(x._binds.document_type_obj, 'hg')
            and hasattr(x, 'process_house_binds')
        )
    ]
    if instantly:
        errors = []
        for model in models:
            try:
                process_house_binds(model, house_id)
            except AttributeError:
                errors.append(model.__name__)
        if errors:
            raise AttributeError(f'At models: {errors}')
    else:
        for model in models:
            process_house_binds.delay(model, house_id)


@joker_app.task(
    soft_time_limit=3 * 60,
    rate_limit='100/s',
    bind=True
)
def process_house_binds(self, model, house_id):
    model.process_house_binds(house_id)


@joker_app.task(
    bind=True,
    max_retries=7,
    soft_time_limit=60 * 2,
    default_retry_delay=30,
    rate_limit='2/s',
)
def sync_permissions(self, account_id: ObjectId):
    """
    Синхронизация прав (Permissions) Worker'ов с Actors
    """
    Permissions.objects(actor_id=account_id).first().transfer_to_actor()
    return 'success'


@joker_app.task(
    soft_time_limit=2 * 60,
    rate_limit='100/s',
    bind=True
)
def process_provider_binds_models(self, provider_id,
                                  force=False, include_slaves=False,
                                  instantly=False):
    # импортируем все модели, чтобы определить сабклассы Document
    import processing.models.billing

    errors = []
    models = [
        x
        for x in Document.__subclasses__()
        if (
            hasattr(x, '_binds')
            and isinstance(x._binds, EmbeddedDocumentField)
            and hasattr(x._binds.document_type_obj, 'pr')
        )
    ]
    # при необходимости подгрузим зависимые организации
    slaves = []
    if include_slaves:
        relations = ProviderRelations.objects(
            provider=provider_id,
        ).as_pymongo().first()
        if relations:
            slaves = [s['provider'] for s in relations['slaves']]
    # запуск задач на пересчёт по каждой модели
    for model in models:
        if instantly:
            try:
                process_provider_binds(model, provider_id, force=force)
            except AttributeError:
                errors.append(model.__name__)
        else:
            process_provider_binds.delay(model, provider_id, force=force)
        if include_slaves:
            exist_slaves = set(model.objects(
                doc__provider=provider_id,
            ).distinct('_binds.pr')) - {provider_id}
            slaves = list(set(slaves) | exist_slaves)
        for slave in slaves:
            if instantly:
                try:
                    process_provider_binds(model, slave, force=force)
                except AttributeError:
                    errors.append(model.__name__)
            else:
                process_provider_binds.delay(model, slave, force=force)
    if errors:
        raise AttributeError(f'At models: {errors}')


@joker_app.task(
    soft_time_limit=10 * 60,
    rate_limit='100/s',
    bind=True
)
def process_provider_binds(self, model, provider_id, force=False):
    pushed, pulled = model.process_provider_binds(provider_id, force=force)
    return '{} pushed, {} pulled'.format(pushed, pulled)


@joker_app.task(
    soft_time_limit=60,
    rate_limit='100/s',
    bind=True
)
def process_account_binds_models(self, account_id):
    # импортируем все модели, чтобы определить сабклассы Document
    import processing.models.billing

    models = [
        x
        for x in Document.__subclasses__()
        if (
            hasattr(x, '_binds')
            and isinstance(x._binds, EmbeddedDocumentField)
            and hasattr(x._binds.document_type_obj, 'ac')
        )
    ]
    for model in models:
        process_account_binds.delay(model, account_id)


@joker_app.task(
    soft_time_limit=2 * 60,
    rate_limit='100/s',
    bind=True
)
def process_account_binds(self, model, account_id):
    pushed, pulled = model.process_account_binds(account_id)
    return '{} pushed, {} pulled'.format(pushed, pulled)


@joker_app.task(
    soft_time_limit=60,
    rate_limit='100/s',
    bind=True
)
def process_department_binds_models(self, account_id):
    # импортируем все модели, чтобы определить сабклассы Document
    import processing.models.billing

    models = [
        x
        for x in Document.__subclasses__()
        if (
            hasattr(x, '_binds')
            and isinstance(x._binds, EmbeddedDocumentField)
            and hasattr(x._binds.document_type_obj, 'dt')
        )
    ]
    for model in models:
        process_department_binds.delay(model, account_id)


@joker_app.task(
    soft_time_limit=2 * 60,
    rate_limit='100/s',
    bind=True
)
def process_department_binds(self, model, account_id):
    pushed, pulled = model.process_department_binds(account_id)
    return '{} pushed, {} pulled'.format(pushed, pulled)
