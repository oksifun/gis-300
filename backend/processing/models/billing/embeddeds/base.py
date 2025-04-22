from mongoengine import EmbeddedDocumentField


class DenormalizedEmbeddedMixin:
    @classmethod
    def from_ref(cls, ref_instance):
        obj = cls()
        for name, field in cls._fields.items():
            if (
                    isinstance(field, EmbeddedDocumentField)
                    and hasattr(field.document_type, 'from_ref')
            ):
                setattr(
                    obj,
                    name,
                    field.document_type.from_ref(getattr(ref_instance, name)),
                )
            else:
                setattr(obj, name, getattr(ref_instance, name))
        return obj

    @classmethod
    def from_ref_dict(cls, ref_as_dict):
        obj = cls()
        for name, field in cls._fields.items():
            if (
                    isinstance(field, EmbeddedDocumentField)
                    and hasattr(field.document_type, 'from_ref_dict')
            ):
                setattr(
                    obj,
                    name,
                    field.document_type.from_ref_dict(ref_as_dict.get(name)),
                )
            else:
                setattr(
                    obj,
                    name,
                    ref_as_dict.get(name) or ref_as_dict.get(field.db_field),
                )
        return obj
