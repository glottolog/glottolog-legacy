# undiacritic.py

# TODO: consider \textepsilon, \textschwa, \textrhooktopd, \textthorn

import re
import unicodedata

__all__ = ['undiacritic']


def undiacritic_utf8(input_str):
    nkfd_form = unicodedata.normalize('NFKD', unicode(input_str))
    return u"".join(c for c in nkfd_form if not unicodedata.combining(c))


spcud = {
    r'\AA': 'A',
    r'\AE': 'Ae',
    r'\aa': 'a',
    r'\ae': 'e',
    r'\O': 'O',
    r'\o': 'o',
    r'\oslash': 'o',
    r'\Oslash': 'O',
    r'\L': 'L',
    r'\l': 'l',
    r'\OE': 'OE',
    r'\oe': 'oe',
    r'\i': 'i',
    r'\NG': 'NG',
    r'\ng': 'ng',
    r'\texteng': 'ng',
    r'\ss': 'ss',
    r'\textbari': 'i',
    r'\textbaru': 'u',
    r'\textbarI': 'I',
    r'\textbarU': 'U',
    r'\texthtd': 'd',
    r'\texthtb': 'b',
    r'\textopeno': 'o',
}


def undiacritic(txt, resub=re.compile(r'\\[\S]+\{|\\.|\}|(?<!\S)\{')):
    for (k, v) in spcud.iteritems():
        txt = txt.replace(k + "{}", v)
    for (k, v) in spcud.iteritems():
        txt = txt.replace(k, v)
    return resub.sub("", txt)


def undiacritic2(txt, resub=re.compile(r'\\[^\s{}]+\{|\\text[a-z]+|\\.|[{}]')):
    for (k, v) in spcud.iteritems():
        txt = txt.replace(k + "{}", v)
    for (k, v) in spcud.iteritems():
        txt = txt.replace(k, v)
    return resub.sub("", txt)


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

    cursor = engine.execute(sa.text('SELECT DISTINCT fields->>:field '
        'FROM entry WHERE fields ? :field'), field=field)

    while True:
        rows = cursor.fetchmany(10000)
        if not rows:
            break
        mapped = ((v, undiacritic(v), undiacritic2(v)) for v, in rows)
        mapped = [{'value': v, 'result1': r1, 'result2': r2}
            for (v, r1, r2) in mapped if v!= r1 or r1!=r2]
        if mapped:
            insert_un(mapped)


if __name__ == '__main__':
    _test_undiacritic()
