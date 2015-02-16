# undiacritic.py

import re
import unicodedata

__all__ = ['undiacritic']


def undiacritic_utf8(input_str):
    nkfd_form = unicodedata.normalize('NFKD', unicode(input_str))
    return u"".join(c for c in nkfd_form if not unicodedata.combining(c))


class Replace(object):
    """Multiple search-replace with mutually exclusive regexes."""

    _rules = [  # ordered counterbleeding
        (r'\\AA(?:\{\})?', 'A'),
        (r'\\AE(?:\{\})?', 'Ae'),
        (r'\\aa(?:\{\})?', 'a'),
        (r'\\ae(?:\{\})?', 'e'),
        (r'\\oslash(?:\{\})?', 'o'),
        (r'\\Oslash(?:\{\})?', 'O'),
        (r'\\OE(?:\{\})?', 'OE'),
        (r'\\oe(?:\{\})?', 'oe'),
        (r'\\O(?:\{\})?', 'O'),
        (r'\\o(?:\{\})?', 'o'),
        (r'\\L(?:\{\})?', 'L'),
        (r'\\l(?:\{\})?', 'l'),
        (r'\\i(?:\{\})?', 'i'),
        (r'\\j(?:\{\})?', 'j'),
        (r'\\NG(?:\{\})?', 'NG'),
        (r'\\ng(?:\{\})?', 'ng'),
        (r'\\texteng(?:\{\})?', 'ng'),
        (r'\\ss(?:\{\})?', 'ss'),
        (r'\\textbari(?:\{\})?', 'i'),
        (r'\\textbaru(?:\{\})?', 'u'),
        (r'\\textbarI(?:\{\})?', 'I'),
        (r'\\textbarU(?:\{\})?', 'U'),
        (r'\\texthtd(?:\{\})?', 'd'),
        (r'\\texthtb(?:\{\})?', 'b'),
        (r'\\textopeno(?:\{\})?', 'o'),
        (r'\\textepsilon(?:\{\})?', 'e'),
        (r'\\textschwa(?:\{\})?', 'e'),
        (r'\\textrhooktopd(?:\{\})?', 'd'),
        (r'\\textthorn(?:\{\})?', 'th'),
    ]

    def __init__(self, pairs=_rules):
        self._old, self._new = zip(*pairs)
        self._pattern = re.compile('|'.join('(%s)' % o for o in self._old))

    def __call__(self, s):
        return self._pattern.sub(self._repl, s)

    def _repl(self, match):
        group = next(i for i, m in enumerate(match.groups()) if m)
        return self._new[group]


REPLACE = Replace()
COMMAND1 = re.compile(r'\\text[a-z]+\{([^}]*)\}')
COMMAND2 = re.compile(r'\\text[a-z]+')
ACCENT = re.compile(r'''\\[`'^"H~ckl=b.druvt](\{[a-zA-Z]\}|[a-zA-Z])''')
DROP = re.compile(r'\\[^\s{}]+\{|\\.|[{}]')


def undiacritic(txt):
    txt = REPLACE(txt)
    txt = COMMAND1.sub(r'\1', txt)
    txt = COMMAND2.sub('', txt)
    txt = ACCENT.sub(r'\1', txt)
    return DROP.sub('', txt)


def _test_undiacritic(field='title'):
    import sqlalchemy as sa

    engine = sa.create_engine('postgresql://postgres@/bibfiles')
    metadata = sa.MetaData()
    undiac = sa.Table('undiacritic', metadata,
        sa.Column('value', sa.Text, primary_key=True),
        sa.Column('result1', sa.Text, nullable=False),
        sa.Column('result2', sa.Text))
    metadata.drop_all(engine)
    metadata.create_all(engine)
    insert_un = undiac.insert(bind=engine).execute

    cursor = engine.execute(sa.text(
        "SELECT fields->>'author' FROM entry WHERE fields ? 'author' UNION "
        "SELECT fields->>'editor' FROM entry WHERE fields ? 'editor' UNION "
        "SELECT fields->>'title' FROM entry WHERE fields ? 'title'"))

    while True:
        rows = cursor.fetchmany(10000)
        if not rows:
            break
        mapped = ((v, undiacritic(v)) for v, in rows)
        mapped = [{'value': v, 'result1': r1}
            for (v, r1) in mapped if v!= r1]
        if mapped:
            insert_un(mapped)


if __name__ == '__main__':
    _test_undiacritic()
