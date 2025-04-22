import datetime
import logging
from multiprocessing.pool import Pool

import pymongo
import requests
import time

from mongoengine.document import DynamicDocument
from multiprocessing import Value

from app.area.models.area import Area
from app.house.models.house import House
import mongoengine_connections
from tools.pyoo_helpers import retry
from utils.crm_utils import get_crm_client_ids


MAX_THREADS = 50

logging.basicConfig(level=logging.ERROR)


class AreasCadastralInfo(DynamicDocument):
    meta = {
        'db_alias': 'gis-db',
        'collection': 'areas_cadastral_numbers',
    }


@retry(
    (
        requests.exceptions.ConnectionError,
        pymongo.errors.AutoReconnect
    )
)
def get_area_info(area, house):
    """
    Получает и сохраняет данные о кадастровом номере с rosreestr.ru/api
        для конкретного помещения, или информацию об их отсутствии

    :param area: Объект app.area.models.area
    :param house: Объект app.house.models.house.House

    :return: True если данные найдены, иначе False
    """

    # TODO доделать остальные macroRegionId

    time.sleep(0.1)

    # Санкт-Петербург
    if house.fias_addrobjs[0] == 'c2deb16a-0330-4f05-821f-1d09c93331e6':
        macroRegionId = '140000000000'

    # Ленинградская область
    elif house.fias_addrobjs[0] == '6d1ebb35-70c6-4129-bd55-da3969658f5d':
        macroRegionId = '141000000000'

    # Краснодарский край
    elif house.fias_addrobjs[0] == 'd00e1013-16bd-4c09-b3d5-3cb09fc54bd8':
        macroRegionId = '103000000000'

    else:

        # По умолчанию - СПб
        macroRegionId = '140000000000'
        logging.warning('Невозможно выбрать macroRegionId для дома', house.id)

    street = ' '.join(house.street_only.split(' ')[1:])

    request_json = {
        "street": street,
        "house": house.number,
        "building": house.bulk,
        "apartment": area.number,
        "macroRegionId": macroRegionId,
    }

    addr_data = requests.post(
        'http://rosreestr.ru/api/online/address/fir_objects',
        json=request_json
    )

    AreasCadastralInfo.objects(area=area.id).delete()

    if addr_data.status_code == 200:

        AreasCadastralInfo(
            area=area.id,
            house=house.id,
            address_data=addr_data.json(),
            # cn_data=cn_data_json
        ).save()

        #
        # for address_data in addr_data.json():
        #     cn_data = requests.get(
        #         'http://rosreestr.ru/api/online/fir_objects/{}'.format(
        #             address_data['objectCn']
        #         )
        #     )
        #
        #     cn_data_json = cn_data.json() \
        #         if cn_data.status_code == 200 \
        #         else None
        #
        #     AreasCadastralInfo(
        #         area=area.id,
        #         house=house.id,
        #         address_data=address_data,
        #         cn_data=cn_data_json
        #     ).save()

        return True

    else:

        AreasCadastralInfo(
            area=area.id,
            house=house.id,
            not_found=True
        ).save()

        return False


@retry(
    Exception,
)
def get_house_areas_info(
        house,
        quiet=True,
        new_only=True
):
    """
    Для заданного помещения получает информацию с rosreestr.ru/api и
    сохраняет её через модель AreasCadastralInfo


    :param house: Объект app.house.models.house.House
    :param quiet: Не выводить инвормацию в процессе работы
    :param new_only: Искать информацию только для помещений,
        информация по которым отсутствует в базе

    :return: None
    """

    # Проверяем что список fias_addrobjs есть и он не пустой
    if not house.fias_addrobjs:
        print('Пустой/отсутствующий список fias_addrobjs для дома '
              + str(house.id))

        for area in Area.objects(house__id=house.id):

            AreasCadastralInfo(
                area=area.id,
                house=house.id,
                empty_fias_addrobjs=True
            ).save()

        return 0, 0, 0

    started = time.time()

    areas = Area.objects(house__id=house.id)

    global areas_done
    global areas_found
    global areas_not_found
    global areas_skipped

    areas_total_in_house = areas.count()

    areas_done_in_house = 0
    areas_found_in_house = 0
    areas_not_found_in_house = 0
    areas_skipped_in_house = 0

    while True:

        try:

            # Пропускаем дом целиком если можно
            if new_only and AreasCadastralInfo.objects(
                    house=house.id).count() == areas_total_in_house:

                areas_skipped.value += int(areas_total_in_house)
                areas_skipped_in_house += int(areas_total_in_house)
                areas_done.value += int(areas_total_in_house)

                if not quiet:
                    print('SKIP House')

                break

            for area in areas:

                if new_only and AreasCadastralInfo.objects(
                        area=area.id).count() > 0:
                    areas_skipped.value += 1
                    areas_skipped_in_house += 1

                elif get_area_info(area, house):
                    areas_found.value += 1
                    areas_found_in_house += 1

                else:
                    areas_not_found.value += 1
                    areas_not_found_in_house += 1

                areas_done.value += 1
                areas_done_in_house += 1

                if areas_done.value % 10000 == 0:
                    print(
                        '\nОбработано всего: {}'
                        '\n\tНайдено: {}'
                        '\n\tНе найдено: {}'
                        '\n\tПропущено: {}'
                        '\n'.format(
                            house.address,
                            time.time() - started,
                            areas_done.value,
                            areas_found.value,
                            areas_not_found.value,
                            areas_skipped.value,
                        )
                    )

            break

        except pymongo.errors.CursorNotFound:
            print('Mongo cursor revive')
            areas = Area.objects(
                house__id=house.id
            )[areas_done_in_house:]

    if not quiet:
        print(
            '{}({:.2f} sec):'
            '\n\tнайдено: {}/{}'
            '\n\tне найдено: {}/{}'
            '\n\tпропущено: {}/{}'
            '\n'.format(
                house.address,
                time.time() - started,
                areas_found_in_house, areas_total_in_house,
                areas_not_found_in_house, areas_total_in_house,
                areas_skipped_in_house, areas_total_in_house,
            )
        )

    return areas_found_in_house, areas_not_found_in_house, \
        areas_skipped_in_house


areas_done = None
areas_found = None
areas_not_found = None
areas_skipped = None


def get_info_for_clients_areas(
        quiet=True,
        new_only=True,
):
    """
    Запрашивает кадастровые номера для всех клиентов
    :return: None
    """
    clients = get_crm_client_ids()
    houses = list(House.objects(service_binds__provider__in=clients))

    areas_num = Area.objects(
        house__id__in=(house.id for house in houses)).count()

    threads_num = min((MAX_THREADS, len(houses)))

    print('\nЗапущено:', datetime.datetime.now())
    print('\tКлиентов:', len(clients))
    print('\tДомов:', len(houses))
    print('\tПомещений:', areas_num)
    # print('\tПримерное время выполнения: {:.2f} ч'.format(
    #       areas_num * 1 / threads_num / 3600))
    print()

    global areas_done
    global areas_found
    global areas_not_found
    global areas_skipped

    areas_done = Value('i', 0)
    areas_found = Value('i', 0)
    areas_not_found = Value('i', 0)
    areas_skipped = Value('i', 0)

    with Pool(
            processes=threads_num,
            initargs=(
                areas_done,
                areas_found,
                areas_not_found,
                areas_skipped,
            )
    ) as pool:

        results = pool.starmap(
            get_house_areas_info,
            ((house, quiet, new_only) for house in list(houses))
        )

    result = list(map(sum, zip(*results)))

    print('\nРезультат:')
    print('\nРезультат:')
    print('Найдено КН помещений:', result[0])
    print('Не найдено КН помещений:', result[1])
    print('Пропущено ранее найденых:', result[2])


if __name__ == '__main__':
    mongoengine_connections.register_mongoengine_connections()
    get_info_for_clients_areas(quiet=True, new_only=True)
