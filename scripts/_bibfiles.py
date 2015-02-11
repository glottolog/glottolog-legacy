# _bibfiles.py

import os
import io
import sqlite3

import operator
import itertools
import contextlib
import collections
import ConfigParser

import _bibtex

__all__ = ['Collection', 'BibFile', 'Database']

DIR = '../references/bibtex'
DBFILE = '_bibfiles.sqlite3'
BIBFILE = '_bibfiles.bib'


class Collection(list):

    _encoding = 'utf-8-sig'

    @classmethod
    def _bibfiles(cls, directory, config, endwith):
        config = os.path.join(directory, config)
        cfg = ConfigParser.RawConfigParser()
        with io.open(config, encoding=cls._encoding) as fp:
            cfg.readfp(fp)
        for s in cfg.sections():
            if not s.endswith(endwith):
                continue
            filepath = os.path.join(directory, s)
            assert os.path.exists(filepath)
            sortkey = cfg.get(s, 'sortkey')
            if sortkey.lower() == 'none':
                sortkey = None
            yield BibFile(filepath=filepath,
                encoding=cfg.get(s, 'encoding'), sortkey=sortkey,
                use_pybtex=cfg.getboolean(s, 'use_pybtex'),
                priority=cfg.getint(s, 'priority'),
                name=cfg.get(s, 'name'), title=cfg.get(s, 'title'),
                description=cfg.get(s, 'description'),
                abbr=cfg.get(s, 'abbr'))

    def __init__(self, directory=DIR, config='BIBFILES.ini', endwith='.bib'):
        self.directory = directory
        bibfiles = self._bibfiles(directory, config, endwith)
        super(Collection, self).__init__(bibfiles)
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
        return _bibtex.iterentries(self.filepath, self.encoding, self.use_pybtex)

    def load(self):
        preserve_order = self.sortkey is None
        return _bibtex.load(self.filepath, self.encoding, self.use_pybtex, preserve_order)

    def save(self, entries):
        _bibtex.save(entries, self.filepath, self.sortkey, self.encoding, self.use_pybtex)

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.filename)


class Database(object):

    @classmethod
    def from_collection(cls, bibfiles, filename):
        if os.path.exists(filename):
            os.remove(filename)

        self = cls(filename)
        db = self.connect(async=True)

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

        for b in bibfiles:
            print(b.filepath)
            b.use_pybtex = True
            db.execute('INSERT INTO file (name, priority) VALUES (?, ?)',
                (b.filename, b.priority))
            for bibkey, (entrytype, fields) in b.iterentries():
                db.execute('INSERT INTO entry (filename, bibkey) VALUES (?, ?)',
                    (b.filename, bibkey))
                fields = itertools.chain([('ENTRYTYPE', entrytype)], fields.iteritems())
                db.executemany('INSERT INTO value '
                    '(filename, bibkey, field, value) VALUES (?, ?, ?, ?)',
                    ((b.filename, bibkey, field, value) for field, value in fields))
            db.commit()
        self._entrystats(db)
        self._fieldstats(db)

        self._generate_hashes(db)
        db.close()
        return self

    @classmethod
    def _generate_hashes(cls, conn):
        from bib import wrds, keyid
        words = collections.Counter()
        cursor = conn.execute('SELECT value FROM value WHERE field = ?', ('title',))
        while True:
            rows = cursor.fetchmany(10000)
            if not rows:
                break
            for title, in rows:
                words.update(wrds(title))
        print('%d title words (from %d tokens)' % (len(words), sum(words.itervalues())))

        get_bibkey = operator.itemgetter(0)
        for filename, first, last in cls._windowed_entries(conn, 500):
            rows = conn.execute('SELECT bibkey, field, value FROM value '
                'WHERE filename = ? AND bibkey BETWEEN ? AND ? '
                'ORDER BY bibkey', (filename, first, last))
            conn.executemany('UPDATE entry SET hash = ? WHERE filename = ? AND bibkey = ?',
                ((keyid({k: v for b, k, v in grp}, words), filename, bibkey)
                for bibkey, grp in itertools.groupby(rows, get_bibkey)))
        conn.commit()
        conn.execute('CREATE INDEX IF NOT EXISTS ix_hash ON entry(hash)')
        cls._hashstats(conn)
        cls._hashidstats(conn)

    @staticmethod
    def _entrystats(conn):
        print('\n'.join('%s %d' % (f, n) for f, n in conn.execute(
            'SELECT filename, count(*) FROM entry GROUP BY filename')))
        print('%d entries total' % conn.execute('SELECT count(*) FROM entry').fetchone())

    @staticmethod
    def _fieldstats(conn, with_files=False):
        if with_files:
            print('\n'.join('%d\t%s\t%s' % (n, f, b) for f, n, b in conn.execute(
                'SELECT field, count(*) AS n, replace(group_concat(DISTINCT filename), ",", ", ") '
                'FROM value GROUP BY field ORDER BY n DESC, field')))
        else:
            print('\n'.join('%d\t%s' % (n, f) for f, n in conn.execute(
                'SELECT field, count(*) AS n '
                'FROM value GROUP BY field ORDER BY n DESC, field')))

    @staticmethod
    def _hashstats(conn):
        print('%d\tdistinct keyids (from %d total)' % conn.execute(
            'SELECT count(DISTINCT hash), count(hash) FROM entry').fetchone())
        print('\n'.join('%d\t%s (from %d distinct of %d total)' % row
            for row in conn.execute('SELECT coalesce(c2.unq, 0), '
            'c1.filename, c1.dst, c1.tot FROM (SELECT filename, '
            'count(hash) AS tot, count(DISTINCT hash) AS dst  '
            'FROM entry GROUP BY filename) AS c1 LEFT JOIN '
            '(SELECT filename, count(DISTINCT hash) AS unq '
            'FROM entry AS e WHERE NOT EXISTS (SELECT 1 FROM entry '
            'WHERE hash = e.hash AND filename != e.filename) '
            'GROUP BY filename) AS c2 ON c1.filename = c2.filename '
            'ORDER BY c1.filename')))
        print('%d\tin multiple files' % conn.execute('SELECT count(*) FROM '
            '(SELECT 1 FROM entry GROUP BY hash '
            'HAVING COUNT(DISTINCT filename) > 1)').fetchone())

    @staticmethod
    def _hashidstats(conn):
        print('\n'.join('1 keyid %d glottolog_ref_ids: %d' % (hash_nid, n)
            for (hash_nid, n) in conn.execute(
            'SELECT hash_nid, count(*) AS n FROM '
            '(SELECT count(DISTINCT v.value) AS hash_nid FROM entry AS e '
            'JOIN value AS v ON e.filename = v.filename AND e.bibkey = v.bibkey AND v.field = ? '
            'GROUP BY e.hash HAVING count(DISTINCT v.value) > 1) '
            'GROUP BY hash_nid ORDER BY n desc', ('glottolog_ref_id',))))
        print('\n'.join('1 glottolog_ref_id %d keyids: %d' % (id_nhash, n)
            for (id_nhash, n) in conn.execute(
            'SELECT id_nhash, count(*) AS n FROM '
            '(SELECT count(DISTINCT hash) AS id_nhash FROM entry AS e '
            'JOIN value AS v ON e.filename = v.filename AND e.bibkey = v.bibkey AND v.field = ? '
            'GROUP BY v.value HAVING count(DISTINCT e.hash) > 1) '
            'GROUP BY id_nhash ORDER BY n desc', ('glottolog_ref_id',))))

    @staticmethod
    def _windowed_entries(conn, chunksize):
        for filename, in conn.execute('SELECT name FROM file ORDER BY name'):
            cursor = conn.execute('SELECT bibkey FROM entry WHERE filename = ? '
                'ORDER BY bibkey', (filename,))
            while True:
                bibkeys = cursor.fetchmany(chunksize)
                if not bibkeys:
                    cursor.close()
                    break
                (first,), (last,) = bibkeys[0], bibkeys[-1]
                yield filename, first, last

    @staticmethod
    def _windowed_hashes(conn, chunksize):
        cursor = conn.execute('SELECT DISTINCT hash FROM entry ORDER BY hash')
        while True:
            hashes = cursor.fetchmany(chunksize)
            if not hashes:
                cursor.close()
                break
            (first,), (last,) = hashes[0], hashes[-1]
            yield first, last

    def __init__(self, filename=DBFILE):
        self.filename = filename

    def stats(self, field_files=False):
        with contextlib.closing(self.connect()) as conn:
            self._entrystats(conn)
            self._fieldstats(conn, field_files)
            self._hashstats(conn)
            self._hashidstats(conn)

    def connect(self, async=False):
        conn = sqlite3.connect(self.filename)
        if async:
            conn.execute('PRAGMA synchronous = OFF')
            conn.execute('PRAGMA journal_mode = MEMORY')
        return conn

    def __iter__(self, chunksize=100):
        with contextlib.closing(self.connect()) as db:
            nopriority, = db.execute('SELECT EXISTS (SELECT 1 FROM entry '
                'WHERE NOT EXISTS (SELECT 1 FROM file '
                'WHERE name = filename))').fetchone()
            assert not nopriority
            get_hash, get_field = operator.itemgetter(0), operator.itemgetter(1)
            for first, last in self._windowed_hashes(db, chunksize):
                cursor = db.execute('SELECT e.hash, v.field, v.value, v.filename, v.bibkey '
                    'FROM entry AS e '
                    'JOIN file AS f ON e.filename = f.name '
                    'JOIN value AS v ON e.filename = v.filename AND e.bibkey = v.bibkey '
                    'LEFT JOIN field AS d ON v.filename = d.filename AND v.field = d.field '
                    'WHERE e.hash BETWEEN ? AND ? '
                    'ORDER BY e.hash, v.field, coalesce(d.priority, f.priority) DESC, v.filename, v.bibkey',
                    (first, last))
                for hash, grp in itertools.groupby(cursor, get_hash):
                    yield (hash, [(field, [(vl, fn, bk) for hs, fd, vl, fn, bk in g])
                        for field, g in itertools.groupby(grp, get_field)])

    def merged(self, union={'lgcode', 'fn', 'asjp_name', 'hhtype', 'isbn'}):
        for hash, grp in self:
            fields = {field: values[0][0] if field not in union
                else ', '.join(unique(vl for vl, fn, bk in values))
                for field, values in grp}
            fields['src'] = ', '.join(sorted(set(fn
                for field, values in grp for vl, fn, bk in values)))
            fields['srctrickle'] = ', '.join(sorted(set('%s#%s' % (fn, bk)
                for field, values in grp for vl, fn, bk in values)))
            entrytype = fields.pop('ENTRYTYPE')
            yield hash, (entrytype, fields)

    def to_bibtex(self, filename=BIBFILE, encoding='utf-8'):
        with io.open(filename, 'w', encoding=encoding) as fd:
            _bibtex.dump(fd, self.merged())


def unique(iterable):
    seen = set()
    for item in iterable:
        if item not in seen:
            seen.add(item)
            yield item


def _test_merge():
    import sqlalchemy as sa

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
    #c.roundtrip_all()
    c.to_sqlite()
    #_test_merge()
