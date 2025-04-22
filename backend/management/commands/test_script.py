import datetime

from management.scripts.mass_update.copy_house import copy_house_data
from mongoengine_connections import register_mongoengine_connections


if __name__ == "__main__":
    register_mongoengine_connections()

    d = datetime.datetime.now()
    r = copy_house_data(
        print,
        None,
        '56828af765939b0021710c46',
        '56c19d227bafd4001f788d40',

    )
    print('завершено', datetime.datetime.now() - d)
