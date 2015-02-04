# _compare_names.py - compare regex-based with pybtex name parsing

import _bibfiles

import bib
import _bibtex


def names1(s):
    return [(n.get('firstname', ''), n.get('lastname', ''), n.get('jr', ''))
        for n in bib.pauthor(s)]


def names2(s):
    return [(first, ' '.join(n for n in (prelast, last) if n), lineage)
        for prelast, last, first, lineage in _bibtex.names(s)]


for b in _bibfiles.Collection():
    print b.filename.center(80, '#')
    for bibkey, (entrytype, fields) in b.iterentries(use_pybtex=True):
        for role in ('author', 'editor'):
            names = fields.get(role, '')
            n1, n2 = names1(names), names2(names)
            if n1 != n2:
                print b.filename, bibkey, role
                print repr(names)
                print n1
                print n2
                print
