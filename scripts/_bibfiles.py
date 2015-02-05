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

__all__ = ['Collection', 'Database']

DIR = '../references/bibtex'
DBFILE = 'monster.sqlite3'


class Collection(list):

    _encoding = 'utf-8-sig'

    def __init__(self, directory=DIR, config='BIBFILES.ini', endwith='.bib'):
        self.directory = directory
        config = os.path.join(directory, config)
        p = ConfigParser.RawConfigParser()
        with io.open(config, encoding=self._encoding) as fp:
            p.readfp(fp)
        kwargs = [{'filepath': os.path.join(directory, s),
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

    def to_sqlite(self, filename=DBFILE):
        import bib
        if os.path.exists(filename):
            os.remove(filename)

        result = Database(filename)
        db = result.connect()

        db.execute('CREATE TABLE entry ('
            'filename TEXT NOT NULL, '
            'bibkey TEXT NOT NULL, '
            'entrytype TEXT NOT NULL, '
            'hash TEXT, '
            'fields TEXT NOT NULL, '
            'title TEXT, '
            'PRIMARY KEY (filename, bibkey))')

        db.execute('PRAGMA synchronous = OFF')
        db.execute('PRAGMA journal_mode = MEMORY')

        for b in self:
            print b.filepath
            db.executemany('INSERT INTO entry '
                '(filename, bibkey, entrytype, fields, title) VALUES (?, ?, ?, ?, ?)',
                ((b.filename, bibkey, entrytype, json.dumps(fields), fields.get('title'))
                for bibkey, (entrytype, fields) in b.iterentries()))
            db.commit()
        print '\n'.join('%d %s' % (n, f) for f, n in db.execute(
            'SELECT filename, count(*) FROM entry GROUP BY filename'))
        print '%d entries' % db.execute('SELECT count(*) FROM entry').fetchone()

        words = collections.Counter()
        for title, in db.execute('SELECT title FROM entry WHERE title IS NOT NULL'):
            words.update(bib.wrds(title))
        print '%d title words' % len(words)

        result = db.execute('SELECT filename, bibkey, fields FROM entry')
        while True:
            rows = result.fetchmany(1000)
            if not rows:
                break
            db.executemany('UPDATE entry SET hash = ? WHERE filename = ? AND bibkey = ?',
                ((bib.keyid(json.loads(fields), words), filename, bibkey)
                for filename, bibkey, fields in rows))
            db.commit()
        db.execute('CREATE INDEX IF NOT EXISTS ix_hash ON entry(hash)')
        print '%d keyids' % db.execute('SELECT count(hash) FROM entry').fetchone()
        db.close()
        return result


class BibFile(object):

    def __init__(self, filepath, priority, name, title, description, abbr):
        assert os.path.exists(filepath)
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.priority = priority
        self.name = name
        self.title = title
        self.description = description
        self.abbr = abbr

    def iterentries(self, encoding=None, use_pybtex=False):
        import _bibtex
        return _bibtex.iterentries(self.filepath, encoding, use_pybtex)

    def load(self, encoding=None, use_pybtex=False):
        import _bibtex
        return _bibtex.load(self.filepath, encoding, use_pybtex)

    def save(self, entries, srtkey, encoding=None, use_pybtex=False):
        import _bibtex
        _bibtex.save(entries, self.filepath, encoding, use_pybtex)

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.filename)


class Database(object):

    def __init__(self, filename=DBFILE):
        self.filename = filename

    def connect(self):
        return sqlite3.connect(self.filename)

    def _iter(self):
        with contextlib.closing(self.connect()) as db:
            result = db.execute('SELECT hash, filename, bibkey, entrytype, fields '
                'FROM entry ORDER BY hash, filename, bibkey')
            while True:
                rows = result.fetchmany(100)
                if not rows:
                    return
                for hs, fn, bk, et, fs in rows:
                    yield hs, fn, bk, et, json.loads(fs)

    def __iter__(self):
        for hs, group in itertools.groupby(self._iter(), operator.itemgetter(0)):
            yield hs, [(fn, bk, et, fs) for hs, fn, bk, et, fs in group]


if __name__ == '__main__':
    c = Collection()
    c.to_sqlite()
