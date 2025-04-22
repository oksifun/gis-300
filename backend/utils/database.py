import settings


def get_replicas_count():
    return len(settings.DATABASES["default"]["host"].split(","))

