from app.house.models.house import House, HouseEmbededServiceBind


def house_attach(
        fias_house_guid,
        areas_range,
        business_type,
        provider_id,
        date_start,
        date_end
):
    """ Привязка дома """

    # Проверяем, что дом еще не привязан
    house = House.objects(fias_house_guid=fias_house_guid).as_pymongo().first()
    if house:
        raise PermissionError("Этот дом уже прикреплен!")

    service_bind_params = dict(
        areas_range=areas_range,
        business_type=business_type,
        provider=provider_id,
        date_start=date_start
    )
    if date_end:
        service_bind_params['date_end'] = date_end
    # Сохраняем дом
    new_house = House(
        fias_house_guid=fias_house_guid,
        service_binds=[HouseEmbededServiceBind(**service_bind_params)]
    )
    new_house.save()
    return str(new_house.pk)
