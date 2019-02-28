# encoding: utf-8

import tempfile
from pathlib import PurePath, Path

import graphviz as gv


def _prep_dotsource(graphviz_tmpdir):
    """Create workdir for graphviz"""
    path = Path(graphviz_tmpdir)
    path.mkdir(mode=0o750, parents=True, exist_ok=True)


def view_dotsource(format, dotsource, graphviz_tmpdir, cleanup=True):
    """Generate and show the fsa structure

    This only makes sense to run on a local computer that has a monitor,
    and depends on the OS recognizing the format to find a program to open
    the result with.

    format: a format supported by graphviz
    doutsource: show dotsource, do not generate from this fsa"""
    _prep_dotsource(graphviz_tmpdir)
    graph = gv.Source(
        directory=str(graphviz_tmpdir),
        source=dotsource,
        format=format,
    )
    graph.view(filename=tempfile.mktemp('.{}'.format(format)), cleanup=cleanup)


def render_dotsource_to_file(format, filename, dotsource, graphviz_tmpdir, directory=''):
    """Generate and store a file of the fsa structure

    This will create a file at <filename> on the computer this software
    runs on.

    format: a format supported by graphviz
    filename: store the file locally at this location
    doutsource: show dotsource, do not generate from this fsa"""
    _prep_dotsource(graphviz_tmpdir)
    extension = '.' + format
    # remove directories, for great paranoia
    filename = PurePath(filename).name
    # The gv library saves as <filename> + <format> so remove any suffix
    try:
        filename = PurePath(filename).stem
    except AttributeError:
        assert False, (type(filename),)
    # Add subdir to default dir, if any
    try:
        directory = Path(directory).relative_to(graphviz_tmpdir)
    except ValueError:
        directory = Path(graphviz_tmpdir)
    directory.mkdir(mode=0o750, exist_ok=True, parents=True)
    graph = gv.Source(
        source=dotsource,
        format=format,
        filename=filename,
        directory=str(directory),
    )
    graph.render(cleanup=True)
    full_path = directory / PurePath(filename).with_suffix(extension)
    return full_path
