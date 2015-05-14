# monster.py - combine, deduplicate, and annotate bibfiles

"""Compiling the monster.

This script takes all the .bib files in the references directory and puts it
together in a file called monster-utf8.bib with some deduplication and annotation in
the process

1.    The hash-id pairings of the previous monster.bib is taken from monster.csv

2.    The .bib are merged in the following manner
2.1.  A hash is computed for each bib-entry in any file
2.2.  For each hash, any bib-entries with that hash are merged
2.2.1 The merging takes place such that some fields of the merged entry are
      previliged according to priority (e.g. title, lgcode and more are taken
      from hh.bib if possible), while others (like note) are the union of all original
      fields. The merged entries link back to the original(s) in the added
      srctrickle field.

3.    Four steps of annotation are added to the merged entries, but only if
      there isn't already such annotation
3.1   macro_area is added based on the lgcode field if any. The mapping between
      lgcode:s and macro_area:s are taken from "../languoids/lginfo.csv"
3.2   hhtype is added based on a small set of trigger words that may occur in
      the titles of bibentries which are taken from 'alt4hhtype.ini'. A hhtype
      is not inferred if it would change the "descriptive status" of a language
      taken from hh.bib.
3.3   lgcode is added based on a large and dirty set of trigger words that
      may/may not occur in the titles of bibentries which are taken from
      'alt4lgcode.ini'. A lgcode is not inferred if it would change the
      "descriptive status" of a language taken from hh.bib.
3.4   inlg is added based on a small set of trigger words that may occur in the
      titles of bibentries which are specified in "../references/alt4inlg.ini".

4.    Once all merging and annotation is done, it's time for the
      glottolog_ref_id:s are dole:ed out
4.1   New glottolog_ref_id:s (from the private area above 300000) are doled out
      to bib-entries which do not have one
4.2   The assigned glottolog_ref_id are burned back into the original bib:s one
      by one (via srctrickle), so that they never change

5.    A final monster-utf8.bib is written
"""

import time

import _bibfiles
import bib

BIBFILES = _bibfiles.Collection('../references/bibtex')
PREVIOUS = '../references/monster.csv'
REPLACEMENTS = 'monster-replacements.json'
MONSTER = _bibfiles.BibFile('monster-utf8.bib', encoding='utf-8', sortkey='bibkey')

HHTYPE = '../references/alt4hhtype.ini'
LGCODE = '../references/alt4lgcode.ini'
LGINFO = '../languoids/lginfo.csv'
MARKHHTYPE = 'monstermark-hht.txt'
MARKLGCODE = 'monstermark-lgc.txt'


def intersectall(xs):
    a = set(xs[0])
    for x in xs[1:]:
        a.intersection_update(x)
    return a


def markconservative(m, trigs, ref, outfn="monstermarkrep.txt", blamefield="hhtype"):
    mafter = markall(m, trigs)
    ls = bib.lstat(ref)
    #print bib.fd(ls.values())
    lsafter = bib.lstat_witness(mafter)
    log = []
    for (lg, (stat, wits)) in lsafter.iteritems():
        if not ls.get(lg):
            print lg, "lacks status", [mafter[k][1]['srctrickle'] for k in wits]
            continue
        if bib.hhtype_to_n[stat] > bib.hhtype_to_n.get(ls[lg]):
            log = log + [(lg, [(mafter[k][1].get(blamefield, "No %s" % blamefield), k, mafter[k][1].get('title', 'no title'), mafter[k][1]['srctrickle']) for k in wits], ls[lg])]
            for k in wits:
                (t, f) = mafter[k]
                if f.has_key(blamefield):
                    del f[blamefield]
                mafter[k] = (t, f)
    bib.write_csv_rows(((lg, was) + mis for (lg, miss, was) in log for mis in miss), outfn, dialect='excel-tab')
    return mafter


def markall(e, trigs, labelab=lambda x: x):
    clss = set(cls for (cls, _) in trigs.iterkeys())
    ei = dict((k, (typ, fields)) for (k, (typ, fields)) in e.iteritems() if [c for c in clss if not fields.has_key(c)])

    wk = {}
    for (k, (typ, fields)) in ei.iteritems():
        for w in bib.wrds(fields.get('title', '')):
            bib.setd(wk, w, k)

    u = {}
    it = bib.indextrigs(trigs)
    for (dj, clslabs) in it.iteritems():
        mkst = [wk.get(w, {}).iterkeys() for (stat, w) in dj if stat]
        mksf = [set(ei.iterkeys()).difference(wk.get(w, [])) for (stat, w) in dj if not stat]
        mks = intersectall(mkst + mksf)
        for k in mks:
            for cl in clslabs:
                bib.setd3(u, k, cl, dj)

    for (k, cd) in u.iteritems():
        (t, f) = e[k]
        f2 = dict((a, b) for (a, b) in f.iteritems())
        for ((cls, lab), ms) in cd.iteritems():
            a = ';'.join(' and '.join(('' if stat else 'not ') + w for (stat, w) in m) for m in ms)
            f2[cls] = labelab(lab) + ' (computerized assignment from "' + a + '")'
            e[k] = (t, f2)
    print "trigs", len(trigs)
    print "trigger-disjuncts", len(it)
    print "label classes", len(clss)
    print "unlabeled refs", len(ei)
    print "updates", len(u)
    return e


def macro_area_from_lgcode(m, lginfo=LGINFO):
    lgd = bib.read_csv_dict(lginfo)

    def inject_macro_area((typ, fields)):
        mas = set(lgd[x].macro_area for x in bib.lgcode((typ, fields)) if x in lgd and lgd[x].macro_area)
        if mas:
            fields['macro_area'] = ', '.join(sorted(mas))
        return (typ, fields)
    
    return dict((k, inject_macro_area(tf)) for k, tf in m.iteritems())


def main(bibfiles=BIBFILES, previous=PREVIOUS, replacements=REPLACEMENTS, monster=MONSTER):
    print '%s open/rebuild bibfiles db' % time.ctime()
    db = bibfiles.to_sqlite()

    print '%s compile_monster' % time.ctime()
    m = dict(db.merged())

    print '%s load hh.bib' % time.ctime()
    hhbib = bibfiles['hh.bib'].load()

    # Annotate with macro_area from lgcode when lgcode is assigned manually
    print '%s macro_area_from_lgcode' % time.ctime()
    m = macro_area_from_lgcode(m)

    # Annotate with hhtype
    print '%s annotate hhtype' % time.ctime()
    hht = dict(((cls, bib.expl_to_hhtype[lab]), v) for ((cls, lab), v) in bib.load_triggers(HHTYPE).iteritems())
    m = markconservative(m, hht, hhbib, outfn=MARKHHTYPE, blamefield="hhtype")

    # Annotate with lgcode
    print '%s annotate lgcode' % time.ctime()
    lgc = bib.load_triggers(LGCODE, sec_curly_to_square=True)
    m = markconservative(m, lgc, hhbib, outfn=MARKLGCODE, blamefield="hhtype")

    # Annotate with inlg
    print '%s add_inlg_e' % time.ctime()
    m = bib.add_inlg_e(m)

    # Print some statistics
    print time.ctime()
    print "# entries", len(m)
    print "with lgcode", sum(1 for t, f in m.itervalues() if 'lgcode' in f)
    print "with hhtype", sum(1 for t, f in m.itervalues() if 'hhtype' in f)
    print "with macro_area", sum(1 for t, f in m.itervalues() if 'macro_area' in f)

    # Update the CSV with the previous mappings for later reference
    print '%s update_previous' % time.ctime()
    db.to_csvfile(previous)

    print '%s save_replacements' % time.ctime()
    db.to_replacements(replacements)

    # Trickling back
    print '%s trickle' % time.ctime()
    db.trickle()

    # Save
    print '%s save as utf8' % time.ctime()
    monster.save(m, verbose=False)

    print '%s done.' % time.ctime()


if __name__ == '__main__':
    main()
