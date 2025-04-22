
if __name__ == '__main__':
    import timeit

    mysetup1 = '''
from mongoengine import Document, ObjectIdField, StringField
from bson import ObjectId
from app.house.models.house import House
from mongoengine_connections import register_mongoengine_connections
register_mongoengine_connections()

class Coll(Document):
    field1 = ObjectIdField()
    field2 = StringField(default='new')
    field3 = StringField()

    def f1(self):
        self.field1 = House()
    '''

    mysetup2 = '''
from mongoengine import Document, ObjectIdField, StringField
from bson import ObjectId
from mongoengine_connections import register_mongoengine_connections
register_mongoengine_connections()

class Coll(Document):
    field1 = ObjectIdField()
    field2 = StringField(default='new')
    field3 = StringField()

    def f1(self):
        from app.house.models.house import House
        self.field1 = House()
        '''

    mycode = '''
obj = Coll(
    field1=ObjectId(),
    field3='new',
)
obj.f1()
    '''

    print(timeit.timeit(setup=mysetup1, stmt=mycode, number=10000))
    print(timeit.timeit(setup=mysetup2, stmt=mycode, number=10000))
