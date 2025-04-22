import logging

from app.c300.models.deleted_data import DeletedData

logger = logging.getLogger('c300')


def soft_delete_object(model_instance):
    model = model_instance.__class__
    qs = model.objects(pk=model_instance.pk)
    data = qs.as_pymongo().first()
    if not data:
        return None
    result = DeletedData(
        model=model.__name__,
        ins_id=model_instance.id,
        data=data,
    ).save()
    if qs.count() == 1:
        qs.delete()
    return result


def soft_delete_by_queryset(qs, name=None):
    if not name:
        name = qs._document.__name__
    logger.debug('soft delete %s by queryset start', name)
    for ix, data in enumerate(qs.as_pymongo()):
        DeletedData(
            model=name,
            ins_id=data['_id'],
            data=data,
        ).save()
        if ix % 100 == 0:
            logger.debug(
                'soft delete %s by queryset progress %s',
                name, ix,
            )
    result = qs.count()
    logger.debug('soft delete %s by queryset done %s', name, result)
    qs.delete()
    return result

