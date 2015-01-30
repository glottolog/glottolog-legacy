# bibtex.py - basic bibtex file parsing

import os
import glob
import io
import mmap
import contextlib
import collections
from pprint import pprint

from pybtex.database.input.bibtex import BibTeXEntryIterator, Parser
from pybtex.scanner import PybtexSyntaxError
from pybtex.exceptions import PybtexError
from pybtex.textutils import normalize_whitespace
from pybtex.bibtex.utils import split_name_list
from pybtex.database import Person

__all__ = ['load']


def load(filename, encoding=None):
    if encoding is None:
        with memorymapped(filename) as source:
            result = dict(iterentries(source))
    else:
        with io.open(filename, encoding=encoding) as fd:
            source = fd.read()
        result = dict(iterentries(source))
    return result


@contextlib.contextmanager
def memorymapped(filename, access=mmap.ACCESS_READ):
    try:
        fd = open(filename)
        m = mmap.mmap(fd.fileno(), 0,  access=access)
        yield m
    finally:
        m.close()
        fd.close()
    

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


def contributors(s):
    for name in split_name_list(s):
        try:
            yield Name.from_string(name)
        except PybtexError as e:
            print e


class Name(collections.namedtuple('Name', 'prelast last given lineage')):

    __slots__ = ()

    @classmethod
    def from_string(cls, name):
        person = Person(name)
        prelast, last, first, middle, lineage = (' '.join(getattr(person, part))
            for part in ('_prelast', '_last', '_first', '_middle', '_lineage'))
        given = ' '.join(n for n in (first, middle) if n)
        return cls(prelast, last, given, lineage)
    

if __name__ == '__main__':
    for filename in glob.glob('../references/bibtex/*.bib'):
        print(filename)
        entries = load(filename)
        print(len(entries))
        #pprint(next(entries.iteritems()))
        print('%d invalid' % check(filename))
