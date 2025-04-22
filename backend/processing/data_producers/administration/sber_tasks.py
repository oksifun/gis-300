from dateutil.relativedelta import relativedelta

from processing.models.billing.sbol import SbolInRegistryTask, \
    SbolOutRegistryTask


def get_registries_statistics(date_from, date_till):
    return {
        'in': get_in_registries_statistics(date_from, date_till),
        'out': get_out_registries_statistics(date_from, date_till),
    }


def get_in_registries_statistics(date_from, date_till):
    reg_in = SbolInRegistryTask.objects(
        created__gte=date_from,
        created__lt=date_till + relativedelta(days=1),
    ).as_pymongo().only(
        'status',
        'known_error',
        'id',
        'parse_tries',
        'reg_file.file_id',
    )
    result = {
        'total': len(reg_in),
        'finished': 0,
        'error': 0,
        'errors': {'unknown': 0},
        'wip': 0,
        'on_parse': 0,
        'unsolvable': 0,
        'unsolvables': [],
        'trash': []
    }
    for reg in reg_in:
        try:
            if reg['status'] == 'finished':
                result['finished'] += 1
            elif reg['status'] == 'error':
                result['error'] += 1
                if reg.get('known_error'):
                    result['errors'].setdefault(reg['known_error'], 0)
                    result['errors'][reg['known_error']] += 1
                else:
                    result['errors']['unknown'] += 1
            else:
                result['wip'] += 1
                if reg['status'] == 'ready':
                    result['on_parse'] += 1
                if reg.get('parse_tries', 0) > 5:
                    result['unsolvable'] += 1
                    result['unsolvables'].append({
                        'task': reg['_id'],
                        'file': reg['reg_file']['file_id'],
                    })
        except Exception as e:
            result['trash'].append(reg['_id'])
    return result


def get_out_registries_statistics(date_from, date_till):
    reg_in = SbolOutRegistryTask.objects(
        created__gte=date_from,
        created__lt=date_till + relativedelta(days=1),
    ).as_pymongo().only(
        'status',
        'known_error',
        'id',
        'reg_file.file_id',
        'logs',
    )
    result = {
        'total': len(reg_in),
        'finished': 0,
        'error': 0,
        'errors': {'unknown': 0, 'files': []},
        'wip': 0,
        'unsolvable': 0,
        'unsolvables': [],
        'trash': []
    }
    for reg in reg_in:
        try:
            if reg['status'] == 'finished':
                result['finished'] += 1
            elif reg['status'] == 'error':
                result['error'] += 1
                if 'known_error' in reg:
                    result['errors'].setdefault(reg['known_error'], 0)
                    result['errors'][reg['known_error']] += 1
                else:
                    result['errors']['unknown'] += 1
                if reg.get('reg_file'):
                    result['errors']['files'].append({
                        'task': reg['_id'],
                        'file': reg['reg_file']['file_id'],
                    })
            else:
                result['wip'] += 1
                if reg.get('logs') and len(reg['logs']) > 5:
                    result['unsolvable'] += 1
                    if reg.get('reg_file'):
                        result['unsolvables'].append({
                            'task': reg['_id'],
                            'file': reg['reg_file']['file_id'],
                        })
        except Exception as e:
            result['trash'].append(reg['_id'])
    return result

