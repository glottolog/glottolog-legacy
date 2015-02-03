# _bibtex_to_db.py - parse bibfiles into postgres 9.4 database

import os
import glob

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

import _bibtex

DB = 'postgresql://postgres@/bibfiles'
BIBS = [(f, os.path.basename(f))
    for f in glob.glob('../references/bibtex/*.bib')]


class Entry(declarative_base()):

    __tablename__ = 'entry'

    pk = sa.Column(sa.Integer, primary_key=True)
    filename = sa.Column(sa.Text, nullable=False)
    bibkey = sa.Column(sa.Text, nullable=False)
    entrytype = sa.Column(sa.Text, nullable=False)
    fields = sa.Column(JSONB, nullable=False)
    glottolog_ref_id = sa.Column(sa.Integer)
    author = sa.Column(sa.Text)
    editor = sa.Column(sa.Text)
    year = sa.Column(sa.Text)
    title = sa.Column(sa.Text)

    __table_args__ = (sa.UniqueConstraint(filename, bibkey),)


class Contributor(Entry.__base__):

    __tablename__ = 'entrycontrib'

    entry_pk = sa.Column(sa.Integer, sa.ForeignKey('entry.pk'), primary_key=True)
    role = sa.Column(sa.Text, primary_key=True)
    index = sa.Column(sa.Integer, primary_key=True)
    prelast = sa.Column(sa.Text, nullable=False)
    last = sa.Column(sa.Text, nullable=False)
    given = sa.Column(sa.Text, nullable=False)
    lineage = sa.Column(sa.Text, nullable=False)


engine = sa.create_engine(DB)
Entry.metadata.drop_all(engine)
Entry.metadata.create_all(engine)


def vacuum(engine):
    with engine.connect() as conn:
        conn = conn.execution_options(isolation_level='AUTOCOMMIT')
        conn.execute('VACUUM ANALYZE')


for filepath, filename in BIBS:
    print filepath
    with engine.begin() as conn, _bibtex.memorymapped(filepath) as m:
        insert_entry = Entry.__table__.insert(bind=conn).execute
        insert_contrib = Contributor.__table__.insert(bind=conn).execute
        for bibkey, (entrytype, fields) in _bibtex.iterentries(m):
            pk, = insert_entry(filename=filename, bibkey=bibkey,
                entrytype=entrytype, fields=fields,
                glottolog_ref_id=fields.get('glottolog_ref_id'),
                author=fields.get('author'), editor=fields.get('editor'),
                year=fields.get('year'), title=fields.get('title')
                ).inserted_primary_key
            contribs = [{'entry_pk': pk, 'role': role, 'index': i,
                'prelast': prelast, 'last': last, 'given': given,
                'lineage': lineage}
                for role in ('author', 'editor')
                for i, (prelast, last, given, lineage)
                in enumerate(_bibtex.names(fields.get(role, '')), 1)]
            if contribs:
                insert_contrib(contribs)
                    

vacuum(engine)
