# justifications.py - check justification tables

import io
import re
import csv
import collections

REF = re.compile(r'\*\*(\d+)\*\*(?::([\d\-]+))?')


class Justifications(list):

    dialect = 'excel-tab'
    encoding = 'utf-8'

    class BaseRow(object):

        @property
        def commentrefs(self):
            result = [int(ma.group(1)) for ma in REF.finditer(self.comment)]
            self.__dict__['commentrefs'] = result
            return result

    Row = tuple

    def __init__(self):
        super(Justifications, self).__init__(self.iterrows())

    def iterrows(self):
        make_row = self.Row.fromrow if issubclass(self.Row, self.BaseRow) else Row
        with open(self.filename, 'rb') as fd:
            for row in csv.reader(fd, dialect=self.dialect):
                yield make_row([c.decode(self.encoding) for c in row])

    def to_dataframe(self):
        from pandas import DataFrame
        records = (r + (r.commentrefs,) for r in self)
        columns = self.Row._fields + ('commentrefs',) if issubclass(self.Row, self.BaseRow) else None
        return DataFrame.from_records(records, columns=columns)


class FamilyJust(Justifications):

    filename = '../languoids/forkel_family_justifications-utf8.tab'

    class Row(Justifications.BaseRow, collections.namedtuple('Row', 'name1 name2 refs comment')):

        @classmethod
        def fromrow(cls, row):
            name1, name2, refs, comment = row
            refs = [int(REF.match(r).group(1)) for r in refs.split(', ')]
            return cls(name1, name2, refs, comment)

        def allrefs(self):
            return self.refs + self.commentrefs
    

class SubclassJust(Justifications):

    filename = '../languoids/forkel_subclassification_justifications-utf8.tab'

    class Row(Justifications.BaseRow, collections.namedtuple('Row', 'name1 name2 comment')):

        @classmethod
        def fromrow(cls, row):
            name1, name2, comment = row
            return cls(name1, name2, comment)

        def allrefs(self):
            return self.commentrefs


if __name__ == '__main__':
    from _bibfiles import Database
    with Database().connect() as conn:
        query = 'SELECT DISTINCT refid FROM entry'
        known = {refid for refid, in conn.execute(query)}
    print len(known)
    for rows in (FamilyJust(), SubclassJust()):
        for r in rows:
            unknown = [i for i in r.allrefs() if i not in known]
            if unknown:
                print r
                print unknown
                print
