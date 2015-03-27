# justifications.py

import io
import re
import csv
import glob
import collections

REF = re.compile(r'\*\*(\d+)\*\*(?:([\d\-]+))?')

FAMILY = glob.glob('../languoids/*_family_justifications-utf8.tab')[0]
SUBCLASS = glob.glob('../languoids/*_subclassification_justifications-utf8.tab')[0]


def iterrows(filename, ncols, dialect='excel-tab', encoding='utf-8'):
    with open(filename, 'rb') as fd:
        for row in csv.reader(fd, dialect=dialect):
            cols = [c.decode(encoding) for c in row]
            if len(cols) != ncols:
                raise ValueError(cols)
            yield cols


def families(filename=FAMILY, Row=collections.namedtuple('Row', 'name1 name2 refs comment')):
    for name1, name2, refs, comment in iterrows(filename, 4):
        refs = [int(REF.match(r).group(1)) for r in refs.split(', ')]
        yield Row(name1, name2, refs, comment)


def subclass(filename=SUBCLASS, Row=collections.namedtuple('Row', 'name1 name2 comment')):
    for name1, name2, comment in iterrows(filename, 3):
        yield Row(name1, name2, comment)

        
if __name__ == '__main__':
    f = list(families())
    s = list(subclass())
