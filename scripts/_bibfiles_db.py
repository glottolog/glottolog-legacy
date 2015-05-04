# _bibfiles_db.py

import os
import sqlite3
import difflib
import operator
import itertools
import contextlib
import collections

import _bibtex

__all__ = ['Database']

DBFILE = '_bibfiles.sqlite3'

BIBFILE = '_bibfiles.bib'

UNION_FIELDS = {'lgcode', 'fn', 'asjp_name', 'hhtype', 'isbn'}


class Database(object):

    @classmethod
    def from_bibfiles(cls, bibfiles=None, filename=None, page_size=32768):
        if bibfiles is None:
            from _bibfiles import Collection
            bibfiles = Collection()

        if filename is None:
            filename = DBFILE
            
        if os.path.exists(filename):
            os.remove(filename)

        self = cls(filename)
        with self.connect(async=True, page_size=page_size) as conn:
            create_tables(conn)
            with conn:
                import_bibfiles(conn, bibfiles)
            entrystats(conn)
            fieldstats(conn)

            with conn:
                generate_hashes(conn)
            hashstats(conn)
            hashidstats(conn)

            with conn:
                assign_ids(conn)

        return self

    def __init__(self, filename=None):
        if filename is None:
            filename = DBFILE
        self.filename = filename

    def recompute(self):
        with self.connect(async=True) as conn:
            with conn:
                generate_hashes(conn)
            hashstats(conn)
            hashidstats(conn)
            with conn:
                assign_ids(conn)

    def connect(self, async=False, close=True, page_size=None):
        conn = sqlite3.connect(self.filename)
        if async:
            conn.execute('PRAGMA synchronous = OFF')
            conn.execute('PRAGMA journal_mode = MEMORY')
        if page_size is not None:
            conn.execute('PRAGMA page_size = %d' % page_size)
        if close:
            conn = contextlib.closing(conn)
        return conn

    def stats(self, field_files=False):
        with self.connect() as conn:
            entrystats(conn)
            fieldstats(conn, field_files)
            hashstats(conn)
            hashidstats(conn)

    def to_bibfile(self, filename=BIBFILE, encoding='utf-8'):
        _bibtex.save(self.merged(), filename, sortkey=None, encoding=encoding)

    def __iter__(self, chunksize=100):
        with self.connect() as conn:
            allid, = conn.execute('SELECT NOT EXISTS (SELECT 1 FROM entry '
                'WHERE id IS NULL)').fetchone()
            assert allid
            allpriority, = conn.execute('SELECT NOT EXISTS '
                '(SELECT 1 FROM entry WHERE NOT EXISTS (SELECT 1 FROM file '
                'WHERE name = filename))').fetchone()
            assert allpriority

            get_id_hash, get_field = operator.itemgetter(0, 1), operator.itemgetter(2)
            for first, last in windowed(conn, 'id', chunksize):
                cursor = conn.execute('SELECT e.id, e.hash, v.field, v.value, v.filename, v.bibkey '
                    'FROM entry AS e '
                    'JOIN file AS f ON e.filename = f.name '
                    'JOIN value AS v ON e.filename = v.filename AND e.bibkey = v.bibkey '
                    'LEFT JOIN field AS d ON v.filename = d.filename AND v.field = d.field '
                    'WHERE e.id BETWEEN ? AND ? '
                    'ORDER BY e.id, v.field, coalesce(d.priority, f.priority) DESC, v.filename, v.bibkey',
                    (first, last))
                for id_hash, grp in itertools.groupby(cursor, get_id_hash):
                    yield (id_hash, [(field, [(vl, fn, bk) for id, hs, fd, vl, fn, bk in g])
                        for field, g in itertools.groupby(grp, get_field)])

    def merged(self):
        for (id, hash), grp in self:
            entrytype, fields = self._merged_entry(grp)
            fields['glottolog_ref_hash'] = hash
            yield id, (entrytype, fields)

    def __getitem__(self, key):
        if not isinstance(key, (int, basestring)):
            raise ValueError
        with self.connect() as conn:
            grp = self._entrygrp(conn, key)
            entrytype, fields = self._merged_entry(grp)
            return key, (entrytype, fields)

    @staticmethod
    def _merged_entry(grp, union=UNION_FIELDS):
        fields = {field: values[0][0] if field not in union
            else ', '.join(unique(vl for vl, fn, bk in values))
            for field, values in grp}
        fields['src'] = ', '.join(sorted(set(fn
            for field, values in grp for vl, fn, bk in values)))
        fields['srctrickle'] = ', '.join(sorted(set('%s#%s' % (fn, bk)
            for field, values in grp for vl, fn, bk in values)))
        entrytype = fields.pop('ENTRYTYPE')
        return entrytype, fields

    @staticmethod
    def _entrygrp(conn, key, legacy=False, get_field=operator.itemgetter(0)):
        col = 'refid' if isinstance(key, int) else 'hash'
        if legacy:
            extra_join = 'JOIN legacypriority AS l ON e.bibkey = l.bibkey '
            order = "ORDER BY v.field, v.filename != 'hh.bib', v.filename, l.priority"
        else:
            extra_join = ''
            order = 'ORDER BY v.field, coalesce(d.priority, f.priority) DESC, v.filename, v.bibkey'
        cursor = conn.execute(('SELECT v.field, v.value, v.filename, v.bibkey '
            'FROM entry AS e '
            'JOIN file AS f ON e.filename = f.name '
            + extra_join +
            'JOIN value AS v ON e.filename = v.filename AND e.bibkey = v.bibkey '
            'LEFT JOIN field AS d ON v.filename = d.filename AND v.field = d.field '
            'WHERE %s = ? ' + order) % col, (key,))
        grp = [(field, [(vl, fn, bk) for fd, vl, fn, bk in g])
            for field, g in itertools.groupby(cursor, get_field)]
        if not grp:
            raise KeyError(key)
        return grp

    def show_splits(self, verbose=True):
        with self.connect() as conn:
            cursor = conn.execute('SELECT refid, hash, filename, bibkey '
            'FROM entry AS e WHERE EXISTS (SELECT 1 FROM entry '
            'WHERE refid = e.refid AND hash != e.hash) '
            'ORDER BY refid, hash, filename, bibkey')
            for refid, group in itertools.groupby(cursor, operator.itemgetter(0)):
                group = list(group)
                for row in group:
                    print(row)
                if verbose:
                    for ri, hs, fn, bk in group:
                        print('\t%r, %r, %r, %r' % hashfields(conn, fn, bk))
                    # FIXME: remove legacy mode after migration
                    old = self._merged_entry(self._entrygrp(conn, refid, legacy=True))[1]
                    cand = [(hs, self._merged_entry(self._entrygrp(conn, hs))[1])
                        for hs in unique(hs for ri, hs, fn, bk in group)]
                    new = min(cand, key=lambda (hs, fields): distance(old, fields))[0]
                    print('-> %s' % new)
                print

    def show_merges(self, verbose=True):
        with self.connect() as conn:
            cursor = conn.execute('SELECT hash, refid, filename, bibkey '
            'FROM entry AS e WHERE EXISTS (SELECT 1 FROM entry '
            'WHERE hash = e.hash AND refid != e.refid) '
            'ORDER BY hash, refid, filename, bibkey')
            for hash, group in itertools.groupby(cursor, operator.itemgetter(0)):
                group = list(group)
                for row in group:
                    print(row)
                if verbose:
                    for hs, ri, fn, bk in group:
                        print('\t%r, %r, %r, %r' % hashfields(conn, fn, bk))
                print

    def show_identified(self):
        with self.connect() as conn:
            cursor = conn.execute('SELECT hash, filename, bibkey '
            'FROM entry AS e WHERE refid IS NULL AND EXISTS (SELECT 1 FROM entry '
            'WHERE refid IS NULL AND hash = e.hash AND bibkey != e.bibkey) '
            'ORDER BY hash, filename, bibkey')
            for hash, group in itertools.groupby(cursor, operator.itemgetter(0)):
                group = list(group)
                for row in group:
                    print(row)
                for hs, fn, bk in group:
                    print('\t%r, %r, %r, %r' % hashfields(conn, fn, bk))
                print


def create_tables(conn):
    conn.execute('CREATE TABLE file ('
        'name TEXT NOT NULL, '
        'size INTEGER NOT NULL, '
        'mtime DATETIME NOT NULL, '
        'priority INTEGER NOT NULL, '
        'PRIMARY KEY (name))')
    conn.execute('CREATE TABLE field ('
        'filename TEXT NOT NULL, '
        'field TEXT NOT NULL, '
        'priority INTEGER NOT NULL, '
        'PRIMARY KEY (filename, field), '
        'FOREIGN KEY (filename) REFERENCES file(name))')
    conn.execute('CREATE TABLE entry ('
        'filename TEXT NOT NULL, '
        'bibkey TEXT NOT NULL, '
        'refid INTEGER, '
        'hash TEXT, '
        'id INTEGER, '
        'PRIMARY KEY (filename, bibkey), '
        'FOREIGN KEY (filename) REFERENCES file(name))')
    conn.execute('CREATE INDEX ix_refid ON entry(refid)')
    conn.execute('CREATE INDEX ix_hash ON entry(hash)')
    conn.execute('CREATE INDEX ix_id ON entry(id)')
    conn.execute('CREATE TABLE value ('
        'filename TEXT NOT NULL, '
        'bibkey TEXT NOT NULL, '
        'field TEXT NOT NULL, '
        'value TEXT NOT NULL, '
        'PRIMARY KEY (filename, bibkey, field), '
        'FOREIGN KEY (filename, bibkey) REFERENCES entry(filename, bibkey))')
    # bibkey -> hash(bibkey) (py2 dict order)
    conn.execute('CREATE TABLE legacypriority ('
        'bibkey TEXT NOT NULL, '
        'priority INTEFGER NOT NULL, '
        'PRIMARY KEY (bibkey))')
 

def import_bibfiles(conn, bibfiles):
    for b in bibfiles:
        print(b.filepath)
        conn.execute('INSERT INTO file (name, size, mtime, priority)'
            'VALUES (?, ?, ?, ?)', (b.filename, b.size, b.mtime, b.priority))
        for bibkey, (entrytype, fields) in b.iterentries():
            conn.execute('INSERT INTO entry (filename, bibkey, refid) VALUES (?, ?, ?)',
                (b.filename, bibkey, fields.get('glottolog_ref_id')))
            fields = itertools.chain([('ENTRYTYPE', entrytype)], fields.iteritems())
            conn.executemany('INSERT INTO value '
                '(filename, bibkey, field, value) VALUES (?, ?, ?, ?)',
                ((b.filename, bibkey, field, value) for field, value in fields))
            conn.execute('INSERT INTO legacypriority (bibkey, priority) '
                'SELECT :bk, :pr WHERE NOT EXISTS '
                '(SELECT 1 FROM legacypriority WHERE bibkey = :bk)',
                {'bk': bibkey, 'pr': hash(bibkey)})


def entrystats(conn):
    print('\n'.join('%s %d' % (f, n) for f, n in conn.execute(
        'SELECT filename, count(*) FROM entry GROUP BY filename')))
    print('%d entries total' % conn.execute('SELECT count(*) FROM entry').fetchone())


def fieldstats(conn, with_files=False):
    if with_files:
        print('\n'.join('%d\t%s\t%s' % (n, f, b) for f, n, b in conn.execute(
            'SELECT field, count(*) AS n, replace(group_concat(DISTINCT filename), ",", ", ") '
            'FROM value GROUP BY field ORDER BY n DESC, field')))
    else:
        print('\n'.join('%d\t%s' % (n, f) for f, n in conn.execute(
            'SELECT field, count(*) AS n '
            'FROM value GROUP BY field ORDER BY n DESC, field')))


def windowed_entries(conn, chunksize):
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


def hashfields(conn, filename, bibkey):
    # also: extra_hash, volume (if not journal, booktitle, or series)
    cursor = conn.execute('SELECT field, value FROM value '
        "WHERE field IN ('author', 'editor', 'year', 'title') "
        'AND filename = ? AND bibkey = ? ', (filename, bibkey))
    fields = dict(cursor)
    return tuple(fields.get(f) for f in ('author', 'editor', 'year', 'title'))


def generate_hashes(conn):
    from bib import wrds, keyid
    words = collections.Counter()
    # TODO: consider distinct titles
    cursor = conn.execute('SELECT value FROM value WHERE field = ?', ('title',))
    while True:
        rows = cursor.fetchmany(10000)
        if not rows:
            break
        for title, in rows:
            words.update(wrds(title))
    print('%d title words (from %d tokens)' % (len(words), sum(words.itervalues())))

    get_bibkey = operator.itemgetter(0)
    for filename, first, last in windowed_entries(conn, 500):
        rows = conn.execute('SELECT bibkey, field, value FROM value '
            'WHERE filename = ? AND bibkey BETWEEN ? AND ? '
            'ORDER BY bibkey', (filename, first, last))
        conn.executemany('UPDATE entry SET hash = ? WHERE filename = ? AND bibkey = ?',
            ((keyid({k: v for b, k, v in grp}, words), filename, bibkey)
            for bibkey, grp in itertools.groupby(rows, get_bibkey)))


def hashstats(conn):
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


def hashidstats(conn):
    print('\n'.join('1 keyid %d glottolog_ref_ids: %d' % (hash_nid, n)
        for (hash_nid, n) in conn.execute(
        'SELECT hash_nid, count(*) AS n FROM '
        '(SELECT count(DISTINCT refid) AS hash_nid FROM entry WHERE hash IS NOT NULL '
        'GROUP BY hash HAVING count(DISTINCT refid) > 1) '
        'GROUP BY hash_nid ORDER BY n desc')))
    print('\n'.join('1 glottolog_ref_id %d keyids: %d' % (id_nhash, n)
        for (id_nhash, n) in conn.execute(
        'SELECT id_nhash, count(*) AS n FROM '
        '(SELECT count(DISTINCT hash) AS id_nhash FROM entry WHERE refid IS NOT NULL '
        'GROUP BY refid HAVING count(DISTINCT hash) > 1) '
        'GROUP BY id_nhash ORDER BY n desc')))


def windowed(conn, col, chunksize):
    query = 'SELECT DISTINCT %(col)s FROM entry ORDER BY %(col)s' % {'col': col}
    cursor = conn.execute(query)
    while True:
        rows = cursor.fetchmany(chunksize)
        if not rows:
            cursor.close()
            break
        (first,), (last,) = rows[0], rows[-1]
        yield first, last


def assign_ids(conn):
    allhash, = conn.execute('SELECT NOT EXISTS (SELECT 1 FROM entry '
        'WHERE hash IS NULL)').fetchone()
    assert allhash

    print('%d entries' % conn.execute('UPDATE entry SET id = NULL').rowcount)
    print('%d unchanged' % conn.execute('UPDATE entry SET id = refid WHERE refid IS NOT NULL '
        'AND NOT EXISTS (SELECT 1 FROM entry AS e '
        'WHERE e.hash = entry.hash AND e.refid != entry.refid '
        'OR e.refid = entry.refid AND e.hash != entry.hash)').rowcount)
    print('%d merged' % conn.execute('UPDATE entry '
        'SET id = (SELECT max(refid) FROM entry AS e WHERE e.hash = entry.hash) '
        'WHERE refid IS NOT NULL '
        'AND EXISTS (SELECT 1 FROM entry AS e '
        'WHERE e.hash = entry.hash AND e.refid != entry.refid) '
        'AND NOT EXISTS (SELECT 1 FROM entry AS e '
        'WHERE e.refid = entry.refid AND e.hash != entry.hash)').rowcount)
    # TODO: consider same23 merge attempt
    # TODO: let the closest match retain the id
    print('%d splitted' % conn.execute('SELECT count(*) FROM entry '
        'WHERE refid IS NOT NULL '
        'AND EXISTS (SELECT 1 FROM entry AS e '
        'WHERE e.refid = entry.refid AND e.hash != entry.hash)').fetchone())
    print('%d new' % conn.execute('SELECT count(*) FROM entry '
        'WHERE refid IS NULL ').fetchone())
    conn.execute('UPDATE entry '
            'SET id = (SELECT id FROM entry as e WHERE e.hash = entry.hash) '
            'WHERE id IS NULL')
    conn.executemany('UPDATE entry SET id = ? WHERE hash = ?',
        ((id, hash) for id, (hash,) in enumerate(
        conn.execute('SELECT hash FROM entry '
            'WHERE id IS NULL '
            'GROUP BY hash ORDER BY hash'),
        conn.execute('SELECT coalesce(max(id), 0) + 1 FROM entry').fetchone()[0])))

    allid, = conn.execute('SELECT NOT EXISTS (SELECT 1 FROM entry '
        'WHERE id IS NULL)').fetchone()
    assert allid
    onetoone, = conn.execute('SELECT NOT EXISTS '
        '(SELECT 1 FROM entry AS e WHERE EXISTS (SELECT 1 FROM entry '
        'WHERE hash = e.hash AND id != e.id '
        'OR id = e.id AND hash != e.hash))').fetchone()
    assert onetoone


def unique(iterable):
    seen = set()
    for item in iterable:
        if item not in seen:
            seen.add(item)
            yield item


def distance(left, right, weight={'author': 3, 'year': 3, 'title': 3}):
    keys = left.viewkeys() & right.viewkeys()
    if not keys:
        return 1.0
    ratios = (weight.get(k, 1) * difflib.SequenceMatcher(None, left[k], right[k]).ratio()
        for k in keys)
    weights = (weight.get(k, 1) for k in keys)
    return 1 - (sum(ratios) / sum(weights))


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

    for hash, grp in Database():
        for field, values in grp:
            if field in UNION_FIELDS:
                continue
            value1, file1, bibkey1 = values[0]
            for value2, file2, bibkey2 in values[1:]:
                if value1.lower() != value2.lower():
                    insert_ov(hash=hash, field=field, value1=value1, value2=value2,
                        file1=file1, bibkey1=bibkey1, file2=file2, bibkey2=bibkey2)


if __name__ == '__main__':
    d = Database.from_bibfiles()
    #d.to_bibfile()
    #_test_merge()
    #d = Database()
    #d.show_splits()
