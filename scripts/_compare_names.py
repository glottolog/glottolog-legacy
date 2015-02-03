# _compare_names.py - compare regex-based with pybtex name parsing

import glob

import bib
import _bibtex


def pauthor1(s):
    return [(n.get('firstname', ''), n.get('lastname', ''), n.get('jr', ''))
        for n in bib.pauthor(s)]


def pauthor2(s):
    return [(first, ' '.join(n for n in (prelast, last) if n), lineage)
        for prelast, last, first, lineage in _bibtex.names(s)]


for filename in glob.glob('../references/bibtex/*.bib'):
    entries = _bibtex.load(filename)
    for bibkey, (entrytype, fields) in entries.iteritems():
        author = fields.get('author', '')
        a1, a2 = pauthor1(author), pauthor2(author)
        if a1 != a2:
            print filename, bibkey
            print repr(author)
            print a1
            print a2
            print
