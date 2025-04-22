import json
from collections import OrderedDict
from rest_framework.parsers import MultiPartParser, DataAndFiles


class MultipartJsonParser(MultiPartParser):

    def parse(self, stream, media_type=None, parser_context=None):
        result = super().parse(
            stream,
            media_type=media_type,
            parser_context=parser_context
        )
        query_dict = OrderedDict()
        for k, v in result.data.items():
            try:
                value = json.loads(v)
            except json.JSONDecodeError:
                value = v
            query_dict[k] = value
        return DataAndFiles(query_dict, result.files)
