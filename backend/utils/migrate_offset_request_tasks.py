import pymongo
import settings

HOST = settings.DATABASES["processing"]["host"]
DB = settings.DATABASES["processing"]["db"]

collection = pymongo.MongoClient(host=HOST)[DB]['task']

requests = list(collection.find({"_cls": "Task.OffsetRequestTask", "tasks": {"$exists": True}}))

for request in requests:
    request['tenants'] = []
    for task in request['tasks']:

        request['tenants'].append(task['tenant'])
        request['on_date'] = task['date']
        request['sectors'] = task['sectors']

    del request['tasks']

    collection.save(request)

print(len(requests), 'objects updated')
