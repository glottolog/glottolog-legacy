# bibtex.py - basic bibtex file parsing

import glob
import re
import io
import collections

from pybtex.database.input.bibtex import BibTeXEntryIterator, Parser
from pybtex.scanner import PybtexSyntaxError
from pybtex.exceptions import PybtexError
from pybtex.textutils import normalize_whitespace
from pybtex.bibtex.utils import split_name_list
from pybtex.database import Person

import _bibfiles
import latexutf8

__all__ = ['load', 'dump']

FIELDS = [
    'author', 'editor', 'title', 'booktitle', 'journal',
    'school', 'publisher', 'address',
    'series', 'volume', 'number', 'pages', 'year', 'issn', 'url',
]


def load(filename, encoding=None):
    if encoding is None:
        with _bibfiles.memorymapped(filename) as source:
            result = dict(iterentries(source))
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


def names(s):
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


def dump(entries, fd, srtkey='author'):
    items = sorted(entries.iteritems(), key=sortkeys[srtkey])
    for bibkey, (entrytype, fields) in items:
        lines = ['@%s{%s' % (entrytype, bibkey)]
        for k, v in fieldorder.sorteddict(fields):
            v = latexutf8.utf8_to_latex(v.strip()).replace("\\_", "_").replace("\\#", "#").replace("\\\\&", "\\&")
            lines.append('    %s = {%s}' % (k, v))
        data = '%s\n}\n' % ',\n'.join(lines)
        fd.write(data)


def numkey(bibkey, nondigits=re.compile('(\D+)')):
    return tuple(try_int(s) for s in nondigit.split(bibkey))


def try_int(s):
    try:
        return int(s)
    except ValueError:
        return s


sortkeys = {
    'author': lambda (k, (typ, fields)): fields.get('author', '') + k.split(':', 1)[-1],
    'bibkey': lambda (k, (typ, fields)): k.lower(),
    'numkey': lambda (k, (typ, fields)): numkey(k.lower())
}


class Ordering(dict):

    _missing = float('inf')

    @classmethod
    def fromlist(cls, keys):
        return cls((k, i) for i, k in enumerate(keys))

    def sorteddict(self, dct):
         return sorted(dct.iteritems(), key=self._sorteddictkey)

    def _sorteddictkey(self, (key, value)):
         return self[key], key

    def __missing__(self, key):
        return self._missing


fieldorder = Ordering.fromlist(FIELDS)


def _test_dump():
    import bib
    from cStringIO import StringIO
    for filename in glob.glob('../references/bibtex/*.bib'):
        print filename
        entries = load(filename)
        a = bib.put(entries)
        s = StringIO()
        dump(entries, s)
        b = s.getvalue()
        assert a == b


if __name__ == '__main__':
    for filename in glob.glob('../references/bibtex/*.bib'):
        print(filename)
        entries = load(filename)
        print(len(entries))
        print('%d invalid' % check(filename))
