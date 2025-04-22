from lib.helpfull_tools import exel_column_letter_generator

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


class BaseReport:
    XLSX_TEMPLATE = ''
    XLSX_WORKSHEETS = {}

    def __init__(self, **kwargs: dict):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def get_entries(self, produce_method_name):
        raise NotImplementedError()

    def get_xlsx_openpyxl(self, output_filename='/tmp/exmpl_rep.xlsx'):

        workbook = openpyxl.load_workbook(self.XLSX_TEMPLATE)

        for ws_title, ws_schema in self.XLSX_WORKSHEETS.items():
            worksheet = workbook.get_sheet_by_name(ws_title)
            print('creating page', ws_title)
            rows = self.get_entries(ws_schema['entry_produce_method'])
            columns = ws_schema['columns']
            for k, v in columns.items():
                if v.get('multicolumn'):
                    alphabet = exel_column_letter_generator(v['column'])
                    inner_dict = rows[k].values()
                    flat_vals = [x.values() for x in inner_dict]
                    for ind, row in enumerate(flat_vals, start=v['start_row']):
                        for ix, line in enumerate(row):
                            worksheet[alphabet[ix] + str(ind)] = line
                else:
                    vals = rows[k].values()
                    for ind, row in enumerate(vals, start=v['start_row']):
                        worksheet[v['column'] + str(ind)] = row

        workbook.save(output_filename)
