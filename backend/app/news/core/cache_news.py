from app.house.models.house import House
from app.news.models.news import News, DEFAULT_HOUSE, DEFAULT_FIAS


def get_house_tenants_news_queryset(house_id):
    house = House.objects(
        pk=house_id,
    ).only(
        'id',
        'service_binds',
        'fias_addrobjs',
    ).as_pymongo().get()
    providers = [
        bind['provider']
        for bind in house['service_binds']
        if bind.get('provider')
    ]
    return News.objects(
        __raw__={
            '$and': [
                {
                    'for_tenants': True,
                    'is_published': True,
                },
                {
                    '$or': [
                        {
                            'houses': {
                                '$in': [DEFAULT_HOUSE, house_id],
                            },
                        },
                        {
                            'fiases': {
                                '$in': house['fias_addrobjs'] + [DEFAULT_FIAS],
                            },
                        },
                    ],
                },
                {
                    '$or': [
                        {'_binds.pr': []},
                        {'_binds.pr': {'$in': providers}},
                    ],
                },
            ],
        },
    ).sort('-created_at')
