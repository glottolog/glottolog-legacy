# _previous.py - parse and explore monster_zip.bib

import os
import sqlite3
import contextlib

import _bibfiles

BIBFILE = _bibfiles.BibFile('monster_zip.bib', encoding='ascii', sortkey=None, use_pybtex=False)
DBFILE = '_previous.sqlite3'
IDFILE = '_bibfiles.sqlite3'


class Database(object):

    @classmethod
    def from_monster(cls, bibfile=BIBFILE, filename=DBFILE):
        if os.path.exists(filename):
            os.remove(filename)

        self = cls(filename)

        db = self.connect(async=True)

        db.execute('CREATE TABLE entry ('
            'hash TEXT NOT NULL PRIMARY KEY, '
            'id INTEGER NOT NULL UNIQUE)')

        db.execute('CREATE TABLE src ('
            'hash TEXT NOT NULL, '
            'filename TEXT NOT NULL, '
            'bibkey TEXT NOT NULL, '
            'refid INTEGER, '
            'PRIMARY KEY (hash, filename, bibkey), '
            'UNIQUE (filename, bibkey), '
            'FOREIGN KEY (hash) REFERENCES entry(hash))')

        for hash, (entrytype, fields) in bibfile.iterentries():
            id = fields['glottolog_ref_id']
            db.execute('INSERT INTO entry (hash, id) VALUES (?, ?)', (hash, id))
            trickle = [s.partition('#')[::2] for s in fields['srctrickle'].split(', ')]
            db.executemany('INSERT INTO src (hash, filename, bibkey) '
                'VALUES (?, ?, ?)', ((hash, '%s.bib' % fn.lower(), bk) for fn, bk in trickle))

        db.commit()
        db.close()
        return self

    def __init__(self, filename=DBFILE):
        self.filename = filename

    def connect(self, async=False):
        conn = sqlite3.connect(self.filename)
        if async:
            conn.execute('PRAGMA synchronous = OFF')
            conn.execute('PRAGMA journal_mode = MEMORY')
        return conn

    def import_refids(self, idfile=IDFILE):
        with contextlib.closing(self.connect(async=True)) as conn, contextlib.closing(sqlite3.connect(idfile)) as idconn:
            cursor = conn.execute('SELECT filename, bibkey FROM src ORDER BY filename, bibkey')
            while True:
                result = cursor.fetchone()
                if result is None:
                    break
                row = idconn.execute('SELECT refid FROM entry '
                    'WHERE filename = ? AND bibkey = ?', result).fetchone()
                if row is None:
                    print result
                    continue
                conn.execute('UPDATE src SET refid = ? WHERE filename = ? AND bibkey = ?',
                    row + result)
            conn.commit()


if __name__ == '__main__':
    Database.from_monster()
    Database().import_refids()
    #d = Database()
