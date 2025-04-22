
_TARIFF_GROUP_CODES = (0, 1, 2, 3, 4, 10, 12)


def get_groups_list(group):
    """
    Устаревший, не использовать в Ципке
    """
    result = [group]
    lev = len(str(group))
    for g in [x for x in _TARIFF_GROUP_CODES if len(str(x)) > lev]:
        if g % (10 ** lev) == group:
            result.append(g)
    return result
