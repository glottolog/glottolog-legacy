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
import zipfile
import time

import latexutf8
import bib

import _bibfiles

DATA_DIR = os.path.join(os.pardir, 'references', 'bibtex')
BIBFILES = _bibfiles.Collection(DATA_DIR)
HHBIB = BIBFILES['hh.bib'].filepath
HHTYPE = os.path.join(os.pardir, 'references', 'alt4hhtype.ini')
LGCODE = os.path.join(os.pardir, 'references', 'alt4lgcode.ini')
LGINFO = os.path.join(os.pardir, 'languoids', 'lginfo.csv')
MONSTER = 'monster.bib'
MONSTER_ZIP = os.path.join(os.pardir, 'references', 'monster.zip')

PRIOS = {
    'typ': 'hh.bib', 'lgcode': 'hh.bib', 'hhtype': 'hh.bib', 'macro_area': 'hh.bib',
    'volume': 'hh.bib', 'series': 'hh.bib', 'publisher': 'hh.bib', 'pages': 'hh.bib',
    'title': 'hh.bib', 'author': 'hh.bib', 'booktitle': 'hh.bib', 'note': 'hh.bib',
}


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


def unduplicate_ids_smart(e, fn=MONSTER, idfield="glottolog_ref_id"):
    # check for duplicates
    q = bib.grp2([(fields[idfield], k) for (k, (typ, fields)) in e.iteritems() if fields.has_key(idfield)])
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
    fnb = bib.takeuntil(fn, ".")
    print "Finding previous version for", fnb
    (ft, previous) = max((os.stat(f).st_mtime, f) for f in os.listdir(".") if f.startswith(fnb) and f.endswith('.bib') and f != fn and not f.endswith("-prio.bib"))
    qp = bib.grp2([(fields[idfield], k) for (k, (typ, fields)) in bib.get(previous).iteritems() if fields.has_key(idfield)])
    for (idn, ks) in dups:
        (_, remaink) = min([(min([bib.edist(k, kold) for kold in qp.get(idn, [])] + [len(k)]), k) for k in ks])
        print remaink, "RETAINS", idn, "BECAUSE IN OLD VER"
        for k in ks:
            if k != remaink:
                del e[k][1][idfield]
                print "DELETED", idn, "FOR", k


def handout_ids(e, idfield="glottolog_ref_id"):
    q = bib.grp2([(fields[idfield], k) for (k, (typ, fields)) in e.iteritems() if fields.has_key(idfield)])

    tid = max([int(x) for x in q.iterkeys()] + [300000]) + 1
    print "NEW UNIQUE ID", tid
    for (k, (t, f)) in e.iteritems():
        if not f.has_key(idfield):
            f[idfield] = str(tid)
            tid = tid + 1
    print "ADDED IDS", tid - max(int(x) for x in q.iterkeys()) - 1


def findidks(e, mks):
    ft = bib.fdt(e)
    ekis = bib.grp2([(bib.keyid(fields, ft), ek) for (ek, (typ, fields)) in e.iteritems()])
    mkis = [(mk, bib.keyid(fields, ft)) for (mk, (typ, fields)) in mks.iteritems()]
    return dict((mk, ekis.get(kid, [])) for (mk, kid) in mkis)


def trickle(m, tricklefields=['isbn'], datadir=""):
    for f in tricklefields:
        ups = [(src, (k, f, fields[f])) for (k, (typ, fields)) in m.iteritems() for src in fields.get('src', '').split(', ') if fields.has_key(f)]
        for (src, us) in bib.grp2(ups).iteritems():
            try:
                te = bib.get(fn=[os.path.join(datadir, '%s.bib' % src)])
            except IOError:
                print "No such file", os.path.join(datadir, '%s.bib' % src)
                continue
            mktk = findidks(te, dict((mk, m[mk]) for (mk, f, newd) in us))
            r = {}
            for (mk, f, newd) in us:
                if m[mk][1].has_key('srctrickle'):
                    tks = [st[len(src)+1:] for st in m[mk][1]['srctrickle'].split(", ") if st.startswith(src + "#")]
                else:
                    tks = mktk.get(mk, [])
                r[mk] = (tks, f, newd)


            fnups = [(tk, f, newd) for (tks, f, newd) in r.itervalues() for tk in tks if te.has_key(tk) and te[tk][1].get(f, '') != newd]
            print len(fnups), "changes to", os.path.join(datadir, src)
            warnings = [tk for (tks, f, newd) in r.itervalues() for tk in tks if not te.has_key(tk)]
            if warnings:
                print src, "Warning, the following keys do not exist anymore:", warnings
            #trace = [(mk, tk, f, newd) for (mk, (tks, f, newd)) in r.iteritems() for tk in tks if te[tk][1].get(f, '') != newd]
            #for a in trace[:10]:
            #    print a
            t2 = renfn(te, fnups)
            bib.bak(os.path.join(datadir, '%s.bib' % src))
            bib.sav(bib.put(t2), os.path.join(datadir, '%s.bib' % src))
    return


def argm(d, f=max):
    if len(d) == 0:
        return None
    (_, m) = f([(v, k) for (k, v) in d.iteritems()])
    return m


def compile_monster((e, r), prios=PRIOS):
    o = {}
    for (hk, dps) in r.iteritems():
        src = ', '.join(set(dpf.replace(".bib", "") for (dpf, _) in dps.iterkeys()))
        srctrickle = ', '.join(dpf.replace(".bib", "") + "#" + dpk for (dpf, dpk) in dps.iterkeys())
        (typ, fields) = bib.fuse([e[dpf][dpk] for (dpf, dpk) in dps.iterkeys()])

        ofs = bib.putfield(('srctrickle', srctrickle), bib.putfield(('src', src), fields))

        for (what, where) in prios.iteritems():
            (_, fields) = bib.fuse([e[dpf][dpk] for (dpf, dpk) in dps.iterkeys() if dpf == where])
            if fields.has_key(what):
                ofs[what] = fields[what]
        if prios.has_key('typ'):
            priotyp = bib.fd([e[dpf][dpk][0] for (dpf, dpk) in dps.iterkeys() if dpf == prios['typ']])
            if priotyp:
                typ = argm(priotyp)

        o[hk] = (typ, ofs)

    return o


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
        if not fields.has_key('macro_area'):
            return (typ, fields)
        mas = set(lgd[x].macro_area for x in bib.lgcode((typ, fields)) if x in lgd and lgd[x].macro_area)
        if mas:
            fields['macro_area'] = ', '.join(sorted(mas))
        return (typ, fields)
    
    lgd = bib.read_csv_dict(LGINFO)
    return dict((k, inject_macro_area(tf, lgd)) for (k, tf) in m.iteritems())


def compile_annotate_monster(bibs, monster, hhbib):
    print '%s mrg' % time.ctime()
    (e, r) = bib.mrg(bibs)

    print '%s compile_monster' % time.ctime()
    m = compile_monster((e, r))

    # Annotate with macro_area
    print '%s macro_area_from_lgcode' % time.ctime()
    m = macro_area_from_lgcode(m)

    print '%s get hhbib' % time.ctime()
    hhe = bib.get(hhbib)

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
    unduplicate_ids_smart(m, monster, idfield='glottolog_ref_id')

    print '%s handout_ids' % time.ctime()
    handout_ids(m, idfield='glottolog_ref_id')

    # Save
    print '%s sav' % time.ctime()
    bib.sav(bib.put(m), monster)


if not os.path.exists(MONSTER):
    with zipfile.ZipFile(MONSTER_ZIP) as z:
        z.extract(MONSTER)
else:
    bib.bak(MONSTER)

compile_annotate_monster(BIBFILES, MONSTER, hhbib=HHBIB)

# Trickling back
print '%s trickle' % time.ctime()
trickle(bib.get(MONSTER), tricklefields=['glottolog_ref_id'], datadir=DATA_DIR)
print '%s savu' % time.ctime()
bib.savu(latexutf8.latex_to_utf8(bib.load(MONSTER)), 'monsterutf8.bib')
