# _monsterold.py - extract former glottolog_ref_ids from old monster.bib files

import os
import re
import csv
import glob
import mmap
import sqlite3
import datetime
import contextlib
import collections

FILES = 'monsteroldv?*.bib'
DBFILE = '_monsterold.sqlite3'

ENTRY = re.compile(r'''
^@ (?P<entrytype> [^{]+) [{] (?P<bibkey> .*) , \s*$\n
    (?P<fields>(?:
        ^ [ ]{4} .*$\n
    )+)
^ [}] \r?$\n
''', re.VERBOSE | re.MULTILINE)

FIELD = re.compile(r'''
^ [ ]{4} (?P<field> \S+) [ ]=[ ] [{] (?P<value> .*) [}] ,?\s*$\n
''', re.VERBOSE | re.MULTILINE)


def iterfiles(pattern=FILES):
    def sortkey(filename):
        name, ext = os.path.splitext(filename)
        numeric = [int(x) if x.isdigit() else x for x in re.split('(\d+)', name) if x]
        return numeric, ext
    
    for bibfile in sorted(glob.glob(pattern), key=sortkey):
        mtime = datetime.datetime.fromtimestamp(os.stat(bibfile).st_mtime)
        dirname, basename = os.path.split(bibfile)
        name, ext = os.path.splitext(basename)
        csvfile = os.path.join(dirname, '%s.csv' % name)
        yield bibfile, mtime, csvfile


def iterentries(filename, fieldcls=dict):
    with open(filename, 'rb') as fd, contextlib.closing(mmap.mmap(fd.fileno(), 0,  access=mmap.ACCESS_READ)) as m:
        end = 0
        for match in ENTRY.finditer(m):
            if match.start() != end:
                raise RuntimeError('umatched entry', m[end:match.start()])
            entrytype, bibkey, fields = match.groups()
            fields = fieldcls(iterfields(fields))
            yield bibkey.strip(), (entrytype.strip(), fields)
            end = match.end()
        if end < len(m):
            raise RuntimeError('umatched entry', m[end:])


def iterfields(fields):
    end = 0
    for match in FIELD.finditer(fields):
        if match.start() > end:
            raise RuntimeError('unmatched field', fields[end:match.start()])
        field, value = match.groups()
        yield field.strip(), value.strip()
        end = match.end()
    if end < len(fields):
        raise RuntimeError('unmatched field', fields[end:])


def showstats(filename, ntop=10):
    count = 0
    counts = collections.Counter()
    for bibkey, (entrytype, fields) in iterentries(filename):
        count += 1
        counts.update(fields.iterkeys())
    print count
    print '\n'.join('%d\t%s' % (n, f) for f, n in counts.most_common(ntop))


def to_csv(bibfile, csvfile, sortkey=lambda (fn, bk, hs, id): (fn.lower(), bk.lower())):
    rows = sorted(iterrows(bibfile), key=sortkey)
    if not rows:
        print '...no matched entries, skipped'
        return
    with open(csvfile, 'wb') as fd:
        writer = csv.writer(fd)
        writer.writerow(['filename', 'bibkey', 'hash', 'id'])
        writer.writerows(rows)


def from_csv(filename):
    with open(filename, 'rb') as fd:
        reader = csv.reader(fd)
        header = next(reader)
        assert  header == ['filename', 'bibkey', 'hash', 'id']
        for row in reader:
            yield row
    

def iterrows(bibfile):
    skipped = 0
    for hash, (entrytype, fields) in iterentries(bibfile):
        if 'glottolog_ref_id' not in fields:
            continue
        id = int(fields['glottolog_ref_id'])
        if 'srctrickle' not in fields and hash.startswith('monster120903110921'):
            skipped += 1
            continue
        trickle = [s.partition('#')[::2] for s in fields['srctrickle'].split(', ')]
        for filename, bibkey in trickle:
            if filename == 'monster120903110921':
                skipped += 1
                continue
            yield filename, bibkey, hash, id
    if skipped:
        print '%d entries skipped' % skipped


def to_sqlite(filename=DBFILE):
    if os.path.exists(filename):
        os.remove(filename)
    with sqlite3.connect(filename) as conn:
        conn.execute('PRAGMA synchronous = OFF')
        conn.execute('PRAGMA journal_mode = MEMORY')
        conn.execute('CREATE TABLE monster ('
            'idx INTEGER NOT NULL PRIMARY KEY, '
            'name TEXT NOT NULL UNIQUE, '
            'mtime DATETIME NOT NULL UNIQUE)')
        conn.execute('CREATE TABLE entry ('
            'monster INTEGER NOT NULL, '
            'filename TEXT NOT NULL, '
            'bibkey TEXT NOT NULL, '
            'hash TEXT NOT NULL, '
            'id INTEGER, '
            'PRIMARY KEY (monster, filename, bibkey), '
            'FOREIGN KEY (monster) REFERENCES monster(idx))')
        conn.execute('CREATE INDEX ix_id ON entry(id)')
        for bibfile, mtime, csvfile in iterfiles():
            if not os.path.exists(csvfile):
                continue
            print csvfile
            rowid = conn.execute('INSERT INTO monster (name, mtime) '
                'VALUES (?, ?)', (bibfile, mtime)).lastrowid
            try:
                conn.executemany('INSERT INTO entry (monster, filename, bibkey, hash, id) '
                    'VALUES (?, ?, ?, ?, ?)',
                    ((rowid,) + tuple(row) for row in from_csv(csvfile)))
            except sqlite3.IntegrityError:
                print '...uniqueness problem, skipped'
                conn.rollback()
            else:
                conn.commit()


if __name__ == '__main__':
    for bibfile, mtime, csvfile in iterfiles():
        print bibfile, mtime
        #showstats(bibfile)
        to_csv(bibfile, csvfile)
    to_sqlite()
