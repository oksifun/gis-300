from processing.models.billing.provider.main import Provider
from processing.models.billing.service_type import ServiceTypeGisName


def do_migration():
    providers = Provider.objects()
    coll = providers.count()
    list_id = providers.as_pymongo().only('id')
    progress = 0
    for _id in list_id:
        gis_names = ServiceTypeGisName.objects(provider=_id.get('_id'))
        if gis_names:
            delete_doubles(gis_names)
        percent = progress * 100 / coll
        print(int(percent))
        progress += 1


def delete_doubles(gis_names):
    saves = []
    for gis_name in gis_names:
        if gis_name.gis_title not in saves:
            saves.append(gis_name.gis_title)
        else:
            gis_name.delete()

if __name__ == "__main__":
    from mongoengine_connections import register_mongoengine_connections
    register_mongoengine_connections()
    do_migration()