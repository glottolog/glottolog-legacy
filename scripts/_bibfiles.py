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
        db.execute('CREATE TABLE field ('
            'filename TEXT NOT NULL, '
            'field TEXT NOT NULL, '
            'priority INTEGER NOT NULL, '
            'PRIMARY KEY (filename, field), '
            'FOREIGN KEY(filename) REFERENCES file(name))')
        db.execute('CREATE TABLE entry ('
            'filename TEXT NOT NULL, '
            'bibkey TEXT NOT NULL, '
            'hash TEXT, '
            'PRIMARY KEY (filename, bibkey), '
            'FOREIGN KEY(filename) REFERENCES file(name))')
        db.execute('CREATE TABLE value ('
            'filename TEXT NOT NULL, '
            'bibkey TEXT NOT NULL, '
            'field TEXT NOT NULL, '
            'value TEXT NOT NULL, '
            'PRIMARY KEY (filename, bibkey, field), '
            'FOREIGN KEY(filename, bibkey) REFERENCES entry(filename, bibkey))')

        db.execute('PRAGMA synchronous = OFF')
        db.execute('PRAGMA journal_mode = MEMORY')

        for b in bibfiles:
            print(b.filepath)
            db.execute('INSERT INTO file (name, priority) VALUES (?, ?)',
                (b.filename, b.priority))
            for bibkey, (entrytype, fields) in b.iterentries():
                db.execute('INSERT INTO entry '
                    '(filename, bibkey) VALUES (?, ?)',
                    (b.filename, bibkey))
                db.executemany('INSERT INTO value '
                    '(filename, bibkey, field, value) VALUES (?, ?, ?, ?)',
                    ((b.filename, bibkey, field, value) for field, value in
                     itertools.chain([('ENTRYTYPE', entrytype)], fields.iteritems())))
            db.commit()
        print('\n'.join('%d %s' % (n, f) for f, n in db.execute(
            'SELECT filename, count(*) FROM entry GROUP BY filename')))
        print('%d entries' % db.execute('SELECT count(*) FROM entry').fetchone())

        words = collections.Counter()
        for title, in db.execute('SELECT value FROM value WHERE field = ?', ('title',)):
            words.update(bib.wrds(title))
        print('%d title words' % len(words))

        for filename, in db.execute('SELECT name FROM file ORDER BY name'):
            cursor = db.execute('SELECT bibkey FROM entry WHERE filename = ? '
                'ORDER BY bibkey', (filename,))
            while True:
                bibkeys = cursor.fetchmany(1000)
                if not bibkeys:
                    cursor.close()
                    break
                (first,), (last,) = bibkeys[0], bibkeys[-1]
                rows = db.execute('SELECT bibkey, field, value FROM value '
                    'WHERE filename = ? AND bibkey BETWEEN ? AND ? '
                    'ORDER BY bibkey', (filename, first, last))
                db.executemany('UPDATE entry SET hash = ? WHERE filename = ? AND bibkey = ?',
                    ((bib.keyid({k: v for b, k, v in grp}, words), filename, bibkey)
                    for bibkey, grp in itertools.groupby(rows, operator.itemgetter(0))))
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

    def _iter(self, chunksize=1000):
        with contextlib.closing(self.connect()) as db:
            nopriority, = db.execute('SELECT EXISTS (SELECT 1 FROM entry '
                'WHERE NOT EXISTS (SELECT 1 FROM file '
                'WHERE name = filename))').fetchone()
            assert not nopriority
            cursor = db.execute('SELECT e.hash, v.field, v.value, v.filename, v.bibkey '
                'FROM value AS v '
                'JOIN entry AS e ON v.filename = e.filename AND v.bibkey = e.bibkey '
                'JOIN file AS f ON v.filename = f.name '
                'LEFT JOIN field AS d ON v.filename = d.filename AND v.field = d.field '
                'ORDER BY e.hash, v.field, coalesce(d.priority, f.priority) DESC, v.filename, v.bibkey')
            while True:
                rows = cursor.fetchmany(chunksize)
                if not rows:
                    cursor.close()
                    return
                for r in rows:
                    yield r

    def __iter__(self, get_hash=operator.itemgetter(0), get_field=operator.itemgetter(1)):
        for hash, grp in itertools.groupby(self._iter(), get_hash):
            yield (hash, [(field, [(vl, fn, bk) for hs, fd, vl, fn, bk in g])
                for field, g in itertools.groupby(grp, get_field)])

    def merged(self, union={'lgcode', 'fn', 'asjp_name', 'hhtype', 'isbn'}):
        for hash, grp in self:
            fields = {field: values[0][0] if field not in union
                else ', '.join(vl for vl, fn, bk in values)
                for field, values in grp}
            fields['src'] = ', '.join(sorted(set(fn
                for field, values in grp for vl, fn, bk in values)))
            fields['srctrickle'] = ', '.join(sorted(set('%s#%s' % (fn, bk)
                for field, values in grp for vl, fn, bk in values)))
            entrytype = fields.pop('ENTRYTYPE')
            yield hash, (entrytype, fields)


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

    with contextlib.closing(Database().connect()) as conn, conn as conn:
        conn.executemany('UPDATE file SET priority = ? WHERE name = ?',
            ((b.priority, b.filename) for b in Collection()))

    UNION = {'lgcode', 'fn', 'asjp_name', 'hhtype', 'isbn'}

    for hash, grp in Database():
        for field, values in grp:
            if field in UNION:
                continue
            value1, file1, bibkey1 = values[0]
            for value2, file2, bibkey2 in values[1:]:
                if value1.lower() != value2.lower():
                    insert_ov(hash=hash, field=field, value1=value1, value2=value2,
                        file1=file1, bibkey1=bibkey1, file2=file2, bibkey2=bibkey2)


if __name__ == '__main__':
    c = Collection()
    c.to_sqlite()
    #c.roundtrip_all()
    #_test_merge()
