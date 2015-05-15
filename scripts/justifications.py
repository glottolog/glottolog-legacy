# justifications.py - check justification tables, translate hh.bib bibkey -> id

import os
import re
import csv
import collections

REF = re.compile(r'\*\*([^*]+)\*\*(?::([\d\-]+))?')

TRANSLATED_SUFFIX = '-ids'


class Justifications(list):

    dialect = 'excel-tab'
    encoding = 'utf-8'

    class BaseRow(object):

        @property
        def comment_bks(self):
            result = [ma.group(1) for ma in REF.finditer(self.comment)]
            self.__dict__['comment_bks'] = result
            return result

        @property
        def refs_bks(self):
            result = [REF.match(r).group(1) for r in self.refs.split(', ')]
            self.__dict__['refs_bks'] = result
            return result

    def __init__(self, rows=None):
        if rows is None:
            rows = self.iterrows()
        super(Justifications, self).__init__(rows)

    def iterrows(self):
        make_row = self.Row._make
        with open(self.filename, 'rb') as fd:
            for row in csv.reader(fd, dialect=self.dialect):
                yield make_row([c.decode(self.encoding) for c in row])

    def translated(self, mapping, save=False, suffix=TRANSLATED_SUFFIX):
        def repl(ma):
            ref, bk = ma.group(0, 1)
            bstart, bend = ma.span(1)
            return '%s%d%s' % (ref[:bstart], mapping[bk], ref[bend:])
        make_row = self.Row._make
        inst = self.__class__(make_row(r) for r in self._translated(REF.sub, repl))
        name, ext = os.path.splitext(self.filename)
        inst.filename = '%s%s%s' % (name, suffix, ext)
        return inst

    def save(self):
        with open(self.filename, 'wb') as fd:
            writer = csv.writer(fd, dialect=self.dialect)
            for row in self:
                writer.writerow([c.encode(self.encoding) for c in row])

    def to_dataframe(self):
        from pandas import DataFrame
        return DataFrame.from_records(iter(self), columns=self.Row._fields)


class FamilyJust(Justifications):

    filename = '../languoids/forkel_family_justifications-utf8.tab'

    _columns = 'name1 name2 refs comment'

    class Row(Justifications.BaseRow, collections.namedtuple('Row', _columns)):

        def allbks(self):
            return self.refs_bks + self.comment_bks

    def _translated(self, sub, repl):
        for name1, name2, refs, comment in self:
            yield name1, name2, sub(repl, refs), sub(repl, comment)


class SubclassJust(Justifications):

    filename = '../languoids/forkel_subclassification_justifications-utf8.tab'

    _columns = 'name1 name2 comment'

    class Row(Justifications.BaseRow, collections.namedtuple('Row', _columns)):

        def allbks(self):
            return self.comment_bks

    def _translated(self, sub, repl):
        for name1, name2, comment in self:
            yield name1, name2, sub(repl, comment)


def check_refs():
    from _bibfiles import Database
    with Database().connect() as conn:
        query = 'SELECT bibkey FROM entry WHERE filename = ?'
        known = {refid for refid, in conn.execute(query, ('hh.bib',))}
    print len(known)
    for rows in (FamilyJust(), SubclassJust()):
        for r in rows:
            unknown = [b for b in r.allbks() if b not in known]
            if unknown:
                print r
                print unknown
                print


def translate_refs():
    from _bibfiles import Database
    with Database().connect() as conn:
        query = 'SELECT bibkey, id FROM entry WHERE filename = ?'
        mapping = dict(conn.execute(query, ('hh.bib',)))
    global new
    for rows in (FamilyJust(), SubclassJust()):
        rows = rows.translated(mapping)
        rows.save()


if __name__ == '__main__':
    check_refs()
    #translate_refs()
