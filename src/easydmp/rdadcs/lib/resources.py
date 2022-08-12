from importlib.resources import open_text, read_text
import json

from easydmp.eestore.utils import fill_cache_from_class
import easydmp.rdadcs.data.large_controlled_vocabularies as lcv
from easydmp.rdadcs.lib.csv import load_rdadcs_from_csv


__all__ = [
    'load_rdadcs_eestore_cache_modelresource',
    'load_rdadcs_keymapping_modelresource',
    'load_rdadcs_template_dictresource',
]


RDADCS_KEYFILE = ('easydmp.rdadcs.data', 'rdadcs-v1.tsv')
RDADCS_TEMPLATE = ('easydmp.rdadcs.data', 'rdadcs-v1.1.template.json')


def load_rdadcs_eestore_cache_modelresource():
    classes = [cls for cls in map(lcv.__dict__.get, lcv.__all__)]
    for cls in classes:
        source = fill_cache_from_class(cls)
        yield source


def load_rdadcs_keymapping_modelresource(show_warnings=True):
    with open_text(*RDADCS_KEYFILE) as F:
        load_rdadcs_from_csv(F, show_warnings=show_warnings)


def load_rdadcs_template_dictresource():
    textblob = read_text(*RDADCS_TEMPLATE)
    return json.loads(textblob)
