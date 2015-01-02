# bibtex.py - basic bibtex file parsing

import os
import glob
import io
import mmap
import contextlib
from pprint import pprint

from pybtex.database.input.bibtex import BibTeXEntryIterator
from pybtex.scanner import PybtexSyntaxError
from pybtex.textutils import normalize_whitespace

__all__ = ['load']


def load(filename, encoding=None):
    if encoding is None:
        with open(filename) as fd:
            with contextlib.closing(mmap.mmap(fd.fileno(), 0,  access=mmap.ACCESS_READ)) as m:
                result = dict(iterentries(m))
    else:
        with io.open(filename, encoding=encoding) as fd:
            source = fd.read()
        result = dict(iterentries(source))
    return result


def iterentries(source):
    try:
        for entrytype, (bibkey, fields) in BibTeXEntryIterator(source):
            fields = {name: normalize_whitespace(''.join(values))
                for name, values in fields}
            yield bibkey, (entrytype, fields)
    except PybtexSyntaxError as e:
        start, line, pos = e.error_context_info
        print('BIBTEX ERROR on line %d, last parsed entry:' % line)
        print(source[start:start+500] + '...')
        raise


def main(pattern='../../references/bibtex/*.bib'):
    for filename in glob.glob(pattern):
        print(filename)
        entries = load(filename)
        print(len(entries))
        pprint(next(entries.iteritems()))


if __name__ == '__main__':
    main()
