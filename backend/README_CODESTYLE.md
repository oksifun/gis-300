# Style Guide for Python Code

## Imports
+ Импорт обычно должен быть в отдельных строках:
```python
# Correct:
import os
import sys
```
```python
# Wrong:
import sys, os
```
+ Импорт всегда помещается в начало файла, сразу после любых комментариев модуля и строк документации, а также перед глобальными параметрами и константами модуля.
Импорт должен быть сгруппирован в следующем порядке:
  + Импорт стандартных библиотек;
  + Связанный импорт третьих сторон;
  + Импорт локального приложения/библиотеки;
  + Между каждой группой импорта необходимо поместить пустую строку.
```python
# Correct:
from apps.app_users.serializers.request_body import (
    CookieRefreshTokenSerializer,
    CookieVerifyTokenSerializer,
    GoogleAuthSerializer,
    UserSerializer,
)
from apps.app_users.serializers.schema import UserSignupResponseSerializer
from apps.app_users.services.check_google_auth import check_google_auth
from apps.app_users.services.set_cookie_data import SetCookie

from django.http import JsonResponse

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
```
```python
# Wrong:
from apps.app_users.serializers.request_body import CookieRefreshTokenSerializer, CookieVerifyTokenSerializer, \
     GoogleAuthSerializer, UserSerializer
from apps.app_users.serializers.schema import UserSignupResponseSerializer
from apps.app_users.services.check_google_auth import check_google_auth
from apps.app_users.services.set_cookie_data import SetCookie
from django.http import JsonResponse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
```
+ Абсолютный импорт рекомендуется, так как он обычно более удобочитаем и, как правило, ведет себя лучше (или, по крайней мере, дает более качественные сообщения об ошибках), если система импорта настроена неправильно (например, когда каталог внутри пакета заканчивается на) sys.path:
```python
import mypkg.sibling
from mypkg import sibling
from mypkg.sibling import example
```

## Максимальная длина строки
+ Ограничение строк максимум 79 символов.
+ Предпочтительным способом переноса длинных строк является использование подразумеваемого Python продолжения строки внутри круглых и фигурных скобок. Длинные строки можно разбивать на несколько строк, заключая выражения в круглые скобки. Их следует использовать вместо использования обратной косой черты для продолжения строки.

## Пустые строки
+ Функции и классы верхнего уровня необходимо разделять двумя пустыми строками.
+ Методы внутри класса необходимо разделять одной пустой строкой.
+ Дополнительные пустые строки можно использовать (экономно) для разделения групп связанных функций.


## Когда использовать конечные запятые
+ Конечные запятые обязательны при создании кортежа из одного элемента: 
```python
# Correct:
FILES = ('setup.cfg',)
```
```python
# Wrong:
FILES = 'setup.cfg',
```
+ Конечные запятые полезны при использовании системы контроля версий, когда ожидается, что список значений, аргументов или импортированных элементов будет расширяться с течением времени. Шаблон заключается в том, чтобы помещать каждое значение (и т. д.) в отдельную строку, всегда добавляя завершающую запятую, и добавляя закрывающую parenthesis/bracket/brace на следующей строке. Однако не имеет смысла ставить запятую на той же строке, что и закрывающий разделитель (за исключением приведенного выше случая одноэлементных кортежей):
```python
# Correct:
FILES = [
    'setup.cfg', 
    'tox.ini',
]
initialize(
    FILES, 
    error=True,
)
```
```python
# Wrong:
FILES = ['setup.cfg', 'tox.ini',]
initialize(FILES, error=True,)
```

## Перенос строк
+ При использовании длинных сообщений их стоит выносить в отдельную переменную. Также необходимо прописывать статус ответа. Во всем проекте используются одинарные кавычки следует придерживаться этого правила:
```python
# Correct:
message = (
    'Выполняется загрузка из '
    f'ГИС ЖКХ показаний ПУ за {fmt_period}'
)
return Response(
    data={'message': message}, 
    status=status.HTTP_200_OK,
)
```
```python
# Wrong:
return Response(data={'message': "Выполняется загрузка"
                      f" мз ГИС ЖКХ показаний ПУ за {fmt_period}"})
```
+ Функции не должны содержать большого количества элементов. Функции должны соответствовать принципу Single Responsibility Principle. Функции должны быть короткими и выполнять только одну задачу. Если нет возможности разбить функцию на несколько с малым количеством элементов перенос выполняется следующим образом: 
```python
# Correct:
def import_readings(
        provider_id: ObjectId,
        house_id: ObjectId,
        period: datetime = None,
        **options
): -> None
```
```python
# Wrong:
def import_readings(provider_id: ObjectId, house_id: ObjectId,
        period: datetime = None, **options):
```

## Комментарии
+ Комментарии, противоречащие коду, хуже, чем отсутствие комментариев. Всегда уделяйте приоритетное внимание обновлению комментариев при изменении кода!
+ Комментарии должны быть полными предложениями. Первое слово должно быть написано с большой буквы, если только это не идентификатор, начинающийся со строчной буквы (никогда не меняйте регистр идентификаторов!).
+ Блочные комментарии обычно состоят из одного или нескольких абзацев, построенных из полных предложений, каждое из которых заканчивается точкой.
+ Вы должны использовать один или два пробела после точки в конце предложения в комментариях, состоящих из нескольких предложений, за исключением последнего предложения.
+ Блочные комментарии обычно применяются к некоторому (или всему) коду, следующему за ними, и имеют отступ на том же уровне, что и этот код. Каждая строка блочного комментария начинается с символа # и одиночного пробела (если это не текст с отступом внутри комментария).
+ Абзацы внутри блочного комментария разделяются строкой, содержащей одиночный #.
+ Встроенные комментарии должны быть отделены от оператора не менее чем двумя пробелами. Они должны начинаться с # и одного пробела. Встроенные комментарии не нужны и на самом деле отвлекают, если они констатируют очевидное:
```python
# Wrong:
x = x + 1  # Increment x
```

## Соглашение об именах
+ Имена классов должны использовать соглашение CapWords.
+ Имена функций должны быть написаны строчными буквами, а слова должны быть разделены символом подчеркивания, если это необходимо для улучшения читаемости.
+ Имена переменных следуют тому же соглашению, что и имена функций.
+ Всегда используйте `self` в качестве первого аргумента методов экземпляра.
+ Всегда используйте `cls` в качестве первого аргумента методов класса.
+ Если имя аргумента функции конфликтует с зарезервированным ключевым словом, как правило, лучше добавить одиночное подчеркивание в конце, чем использовать аббревиатуру или искажение орфографии. Таким образом, `class_` лучше, чем `clss`. (Лучше избегать таких конфликтов, используя синоним.).
+ Имена методов и переменные экземпляра. Используйте правила именования функций: нижний регистр со словами, разделенными символами подчеркивания, если это необходимо для улучшения читабельности.

## Logging
+ При ведении журнала логов или вывода логов в консоль используйте `%s`: 
```python
# Correct:
logger.error('Error: %s', error)
```
```python
# Wrong:
logger.error(f'Error: {error}')
```
+ Что бы иметь возможность посмотреть промежуточное значение переменной в процессе отладки необходимо результаты любых операций выносить в отдельную переменную: 
```python
# Correct:
def calculate_sum(coord_x, coord_y):
    sum_coord = coord_x + coord_y
    return sum_coord
```
```python
# Wrong:
def calculate_sum(coord_x, coord_y): 
    return coord_x + coord_y
```

## Docstrings
+ Используйте документационные строки (google docstring) для описания назначения функций, классов и методов. Документационные строки должны быть заключены в тройные кавычки и располагаться сразу после объявления функции, класса или метода. формат строки документации можно изменить в Settings | Tools | Python Integrated Tools | Docstring format: 
```python
# Correct:
@celery_app.task(
    bind=True,
    soft_time_limit=8*60,
)
def verified_params(self, cad_numbers, rights: bool, main_characters: bool):
    """Таска на групповую сверку ряда кадастровых номеров.

    Таска проводит сверку большой группы квартир, повторяя те же операции,
    что и verify_area, verify_tenant и verify_all, но на большом объеме
    данных.

    Args:
        self: celery таска
        cad_numbers: Список кадастровых номеров на проверку
        rights: Идет ли проверка записей о праве собственности
        main_characters: идет ли проверка значений площади помещения

    Returns:
        Таска не возвращает значений

    """
    houses = VerifyAreaData.verify_by_cad_nums(
        cad_numbers, rights, main_characters
    )

    if houses:
        statistic_for_house_in_cache.delay(houses)
```
```python
# Wrong:
@celery_app.task(
    bind=True,
    soft_time_limit=8*60,
)
def verified_params(self, cad_numbers, rights: bool, main_characters: bool):
   """
   Таска на групповую сверку ряда кадастровых номеров. 
   Таска проводит сверку большой группы квартир, повторяя те же операции, 
   что и verify_area, verify_tenant и verify_all, но на большом объеме данных.
   :param self: celery таска
   :param cad_numbers: Список кадастровых номеров на проверку
   :param rights: Идет ли проверка записей о праве собственности
   :param main_characters: идет ли проверка значений площади помещения
   :return: Таска не возвращает значений
   """
    houses = VerifyAreaData.verify_by_cad_nums(
        cad_numbers, rights, main_characters
    )
    if houses:
        statistic_for_house_in_cache.delay(houses)
```
+ Документация должна быть представлена для всех самописных функций и классов.

## Typing
+ Для всех самописных функций и классов, обязательно использовать аннотации типов для всех аргументов и возвращаемых значений:
```python
# Correct:
class StartController:
    def __init__(self, bot: Bot, p2p: QiwiP2P) -> None:
        self.bot = bot
        self.p2p = p2p
```
```python
# Wrong:
class StartController:
    def __init__(self, bot, p2p):
        self.bot = bot
        self.p2p = p2p
```

## Рекомендации по программированию
+ Сравнения с синглтонами, такими как None, всегда должны выполняться с помощью `is` или `is not`, а не с операторами равенства.
+ Получайте исключения из `Exceptionа` не из `BaseException`. Прямое наследование `from BaseException` зарезервировано для исключений, перехват которых почти всегда является неправильным.
+ При перехвате исключений по возможности упоминайте конкретные исключения вместо использования голого `except`. Голое `except` будет перехватывать исключения `SystemExit` и `KeyboardInterrupt`, что усложнит прерывание программы с помощью Control-C и может замаскировать другие проблемы. Если вы хотите перехватывать все исключения, сигнализирующие об ошибках программы, используйте `except Exception: (bare except is equivalent to except BaseException:)`:
```python
try:
    import platform_specific_module
except ImportError:
    platform_specific_module = None
```
+ Для всех `try/except` ограничьте `try` абсолютным минимумом необходимого объема кода. Это позволяет избежать маскировки ошибок:
```python
# Correct:
try:
    value = collection[key]
except KeyError:
    return key_not_found(key)
else:
    return handle_value(value)
```
```python
# Wrong:
try:
    # Too broad!
    return handle_value(collection[key])
except KeyError:
    # Will also catch KeyError raised by handle_value()
    return key_not_found(key)
```
+ Используйте `''.startswith()` и `''.endswith()` вместо срезов строки для проверки префиксов или суффиксов:
```python
# Correct:
if foo.startswith('bar'):
```
```python
# Wrong:
if foo[:3] == 'bar':
```
+ При сравнении типов объектов всегда следует использовать `isinstance()` вместо прямого сравнения типо:
```python
# Correct:
if isinstance(obj, int):
```
```python
# Wrong:
if type(obj) is type(1):
```
+ Для последовательностей (строки, списки, кортежи) используйте тот факт, что пустые последовательности являются ложными:
```python
# Correct:
if not seq:
if seq:
```
```python
# Wrong:
if len(seq):
if not len(seq):
```
+ Не сравнивайте логические значения с `True` или `False`, используя `==`:
```python
# Correct:
if greeting:
```
```python
# Wrong:
if greeting == True:
```
```python
# Wrong:
if greeting is True:
```