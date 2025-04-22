

def str_to_bool(string):
    return string in ('1', 'true', 'True', True)


def str_to_bool_or_none(string):
    if string in ('', 'none', 'None', None):
        return None
    return string in ('1', 'true', 'True', True)
