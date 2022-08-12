import sys
import csv

from .models import createupdate_rdakey
from .models import createupdate_rda_question_link
from .models import createupdate_rda_section_link


def load_rdadcs_from_csv(file, stderr=sys.stderr, csv_options=None, show_warnings=True):
    if not csv_options:
        csv_options = {'delimiter': '\t'}
    tabreader = csv.DictReader(file, fieldnames=('path', 'type'), **csv_options)
    for line in tabreader:
        path = line['path']
        input_type = line.get('type', None)
        warnings = createupdate_rdakey(path, input_type)
        if show_warnings:
            for warning in warnings:
                stderr.write(warning)


def dump_rdadcs_to_csv(paths_types, file, stderr=sys.stderr, csv_options=None):
    "paths_types is an iterator of (path, input_type)"
    if not csv_options:
        csv_options = {'delimiter': '\t'}
    tabwriter = csv.writer(file, **csv_options)
    for key, it in paths_types:
        it = it if it else ''
        tabwriter.writerow([key, it])


def load_rdapth_from_csv(file, function, stderr=sys.stderr, csv_options=None):
    if not csv_options:
        csv_options = {'delimiter': '\t'}
    tabreader = csv.DictReader(file, fieldnames=('path', 'pk'), **csv_options)
    for line in tabreader:
        if not line['pk']: continue
        path = line['path']
        pk = int(line['pk'])
        try:
            function(path, pk)
        except ValueError as e:
            stderr.write(str(e))


def load_rdapth_to_question_from_csv(file, stderr=sys.stderr, csv_options=None):
    return load_rdapth_from_csv(
        file,
        createupdate_rda_question_link,
        stderr,
        csv_options,
    )


def load_rdapth_to_section_from_csv(file, stderr=sys.stderr, csv_options=None):
    return load_rdapth_from_csv(
        file,
        createupdate_rda_section_link,
        stderr,
        csv_options,
    )
