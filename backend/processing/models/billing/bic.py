from mongoengine import StringField, Document, DynamicDocument


class Bic(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'Bic'
    }

    ADR = StringField(null=True)
    AT2 = StringField(null=True)
    AT1 = StringField(null=True)
    CKS = StringField(null=True)
    NNP = StringField(null=True)
    PZN = StringField(null=True)
    TNP = StringField(null=True)
    IND = StringField(null=True)
    RKC = StringField(null=True)
    RGN = StringField(null=True)
    UER = StringField(null=True)
    KSNP = StringField(null=True)
    OKPO = StringField(null=True)
    REGN = StringField(null=True)
    REAL = StringField(null=True)
    SROK = StringField(null=True)
    VKEY = StringField(null=True)
    NAMEN = StringField(null=True)
    NAMEP = StringField(null=True)
    NEWKS = StringField(null=True)
    TELEF = StringField(null=True)
    NEWNUM = StringField(null=True)
    PERMFO = StringField(null=True)
    DT_IZM = StringField(null=True)
    DATE_CH = StringField(null=True)
    DATE_IN = StringField(null=True)
    DT_IZMR = StringField(null=True)
    VKEYDEL = StringField(null=True)
    is_deleted = StringField(null=True)

    def delete(self, **write_concern):
        self.is_deleted = "True"
        self.save()


class BicNew(DynamicDocument):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'BicNew'
    }
