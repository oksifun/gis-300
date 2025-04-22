from app.area.models.area import Area


def restore_deleted_area(logger, task, house_id, area_str_number):
    """
        Скрипт восстанавливает удаленные помещения.
        :param logger: функция, которая пишет логи
        :param task: задача, запустившая скрипт
        :param house_id: id дома
        :param area_str_number: краткое наименование помещения на основе номера
        """
    areas = Area.objects(
        house__id=house_id,
        str_number=area_str_number,
        is_deleted=True,
    ).order_by('-id')
    if not areas:
        logger(f'Помещение "{area_str_number}" не найдено среди удаленных')
        return
    for area in areas:
        area.is_deleted = False
        if area.save():
            logger(
                f'Помещение {area.str_number_full} (id: {area.id}) '
                f'восстановлено'
            )
        else:
            logger('Ошибка восстановления')
