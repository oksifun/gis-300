import pymongo
import settings

from datetime import datetime

HOST = settings.DATABASES["default"]["host"]
DB = settings.DATABASES["default"]["db"]
collection = pymongo.MongoClient(host=HOST)[DB]['Meter']

date_limit = datetime(year=7000, month=1, day=1)
correct_year = 2016

invalid_reading_meters = list(collection.find({"readings.period": {"$gt": date_limit}}))

invalid_readings_number = 0
for meter in invalid_reading_meters:
    invalid_readings = [r for r in meter['readings'] if r['period'] > date_limit]
    invalid_readings_number += len(invalid_readings)
    for reading in invalid_readings:
        new_period = reading['period'].replace(year=correct_year)
        print('{} : {} replace {} with {}'.format(
            meter.get('_id', 'Unknown meter!'),
            reading.get('_id', 'Unknown reading!'),
            reading['period'],
            new_period
        ))
        reading['period'] = new_period

    collection.save(meter)

print('\nFix {} readings in {} meters'.format(invalid_readings_number, len(invalid_reading_meters)))

