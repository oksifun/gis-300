def getattr_deep(obj, name, default=None):
    """
    Same as getattr(), but allows dot notation lookup
    Peeped from: http://stackoverflow.com/questions/11975781
    """

    try:
        return reduce(getattr, name.split("."), obj)
    except AttributeError:
        if default:
            return default
        raise


def denormalize(instance=None, embedded=None, *args):
    """
    Denormalize document instance to EmbeddedDocument
    :param instance: source <Document>
    :param embedded: embedded document class <Class>
    :param args: fields for denormalization, <str>, can be "field_name", "field_name.subfield_name"
    :return: <EmbeddedDocumentClass>
    """
    embedded()
    fields = dict()
    for field in args:
        fields[field] = getattr_deep(instance, field)
    # TODO: complete


