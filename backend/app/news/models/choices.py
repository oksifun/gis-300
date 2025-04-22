# TODO пока эти константы используются только в новой модели
# TODO надо будет переключиться на них также при переезде контроллера
# TODO backend/tornado_legacy/controllers/constants.py

class NewsSystemCategory(object):
    RELEASE = 'release'
    GOOD_KNOW = 'good_know'
    SYS_OFFER = 'sys_offer'
    SYS_NOTIFY = 'sys_notify'
    TECH_WORKS = 'tech_works'


class NewsCategory(object):
    GOOD_KNOW = 'good_know'
    ORDER = 'order'
    INFO = 'info'
    RESULTS_MEETING = 'results_meeting'


NEWS_SYSTEM_CATEGORIES_CHOICES = (
    (NewsSystemCategory.RELEASE, 'Релиз системы'),
    (NewsSystemCategory.GOOD_KNOW, 'Это полезно знать'),
    (NewsSystemCategory.SYS_OFFER, 'Предложение системы'),
    (NewsSystemCategory.SYS_NOTIFY, 'Уведомление системы'),
    (NewsSystemCategory.TECH_WORKS, 'Технические работы'),
)

NEWS_CATEGORIES_CHOICES = (
    (NewsCategory.GOOD_KNOW, 'Это полезно знать'),
    (NewsCategory.ORDER, 'Приказ по организации'),
    (NewsCategory.INFO, 'Информация'),
    (NewsCategory.RESULTS_MEETING, 'По результатам совещания')
)

NEWS_CATEGORIES_CHOICES = tuple(set(
    NEWS_SYSTEM_CATEGORIES_CHOICES + NEWS_CATEGORIES_CHOICES
))
