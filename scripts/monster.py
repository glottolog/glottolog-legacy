# monster.py - combine, deduplicate, and annotate bibfiles

"""Compiling the monster.

This script takes all the .bib files in the references directory and puts it
together in a file called monster.bib with some deduplication and annotation in
the process

1.    First any existing monster.bib is backed up

2.    The .bib are merged in the following manner
2.1.  A hash is computed for each bib-entry in any file
2.2.  For each hash, any bib-entries with that hash are merged
2.2.1 The merging takes place such that some fields of the merged entry are
      previliged according to provenance (e.g. title, lgcode and more are taken
      from hh.bib if possible), while other fields are taken from a random
      provenance, and yet others (like note) are the union of all original
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
4.1   The resulting merged bib may contain different entries which nevertheless
      have the same glottolog_ref_id-field. This is handled as follows:
4.1.1 If there are different bib-entries with the same glottolog_ref_id which
      are "the same" (diacritics, first names etc ignored) in two of the three
      fields author/title/year, they are considered the same entry and are
      merged
4.1.2 If there are still different bib-entries with the same glottolog_ref_id,
      any earlier version is monster.bib (in the same dir) is checked, and if
      one entry had the ref_id in an earlier version, this is retained. (This is
      because often new entries are typed up manually by copying an earlier
      entry and changing the fields which the by accident -- it should be
      removed -- is kept.)
4.2   New glottolog_ref_id:s (from the private area above 300000) are doled out
      to bib-entries which do not have one
4.3   The assigned glottolog_ref_id are burned back into the original bib:s one
      by one (via srctrickle), so that they never change

5.    A final monster.bib/monsterutf8.bib is written
"""

import os
import glob
import zipfile
import time

from latexutf8 import latex_to_utf8

import bib

import _bibfiles
import _bibtex

BIBFILES = _bibfiles.Collection('../references/bibtex')
HHTYPE = '../references/alt4hhtype.ini'
LGCODE = '../references/alt4lgcode.ini'
LGINFO = '../languoids/lginfo.csv'
MONSTER_ZIP = '../references/monster.zip'
MONSTER_UNZIP = 'monster_zip.bib'
MONSTER = _bibfiles.BibFile('monster.bib', encoding='ascii', sortkey='bibkey')
UMONSTER = _bibfiles.BibFile('monsterutf8.bib', encoding='utf-8', sortkey='bibkey')

PRIOS = {
    'typ': 'hh.bib', 'lgcode': 'hh.bib', 'hhtype': 'hh.bib', 'macro_area': 'hh.bib',
    'volume': 'hh.bib', 'series': 'hh.bib', 'publisher': 'hh.bib', 'pages': 'hh.bib',
    'title': 'hh.bib', 'author': 'hh.bib', 'booktitle': 'hh.bib', 'note': 'hh.bib',
}


def zip_extract(zip_archive, filename, target_name=None):
    with zipfile.ZipFile(zip_archive) as z:
        zi = next(zi for zi in z.filelist if zi.filename == filename)
        if target_name:
            zi.filename = target_name
        z.extract(zi)


def intersectall(xs):
    a = set(xs[0])
    for x in xs[1:]:
        a.intersection_update(x)
    return a


def groupsame(ks, e):
    ksame = [((k1, k2), bib.same23(e[k1], e[k2])) for (k1, k2) in bib.pairs(ks)]
    r = dict((k, i) for (i, k) in enumerate(ks))
    for ((k1, k2), s23) in ksame:
        if s23:
            r[k2] = r[k1]
    return bib.inv(r).values()


def unduplicate_ids_smart(e, previous, idfield="glottolog_ref_id"):
    # check for duplicates
    q = bib.grp2((fields[idfield], k) for (k, (typ, fields)) in e.iteritems() if fields.has_key(idfield))
    dups = [(idn, ks) for (idn, ks) in q.iteritems() if len(ks) != 1]

    # if are same? then merge
    # if one same as prev keep that
    # otherwise keep first
    for (idn, ks) in dups:
        for g in groupsame(ks, e):
            gsort = list(sorted(g, key=lambda x: (e[x][1].get("src", "").find("hh") == -1, x)))
            e[gsort[0]] = bib.fuse([e[k] for k in gsort])
            for k in gsort[1:]:
                print "FUSED", k, "WITH", gsort[0], "BECAUSE SAME", idfield, idn
                del e[k]

    dups = [(idn, [k for k in ks if e.has_key(k)]) for (idn, ks) in dups]
    print "Using previous version %s" % previous.filename
    qp = bib.grp2((fields[idfield], k) for (k, (typ, fields)) in previous.iterentries() if fields.has_key(idfield))
    for (idn, ks) in dups:
        (_, remaink) = min([(min([bib.edist(k, kold) for kold in qp.get(idn, [])] + [len(k)]), k) for k in ks])
        print remaink, "RETAINS", idn, "BECAUSE IN OLD VER"
        for k in ks:
            if k != remaink:
                del e[k][1][idfield]
                print "DELETED", idn, "FOR", k


def handout_ids(e, idfield="glottolog_ref_id"):
    q = bib.grp2((fields[idfield], k) for (k, (typ, fields)) in e.iteritems() if fields.has_key(idfield))

    tid = max([int(x) for x in q.iterkeys()] + [300000]) + 1
    print "NEW UNIQUE ID", tid
    for (k, (t, f)) in e.iteritems():
        if not f.has_key(idfield):
            f[idfield] = str(tid)
            tid = tid + 1
    print "ADDED IDS", tid - max(int(x) for x in q.iterkeys()) - 1


def findidks(e, mks):
    ft = bib.fdt(e)
    ekis = bib.grp2((bib.keyid(fields, ft), ek) for (ek, (typ, fields)) in e.iteritems())
    mkis = [(mk, bib.keyid(fields, ft)) for (mk, (typ, fields)) in mks.iteritems()]
    return dict((mk, ekis.get(kid, [])) for (mk, kid) in mkis)


def trickle(m, bibfiles, tricklefields=['isbn']):
    for f in tricklefields:
        ups = [(src, (k, f, fields[f])) for (k, (typ, fields)) in m.iteritems() for src in fields.get('src', '').split(', ') if fields.has_key(f)]
        for (src, us) in bib.grp2(ups).iteritems():
            te = bibfiles['%s.bib' % src].load()
            mktk = findidks(te, dict((mk, m[mk]) for (mk, f, newd) in us))
            r = {}
            for (mk, f, newd) in us:
                if m[mk][1].has_key('srctrickle'):
                    tks = [st[len(src)+1:] for st in m[mk][1]['srctrickle'].split(", ") if st.startswith(src + "#")]
                else:
                    tks = mktk.get(mk, [])
                r[mk] = (tks, f, newd)


            fnups = [(tk, f, newd) for (tks, f, newd) in r.itervalues() for tk in tks if te.has_key(tk) and te[tk][1].get(f, '') != newd]
            print len(fnups), "changes to", src
            warnings = [tk for (tks, f, newd) in r.itervalues() for tk in tks if not te.has_key(tk)]
            if warnings:
                print src, "Warning, the following keys do not exist anymore:", warnings
            #trace = [(mk, tk, f, newd) for (mk, (tks, f, newd)) in r.iteritems() for tk in tks if te[tk][1].get(f, '') != newd]
            #for a in trace[:10]:
            #    print a
            t2 = renfn(te, fnups)
            bibfiles['%s.bib' % src].save(t2)


def argm(d, f=max):
    if len(d) == 0:
        return None
    (_, m) = f([(v, k) for (k, v) in d.iteritems()])
    return m


def compile_monster(bibs, prios=PRIOS):
    (e, r) = bib.mrg(bibs)
    o = {}
    for (hk, dps) in r.iteritems():
        src = ', '.join(sorted(set(dpf.replace(".bib", "") for (dpf, _) in dps)))
        srctrickle = ', '.join(sorted('%s#%s' % (dpf.replace(".bib", ""), dpk) for (dpf, dpk) in dps))
        (typ, fields) = bib.fuse(e[dpf][dpk] for (dpf, dpk) in dps)

        ofs = fields
        ofs.update(srctrickle=srctrickle, src=src)

        for (what, where) in prios.iteritems():
            (_, fields) = bib.fuse(e[dpf][dpk] for (dpf, dpk) in dps if dpf == where)
            if fields.has_key(what):
                ofs[what] = fields[what]
        if prios.has_key('typ'):
            priotyp = bib.fd(e[dpf][dpk][0] for (dpf, dpk) in dps if dpf == prios['typ'])
            if priotyp:
                typ = argm(priotyp)

        o[hk] = (typ, ofs)

    return o, e['hh.bib']


def renfn(e, ups):
    for (k, field, newvalue) in ups:
        (typ, fields) = e[k]
        #fields['mpifn'] = fields['fn']
        fields[field] = newvalue
        e[k] = (typ, fields)
    return e


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
    bib.sav(bib.tabtxt([(lg, was) + mis for (lg, miss, was) in log for mis in miss]), outfn)
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


def macro_area_from_lgcode(m):
    def inject_macro_area((typ, fields), lgd):
        if fields.has_key('macro_area'):
            return (typ, fields)
        mas = set(lgd[x].macro_area for x in bib.lgcode((typ, fields)) if x in lgd and lgd[x].macro_area)
        if mas:
            fields['macro_area'] = ', '.join(sorted(mas))
        return (typ, fields)
    
    lgd = bib.read_csv_dict(LGINFO)
    return dict((k, inject_macro_area(tf, lgd)) for (k, tf) in m.iteritems())


def main(bibfiles, monster, monster_prv, umonster):
    print '%s compile_monster' % time.ctime()
    m, hhe = compile_monster(bibfiles)

    # Annotate with macro_area
    print '%s macro_area_from_lgcode' % time.ctime()
    m = macro_area_from_lgcode(m)

    # Annotate with hhtype
    print '%s annotate hhtype' % time.ctime()
    hht = dict(((cls, bib.expl_to_hhtype[lab]), v) for ((cls, lab), v) in bib.load_triggers(HHTYPE).iteritems())
    m = markconservative(m, hht, hhe, outfn="monstermarkhht.txt", blamefield="hhtype")

    # Annotate with lgcode
    print '%s annotate lgcode' % time.ctime()
    lgc = bib.load_triggers(LGCODE, sec_curly_to_square=True)
    m = markconservative(m, lgc, hhe, outfn="monstermarklgc.txt", blamefield="hhtype")

    # Annotate with inlg
    print '%s add_inlg_e' % time.ctime()
    m = bib.add_inlg_e(m)

    # Standardize author list
    print '%s stdauthor' % time.ctime()
    m = dict((k, (t, bib.stdauthor(f))) for (k, (t, f)) in m.iteritems())

    # Print some statistics
    print time.ctime()
    print "# entries", len(m)
    print "with lgcode", sum(1 for t, f in m.itervalues() if 'lgcode' in f)
    print "with hhtype", sum(1 for t, f in m.itervalues() if 'hhtype' in f)
    print "with macro_area", sum(1 for t, f in m.itervalues() if 'macro_area' in f)

    # Remove old fields
    print '%s remove glotto_id/numnote' % time.ctime()
    for k, (t, f) in m.iteritems():
        for field in ('glotto_id', 'numnote'):
            if field in f:
                del f[field]

    print '%s unduplicate_ids_smart' % time.ctime()
    unduplicate_ids_smart(m, monster_prv, idfield='glottolog_ref_id')

    print '%s handout_ids' % time.ctime()
    handout_ids(m, idfield='glottolog_ref_id')

    # Save
    print '%s save' % time.ctime()
    monster.save(m)

    # Trickling back
    print '%s trickle' % time.ctime()
    trickle(m, bibfiles, tricklefields=['glottolog_ref_id'])

    print '%s save as utf8' % time.ctime()
    umonster.save(m)


if __name__ == '__main__':
    if not os.path.exists(MONSTER_UNZIP):  # extract old version for unduplicate_ids_smart
        zip_extract(MONSTER_ZIP, MONSTER.filename, MONSTER_UNZIP)

    MONSTER_PRV = _bibfiles.BibFile(max(
        (f for f in glob.glob('monster?*.bib') if not f.endswith('-prio.bib')),
        key=lambda f: os.stat(f).st_mtime),
        encoding='ascii', sortkey=None)

    main(BIBFILES, MONSTER, MONSTER_PRV, UMONSTER)
