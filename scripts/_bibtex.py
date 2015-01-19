# bibtex.py - basic bibtex file parsing

import os
import glob
import io
import mmap
import contextlib
from pprint import pprint

from pybtex.database.input.bibtex import BibTeXEntryIterator, Parser
from pybtex.scanner import PybtexSyntaxError
from pybtex.exceptions import PybtexError
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
            fields = {name.lower(): normalize_whitespace(''.join(values))
                for name, values in fields}
            yield bibkey, (entrytype, fields)
    except PybtexSyntaxError as e:
        start, line, pos = e.error_context_info
        print('BIBTEX ERROR on line %d, last parsed entry:' % line)
        print(source[start:start+500] + '...')
        raise


def check(filename):
    parser = CheckParser()
    parser.parse_file(filename)
    return parser.error_count
    

class CheckParser(Parser):
    def __init__(self, *args, **kwargs):
        super(CheckParser, self).__init__(*args, **kwargs)
        self.error_count = 0
    def process_entry(self, *args, **kwargs):
        try:
            super(CheckParser, self).process_entry(*args, **kwargs)
        except PybtexError as e:
            print e
            self.error_count +=1


if __name__ == '__main__':    
    for filename in glob.glob('../references/bibtex/*.bib'):
        print(filename)
        entries = load(filename)
        print(len(entries))
        #pprint(next(entries.iteritems()))
        print('%d invalid' % check(filename))
