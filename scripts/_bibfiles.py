# _bibfiles.py

import os
import glob
import re
import json
import sqlite3
import collections

__all__ = ['Collection']

DIR = '../references/bibtex'
MATCH = '*.bib'
EXCLUDE = '.+old(v\d+)?\.bib$'
DBFILE = 'monster.sqlite3'


class Collection(list):

    def __init__(self, directory=DIR, match=MATCH, exclude=EXCLUDE):
        self.directory = directory
        super(Collection, self).__init__(BibFile(fp)
            for fp in glob.glob(os.path.join(directory, match))
            if not re.match(exclude, fp))
        self._map = {b.filename: b for b in self}

    def __getitem__(self, index_or_filename):
        if isinstance(index_or_filename, basestring):
            return self._map[index_or_filename]
        return super(Collection, self).__getitem__(index_or_filename)

    def to_sqlite(self, filename=DBFILE):
        import bib
        if os.path.exists(filename):
            os.remove(filename)

        db = sqlite3.connect(filename)

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
                for bibkey, (entrytype, fields) in bib.get(b.filepath).iteritems()))
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
        return filename


class BibFile(object):

    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)

    @property
    def entries(self):
        import bib
        with open(self.filepath) as fd:
            data = fd.read()
        result = self.__dict__['entries'] = bib.get2txt(data)
        return result

    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.filename)


if __name__ == '__main__':
    Collection().to_sqlite()
