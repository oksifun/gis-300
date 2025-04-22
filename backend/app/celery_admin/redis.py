# -*- coding: utf-8 -*-
import json

from celery import Celery
import redis

from app.celery_admin.workers.config import celery_app


def after_set_redis(f):
    """
    Декоратор, который перед выполнением функции инициализирует redis-client.
    """
    def wrapper(self, *args, **kwargs):
        if not self.redis:
            self.set_redis_client()
            return f(self, *args, **kwargs)
    return wrapper


class CeleryRedisClient:
    def __init__(self, celery_app=celery_app):
        self.celery_app = celery_app
        self.redis = None

    def set_redis_client(self):
        """Возвращает клиент редиса подключенного к брокеру Celery."""
        redis_host = self.celery_app.conf.broker_url.replace('redis://', '')
        if '/' in redis_host:
            data = redis_host.split('/')
            db_num = int(data[1])
            redis_host = data[0]
        else:
            db_num = 0
        data = redis_host.split(':')
        self.redis = redis.StrictRedis(host=data[0], port=data[1], db=db_num)
        
    @after_set_redis
    def queue_length(self, queue_name: str) -> int:
        """Возвращает длину очереди в redis."""
        return self.redis.llen(queue_name)
    
    @after_set_redis
    def revoke_tasks(self, queue_name: str, task_ids):
        """Удаляет задачу из redis и отменяет её выполнение в Celery."""
        task_ids = [task_ids] if type(task_ids) == str else task_ids
        celery_app.control.revoke(task_ids, terminate=True)
        tasks = self.redis.lrange(queue_name, 0, -1)
        tasks_with_task_ids = list(filter(
            lambda x: json.loads(x.decode())['headers']['id'] in task_ids, tasks
        ))
        for task in tasks_with_task_ids:
            self.redis.lrem(queue_name, -1, task)
