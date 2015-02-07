# _bibfiles.py

import os
import io
import glob
import json
import sqlite3
import operator
import itertools
import contextlib
import collections
import ConfigParser

__all__ = ['Collection', 'BibFile', 'Database']

DIR = '../references/bibtex'
DBFILE = '_bibfiles.sqlite3'


class Collection(list):

    _encoding = 'utf-8-sig'

    def __init__(self, directory=DIR, config='BIBFILES.ini', endwith='.bib'):
        self.directory = directory
        config = os.path.join(directory, config)
        p = ConfigParser.RawConfigParser()
        with io.open(config, encoding=self._encoding) as fp:
            p.readfp(fp)
        kwargs = [{'filepath': os.path.join(directory, s),
            'encoding': p.get(s, 'encoding'), 'sortkey': p.get(s, 'sortkey'),
            'use_pybtex': p.getboolean(s, 'use_pybtex'),
            'priority': p.getint(s, 'priority'),
            'name': p.get(s, 'name'), 'title': p.get(s, 'title'),
            'description': p.get(s, 'description'), 'abbr': p.get(s, 'abbr')}
            for s in p.sections() if s.endswith(endwith)]
        super(Collection, self).__init__(BibFile(**kw) for kw in kwargs)
        self._map = {b.filename: b for b in self}

    def __getitem__(self, index_or_filename):
        if isinstance(index_or_filename, basestring):
            return self._map[index_or_filename]
        return super(Collection, self).__getitem__(index_or_filename)

    def roundtrip_all(self):
        for b in self:
            print(b)
            b.save(b.load())

    def to_sqlite(self, filename=DBFILE):
        return Database.from_collection(self, filename)


class BibFile(object):

    def __init__(self, filepath, encoding, sortkey, use_pybtex=False, priority=0,
                 name=None, title=None, description=None, abbr=None):
        assert os.path.exists(filepath)
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.encoding = encoding
        self.sortkey = sortkey
        self.use_pybtex = use_pybtex
        self.priority = priority
        self.name = name
        self.title = title
        self.description = description
        self.abbr = abbr

    def iterentries(self):
        import _bibtex
        return _bibtex.iterentries(self.filepath, self.encoding, self.use_pybtex)

    def load(self):
        import _bibtex
        return _bibtex.load(self.filepath, self.encoding, self.use_pybtex)

    def save(self, entries):
        import _bibtex
        _bibtex.save(entries, self.filepath, self.sortkey, self.encoding, self.use_pybtex)

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.filename)


class Database(object):

    @classmethod
    def from_collection(cls, bibfiles, filename):
        import bib
        if os.path.exists(filename):
            os.remove(filename)

        self = cls(filename)
        db = self.connect()

        db.execute('CREATE TABLE file ('
            'name TEXT NOT NULL, '
            'priority INTEGER NOT NULL, '
            'PRIMARY KEY (name))')
        db.execute('CREATE TABLE entry ('
            'filename TEXT NOT NULL, '
            'bibkey TEXT NOT NULL, '
            'entrytype TEXT NOT NULL, '
            'hash TEXT, '
            'fields TEXT NOT NULL, '
            'title TEXT, '
            'PRIMARY KEY (filename, bibkey), '
            'FOREIGN KEY(filename) REFERENCES file(name))')

        db.execute('PRAGMA synchronous = OFF')
        db.execute('PRAGMA journal_mode = MEMORY')

        for b in bibfiles:
            print(b.filepath)
            db.execute('INSERT INTO file (name, priority) VALUES (?, ?)',
                (b.filename, b.priority))  
            db.executemany('INSERT INTO entry '
                '(filename, bibkey, entrytype, fields, title) VALUES (?, ?, ?, ?, ?)',
                ((b.filename, bibkey, entrytype, json.dumps(fields), fields.get('title'))
                for bibkey, (entrytype, fields) in b.iterentries()))
            db.commit()
        print('\n'.join('%d %s' % (n, f) for f, n in db.execute(
            'SELECT filename, count(*) FROM entry GROUP BY filename')))
        print('%d entries' % db.execute('SELECT count(*) FROM entry').fetchone())

        words = collections.Counter()
        for title, in db.execute('SELECT title FROM entry WHERE title IS NOT NULL'):
            words.update(bib.wrds(title))
        print('%d title words' % len(words))

        cursor = db.execute('SELECT filename, bibkey, fields FROM entry')
        while True:
            rows = cursor.fetchmany(1000)
            if not rows:
                cursor.close()
                break
            db.executemany('UPDATE entry SET hash = ? WHERE filename = ? AND bibkey = ?',
                ((bib.keyid(json.loads(fields), words), filename, bibkey)
                for filename, bibkey, fields in rows))
            db.commit()
        db.execute('CREATE INDEX ix_hash ON entry(hash)')
        print('%d keyids' % db.execute('SELECT count(hash) FROM entry').fetchone())
        print('%d distinct keyids' % db.execute('SELECT count(DISTINCT hash) FROM entry').fetchone())
        db.close()
        return self

    def __init__(self, filename=DBFILE):
        self.filename = filename

    def connect(self):
        return sqlite3.connect(self.filename)

    def _iter(self):
        with contextlib.closing(self.connect()) as db:
            nopriority, = db.execute('SELECT EXISTS (SELECT 1 FROM entry '
                'WHERE NOT EXISTS (SELECT 1 FROM file '
                'WHERE name = filename))').fetchone()
            assert not nopriority
            cursor = db.execute('SELECT hash, filename, bibkey, entrytype, fields '
                'FROM entry JOIN file ON filename = name '
                'ORDER BY hash, priority DESC, filename, bibkey')
            while True:
                rows = cursor.fetchmany(1000)
                if not rows:
                    cursor.close()
                    return
                for hs, fn, bk, et, fs in rows:
                    yield hs, fn, bk, et, json.loads(fs)

    def __iter__(self):
        for hs, group in itertools.groupby(self._iter(), operator.itemgetter(0)):
            yield hs, [(fn, bk, et, fs) for hs, fn, bk, et, fs in group]


def _test_merge():
    import sqlalchemy as sa
    from itertools import chain

    engine = sa.create_engine('postgresql://postgres@/overrides')
    metadata = sa.MetaData()
    overrides = sa.Table('overrides', metadata,
        sa.Column('hash', sa.Text, primary_key=True),
        sa.Column('field', sa.Text, primary_key=True),
        sa.Column('file1', sa.Text, primary_key=True),
        sa.Column('bibkey1', sa.Text, primary_key=True),
        sa.Column('file2', sa.Text, primary_key=True),
        sa.Column('bibkey2', sa.Text, primary_key=True),
        sa.Column('value1', sa.Text),
        sa.Column('value2', sa.Text))
    metadata.drop_all(engine)
    metadata.create_all(engine)
    insert_ov = overrides.insert(bind=engine).execute

    UNION = {'lgcode', 'fn', 'asjp_name', 'hhtype', 'isbn'}
    ET = type('entrytype', (object,), {'__str__': lambda self: self.__class__.__name__})()

    with contextlib.closing(Database().connect()) as conn, conn as conn:
        conn.executemany('UPDATE file SET priority = ? WHERE name = ?',
            ((b.priority, b.filename) for b in Collection()))

    for hash, grp in Database():
        merged, overrider = {}, {}
        for filename, bibkey, entrytype, fields in grp:
            for field, value in chain([(ET, entrytype)], fields.iteritems()):
                if field in UNION:
                    continue
                elif field not in merged:
                    merged[field] = value
                    overrider[field] = (filename, bibkey)
                elif value.lower() != merged[field].lower():
                    ofilename, obibkey = overrider[field]
                    insert_ov(hash=hash, field=str(field),
                        file1=ofilename, bibkey1=obibkey, value1=merged[field],
                        file2=filename, bibkey2=bibkey, value2=value)


if __name__ == '__main__':
    c = Collection()
    c.to_sqlite()
    #c.roundtrip_all()
    #_test_merge()
