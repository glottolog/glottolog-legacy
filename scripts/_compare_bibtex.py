# _compare_bibtex - compare regex-based with pybtex bibfile parsing

import glob

import bib
import _bibtex


def compare(filename):
    print filename
    d = bib.get(filename)
    e = _bibtex.load(filename, 'utf-8')
    if d.keys() != e.keys():
        print sorted(set(d).symmetric_difference(e))
    for k in e:
        x = d[k][1]
        y = e[k][1]
        if x.keys() != y.keys():
            print k
            print repr(x.keys())
            print repr(y.keys())
        for field in x:
            if x[field].decode('utf-8') != y[field]:
                print k
                print field
                print repr(x[field])
                print repr(y[field])


for filename in glob.glob('../references/bibtex/*.bib'):
    compare(filename)
