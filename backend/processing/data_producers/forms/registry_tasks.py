from lib.helpfull_tools import by_mongo_path
from app.registries.models.parse_tasks import RegistryParseTask
from processing.models.billing.sbol import SbolInRegistryTask


def get_meta(task_class):
    return getattr(task_class, '_meta')['collection']


REG_FIELDS = dict(
    status={
        get_meta(RegistryParseTask): 'state',
        get_meta(SbolInRegistryTask): 'status'
    },
    error_code={
        get_meta(RegistryParseTask): 'description',
        get_meta(SbolInRegistryTask): ('error_message', 'known_error')
    },
    file_name={
        get_meta(RegistryParseTask): 'registry_name',
        get_meta(SbolInRegistryTask): 'reg_name'
    },
    file_id={
        get_meta(RegistryParseTask): 'file',
        get_meta(SbolInRegistryTask): 'reg_file.file_id'
    },
    date={
        get_meta(RegistryParseTask): 'created',
        get_meta(SbolInRegistryTask): 'created'
    },
)
TASK_NAMES = {
    get_meta(SbolInRegistryTask): 'упш',
    get_meta(RegistryParseTask): 'почта',
}


def find_registry(name: str):
    """
    Поиск задачи по реестру по точному совпадению имени файла
    и вывод информации из полей, описанной в REG_FIELDS
    """
    sber_registries = SbolInRegistryTask.objects(reg_name=name).as_pymongo()
    mail_registries = RegistryParseTask.objects(registry_name=name).as_pymongo()
    return [
        _build_dict(registry, SbolInRegistryTask._collection.name)
        for registry in sber_registries
    ] + [
        _build_dict(registry, RegistryParseTask._collection.name)
        for registry in mail_registries
    ]


def _build_dict(registry, reg_type):
    _dict = {}
    for field_name, value in REG_FIELDS.items():
        if isinstance(value[reg_type], (list, tuple)):
            values = [by_mongo_path(registry, x, '') for x in value[reg_type]]
            # Либо выводим через точки, либо не выводим вообще
            new_value = (
                '. '.join(values).rstrip()
                if [x for x in values if x]
                else ''
            )
        else:
            new_value = by_mongo_path(registry, value[reg_type])
        _dict.update({field_name: new_value})

    _dict.update(task_type=TASK_NAMES[reg_type])
    return _dict
