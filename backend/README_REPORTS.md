## Описание работы с бессхемными отчетами

#### В чем их смысл?

В том, что базовый стандартный отчет использует строгую схему и 
данные нужно подстраивать под него. Иногда это неудобно, особенно если 
нужно сделать мелкий отчет или сделать его не блевотным.

#### Как пользоваться на бэке?


```python

class MeterReadingsViewSet(BaseSchemeLessReportViewSet):
    """
    Отчет по показаниям счетчиков
    """
    REPORT = MeterReadingsReport
    SERIALIZER = MeterReadingsReportSerializer

```

- создать `ViewSet` унаследованный от `BaseSchemeLessReportViewSet`

- переопределить атрибут `SERIALIZER` сериалайзером, который
обработает тело POST запроса

- переопределить атрибут `REPORT` классом, унаследованным от `BaseSchemeLessReport`
и в нем перезагрузить метод `get_binary`, который всегда должен возвращать
два объекта: бинарник отчета (.xlsx) и имя файла с расширением

    ```python
    class MeterReadingsReport(BaseSchemeLessReport):
    
        def get_binary(self, meta, **kwargs):
            date_from, date_till = kwargs['date_from'], kwargs['date_till']
            data, caption = self.get_data(kwargs['area'], date_from, date_till)
            return self.create_report(data, caption)
    ```
    
Важно понимать, что `get_binary` принимает аргумент **meta** и 
неограниченное кол-во именованных параметров **kwargs**, где:
- meta - метаданные, которые присутсвуют всегда (привязки, провайдер и actor)
- kwargs - все остальные параметры, которые были обработаны сериалайзером


#### Как пользоваться на фронте?

- сделать POST запрос на такой отчет, передавая в теле необходиме данные
и получить в ответ ID операции

    Пример:
    
        POST /api/v4/report/meters/readings/
        
        Параметры:
        {
            "area": "5d028358b6cae700011f3379",
            "date_from": "2018-08-01T00:00:00",
            "date_till": "2019-09-01T00:00:00"
        }
        
        Ответ:
        "5d67e004b9f23452c651a275"

- сделать GET запрос с указанием полученного ID и передачей 
параметра status=true
    
    В результате будет возвращён один из 4 статусов:
    - `failed` - ошибка при формировании отчета
    - `ready` - готов
    - `wip` - в работе
    - `new` - еще не взят в работу
    
    Пример:
    
        GET /api/v4/report/meters/readings/5d67e6bc2d1c4900095470f8/?status=true
    
    Ответ:
    
        {"state": "ready"}

- сделать GET запрос с указанием полученного ID без передачи каких либо параметров

    Пример:
    
        GET /api/v4/report/meters/readings/5d67e6bc2d1c4900095470f8/
    
    Ответ:
    binary data (сам отчет)



#### Enjoy your report!