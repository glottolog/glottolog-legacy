# paths.py - parse (path, members) files like lff.txt and lof.txt

import io
import re
import collections
import itertools


class PathsFile(object):

    RECORD = re.compile(r'^(\S.+)\n((?:^  .+$\n?)+)', re.MULTILINE)

    MEMBER = re.compile(r'([^[]+)\[([^]]+)\]')

    @classmethod
    def records(cls, data):
        pos = 0
        for match in cls.RECORD.finditer(data):
            if match.start() != pos:
                raise ValueError(data[pos:match.start()])
            path = tuple(m.strip() for m in match.group(1).split(', '))
            members = [cls.member(m) for m in match.group(2).splitlines()]
            yield path, members
            pos = match.end()
        if pos < len(data) - 1:
            raise ValueError(data[pos:])

    @classmethod
    def member(cls, line):
        match = cls.MEMBER.match(line.strip())
        if match is None:
            raise ValueError(line)
        name = match.group(1).strip()
        code = match.group(2).strip()
        return name, code
    
    def __init__(self, filename, encoding='utf-8'):
        self.filename = filename
        self.encoding = encoding

    def __iter__(self):        
        with io.open(self.filename, encoding=self.encoding) as fd:
            data = fd.read()
        return self.records(data)

    def to_dict(self, cls=collections.OrderedDict):
        result = cls()
        for key, values in self:
            result.setdefault(key, []).extend(values)
        return result


class Paths(dict):

    def walk_routes(self):
        result = {}
        for path in self:
            path = ('__root__',) + path
            for start, end in itertools.combinations(range(len(path)), 2):
                walk = path[start], path[end]
                route = path[start + 1:end]
                result.setdefault(walk, set()).add(route)
        return result
    
    def member_paths(self):
        result = {}
        for path, members in self.iteritems():
            for m in members:
                result.setdefault(m, []).append(path)
        return result
    
    def is_tree(self):
        ambig_routes = [(w, r) for w, r in self.walk_routes().iteritems() if len(r) != 1]
        ambig_paths = [(m, p) for m, p in self.member_paths().iteritems() if len(p) != 1]
        return not (ambig_routes or ambig_paths)
    
    def iterpairs(self):
        for path, members in self.iteritems():
            for m in members:
                yield path, m

    def to_dataframe(self, flatten=False):
        from pandas import DataFrame
        if flatten:
            records, columns = self.iterpairs(), ['path', 'member']
        else:
            records, columns = self.iteritems(), ['path', 'members']
        return DataFrame.from_records(records, columns=columns)


if __name__ == '__main__':
    lff = PathsFile('../languoids/lff.txt').to_dict(Paths)
    assert lff.is_tree()
    print(len(lff))
    print(next(lff.iteritems()))

    lof = PathsFile('..//languoids/lof.txt').to_dict()
    print(len(lof))
    print(next(lof.iteritems()))
