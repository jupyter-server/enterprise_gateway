from ..cell.parser import APICellParser
from os import path

class SwaggerSpecBuilder(object):
    value = { 'swagger' : '2.0', 'paths' : {}, 'info' : {'version' : '0.0.0', 'title' : 'Default Title'} }

    def __init__(self, kernel_spec):
        self.cell_parser = APICellParser(kernel_spec)

    def add_cell(self, cell_source):
        path_name, verb = self.cell_parser.get_cell_endpoint_and_verb(cell_source)
        path_value = {
            'responses' : {
                200 : { 'description': 'Success'}
            }
        }
        if not path_name in self.value['paths']:
            self.value['paths'][path_name] = {}
        self.value['paths'][path_name][verb.lower()] = path_value

    def set_title(self, title):
        basename = path.basename(title)
        self.value['info']['title'] = basename.split('.')[0] if basename.find('.') > 0 else basename

    def build(self):
        return self.value
