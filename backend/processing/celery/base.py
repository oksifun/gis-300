import redis


def get_celery_queue_len(celery_app, queue_name):
    redis_host = celery_app.conf.broker_url.replace('redis://', '')
    if '/' in redis_host:
        data = redis_host.split('/')
        db_num = int(data[1])
        redis_host = data[0]
    else:
        db_num = 0
    data = redis_host.split(':')
    dbr = redis.StrictRedis(host=data[0], port=data[1], db=db_num)
    return dbr.llen(queue_name)
