import logging
import os
import tempfile

try:  # импортируем если установлено (не импортируем, например, в eve-api)
    import openpyxl
    import pyoo
    import pyuno

    uno_exceptions = (
        pyuno.getClass('com.sun.star.uno.RuntimeException'),
        pyuno.getClass('com.sun.star.lang.DisposedException'),
        pyuno.getClass('com.sun.star.connection.NoConnectException'),
        OSError
    )
except ImportError:
    uno_exceptions = ()

from tools.fakefiles import InMemoryFile
from tools.pyoo_helpers import column_letter_to_number, MAX_COLUMNS, retry

import settings


logger = logging.getLogger('c300')


class BaseGISDataProducer:
    XLSX_TEMPLATE = ''
    XLSX_WORKSHEETS = {}

    def __init__(self, entries):
        self.entry_sources = entries

    def get_entries(self, produce_method_name, export_task, static_data=False):

        entries = []

        sources: list = [None] if static_data else self.entry_sources.values()
        for entry_source in sources:
            produce_method = getattr(self, produce_method_name)  # foo
            entry = produce_method(entry_source, export_task)
            if not entry:
                continue  # get_capital_repair_data -> None
            elif isinstance(entry, list) and \
                    all(isinstance(sub_entry, dict) for sub_entry in entry):
                for sub_entry in entry:
                    entries.append(sub_entry)
            elif isinstance(entry, dict):
                entries.append(entry)

        return entries

    def get_xlsx_openpyxl(self):

        memfile = InMemoryFile()

        workbook = openpyxl.load_workbook(self.XLSX_TEMPLATE)

        for ws_title, ws_schema in self.XLSX_WORKSHEETS.items():
            start_row = ws_schema['start_row']
            worksheet = workbook.get_sheet_by_name(ws_title)

            rows = self.get_entries(ws_schema['entry_produce_method'])
            columns = ws_schema['columns']

            for ind, row in enumerate(rows, start_row):
                for column in columns:
                    worksheet[columns[column] + str(ind)] = row.get(column, '')

        workbook.save(memfile)
        memfile.seek(0)

        return memfile

    @retry(
        exceptions=uno_exceptions,
        tries=4
    )
    def get_xlsx_pyoo(self, export_task):
        logger.info(
            'Task %s entered "%s.get_xlsx_pyoo"',
            export_task.id,
            self.__class__.__name__,
        )
        # docker run -d -m 2000M -p 8997:8997 -v /tmp:/tmp -v /home/nizovtsev/tmp/templates:/templates xcgd/libreoffice
        # TODO try-except
        desktop = pyoo.Desktop(settings.LO_DOCKER_HOST, settings.LO_DOCKER_PORT)
        logger.info('Task %s created libre-office Desktop', export_task.id)

        # Копируем шаблон в новый временный файл, для каждого создаваемого файла свой
        template_bytes = open(self.XLSX_TEMPLATE, 'rb').read()
        temp_file = tempfile.NamedTemporaryFile(dir='/tmp/', suffix='.xlsx')
        temp_file.write(template_bytes)
        temp_file.flush()

        spreadsheet = desktop.open_spreadsheet(
            '/tmp/' + os.path.basename(temp_file.name),
        )
        logger.info('Task %s opened sheet by libre-office', export_task.id)

        speadsheet_data = {
            ws_title: self.get_entries(
                ws_schema['entry_produce_method'],
                export_task,
                ws_schema.get('static_page', False)
            )
            for ws_title, ws_schema in self.XLSX_WORKSHEETS.items()
        }

        for ws_title, ws_schema in self.XLSX_WORKSHEETS.items():
            start_row = ws_schema['start_row']

            rows = speadsheet_data[ws_title]

            if rows:

                @retry(
                    exceptions=(KeyError, ),
                    tries=3
                )
                def get_sheet(sheet_name):
                    return spreadsheet.sheets[sheet_name]

                sheet = get_sheet(ws_title)
                values = []

                for row in rows:
                    row_values = ['' for i in range(MAX_COLUMNS)]

                    for k, v in row.items():
                        row_values[column_letter_to_number(ws_schema['columns'][k])] = v if v or isinstance(v, (int, float)) else ''

                    values.append(row_values)

                sheet[start_row - 1 : start_row + len(rows) - 1, 0 : MAX_COLUMNS].values = values

        spreadsheet.save(filter_name=pyoo.FILTER_EXCEL_2007)
        spreadsheet.close()

        # TODO del desktop ?

        temp_file.seek(0)
        memfile = InMemoryFile(temp_file.read())
        temp_file.close()

        logger.info(
            'Task %s left "%s.get_xlsx_pyoo"',
            export_task.id,
            self.__class__.__name__,
        )
        return memfile

