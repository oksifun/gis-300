from requests import post
from bson import ObjectId

from app.notifications.constants import BOT_HOST, BOT_PORT
from processing.models.billing.account import Tenant
from processing.models.logging.custom_scripts import CustomScriptData


def synchronize_telegram_chats(logger, task, house_from, house_to):
    """
    Скрипт копирует жителей, помещения и счетчики из дома источника
    в дома цель. Только в случае если дом цель является пустым от счетчиков и
    жителей.
    :param logger: функция, которая пишет логи
    :param task: задача, запустившая скрипт
    :param house_from: дом источник
    :param house_to: дом цель
    """
    source_tenants_with_telegram = Tenant.objects(
        telegram_chats__not__size=0,
        telegram_chats__exists=True,
        area__house__id=ObjectId(house_from)
    )
    source_telegram_tenants_count = source_tenants_with_telegram.count()
    logger(f'Найдено {source_telegram_tenants_count} жителей с ботом, '
           f'запускаем синхронизацию 🐗')
    CustomScriptData(
        task=task.id if task else None,
        coll='Tenant',
        data=list(source_tenants_with_telegram.as_pymongo())
    ).save()
    for source_tenant in source_tenants_with_telegram:
        target_tenants = Tenant.objects(
            area__house__id=house_to,
            telegram_chats=source_tenant.telegram_chats
        )
        for target in target_tenants:
            for chat in target.telegram_chats:
                sync_data = dict(
                    chat_id=chat.chat_id,
                    old_number=source_tenant.number,
                    new_number=target.number
                )
                try:
                    sync_response = _send_sync_request(sync_data)
                    logger(f'{sync_response.text}, житель: {target.id}')
                except Exception as sync_exception:
                    logger(f'Ошибка синхронизации жителя: {target.id}. '
                           f'{sync_exception}')
    logger('Синхронизация завершена')


def _send_sync_request(sync_params):
    endpoint = '/api/v1/sync/tenant'
    url = f'{BOT_HOST}:{BOT_PORT}{endpoint}'
    response = post(url, json=sync_params, verify=False)
    response.raise_for_status()
    return response
