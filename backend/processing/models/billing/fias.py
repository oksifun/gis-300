from bson import ObjectId
from mongoengine import Document, IntField
from mongoengine.base.fields import ObjectIdField
from mongoengine.fields import StringField


class Fias(Document):
    meta = {
        'db_alias': 'fias-db',
        'collection': 'addrobjs',
    }

    CITYCODE = StringField()
    CENTSTATUS = StringField()
    ENDDATE = StringField()
    REGIONCODE = StringField()
    PREVID = StringField()
    OFFNAME = StringField()
    AREACODE = StringField()
    STREETCODE = StringField()
    IFNSUL = StringField()
    EXTRCODE = StringField()
    STARTDATE = StringField()
    AUTOCODE = StringField()
    OPERSTATUS = StringField()
    CODE = StringField()
    CURRSTATUS = StringField()
    SHORTNAME = StringField()
    AOLEVEL = StringField()
    CTARCODE = StringField()
    POSTALCODE = StringField()
    ACTSTATUS = StringField()
    PLAINCODE = StringField()
    SEXTCODE = StringField()
    PLACECODE = StringField()
    LIVESTATUS = StringField()
    FORMALNAME = StringField()
    UPDATEDATE = StringField()
    AOID = StringField()
    IFNSFL = StringField()
    OKATO = StringField()
    AOGUID = StringField()
    PARENTGUID = StringField()
    OKTMO = StringField()
    NORMDOC = StringField()
    DIVTYPE = StringField()
    PLANCODE = StringField()
    TERRIFNSFL = StringField()
    TERRIFNSUL = StringField()

    aolevel = IntField()


class FiasHouses(Document):
    meta = {
        'db_alias': 'fias-db',
        'collection': 'houses',
    }

    id = ObjectIdField(db_field="_id", primary_key=True)

    CITYCODE = StringField()
    TARTDATE = StringField()
    OKTMO = StringField()
    COUNTER = StringField()
    HOUSENUM = StringField()
    DIVTYPE = StringField()
    STATSTATUS = StringField()
    HOUSEID = StringField()
    UPDATEDATE = StringField()
    IFNSFL = StringField()
    STRSTATUS = StringField()
    POSTALCODE = StringField()
    HOUSEGUID = StringField()
    OKATO = StringField()
    ESTSTATUS = StringField()
    ENDDATE = StringField()
    AOGUID = StringField()
    IFNSUL = StringField()
    BUILDNUM = StringField()
    #  Возможно нужно убрать!
    STRUCNUM = StringField()
    CADNUM = StringField()
    STARTDATE = StringField()
    NORMDOC = StringField()
    REGIONCODE = StringField()
    TERRIFNSFL = StringField()
    TERRIFNSUL = StringField()


class SearchFias(Document):
    meta = {
        'db_alias': 'legacy-db',
        'collection': 'FiasSearch',
    }

    id = ObjectIdField(db_field="_id", primary_key=True, default=ObjectId)
    aoguid = StringField()
    aolevel = StringField()
    short_name = StringField()
    address = StringField()
    search_address = StringField()
