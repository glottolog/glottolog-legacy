# bib.py

import os
import shutil
import re
import codecs
from collections import defaultdict

from pybtex.database.input import bibtex
import latexutf8

exts = ['zip', 'pdf', 'doc', 'djvu', 'bib', 'html', 'txt']
reext = "(?:" + '|'.join(["(?:" + z + ")" for z in exts + [z.upper() for z in exts]]) + ")"
rev2 = re.compile("(v\d+)?((?:\_o)?\.%s)" % reext)


def incv(s):
    def ivh(o):
        if o.group(1):
            return "v" + str(int(o.group(1)[1:]) + 1) + o.group(2)
        else:
            return "v2" + o.group(2)
    return rev2.sub(ivh, s)


def bak(fn, ext = 'old'):
    if not os.path.exists(fn):
        print fn, "not saved in since it doesn't exist"
        return True
    thislen = os.path.getsize(fn)
    basefn = os.path.basename(fn)
    newf = os.path.join(os.path.dirname(fn), takeuntil(basefn, '.') + ext + "." + takeafter(basefn, '.'))
    while os.path.exists(newf):
        if thislen == os.path.getsize(newf):
            print newf, "not saved in since", fn, "has same size"
            return False
        newf = incv(newf)
    shutil.copyfile(fn, newf)
    print newf, "saved"
    return True


def delta(a, b, case_sensitive = False, inscost = 1, subcost = 0.5):
    if a and b:
        if not case_sensitive:
            a = a.lower()
            b = b.lower()
        if a == b:
            return 0
        else:
            return subcost
    else:
        return inscost


def align(d, x, y):
    i = len(x)
    j = len(y)
    r = {}
    k = 0
    #print d
    while (0, 0) != (i, j):
        #print i, j
        (_, t) = d[i, j]
        if t == 'S':
            r[k] = (x[i-1], y[j-1])
            i = i - 1
            j = j - 1
        elif t == 'I':
            r[k] = ("", y[j-1]) #'-'.ljust(len(y[j-1]))
            j = j - 1
        elif t == 'D':
            r[k] = (x[i-1], "") #'-'.ljust(len(x[i-1]))
            i = i - 1
        k = k + 1
    return [r[k] for k in sorted(r, reverse=True)]


def edist(x, y, delta = delta, case_sensitive = False):
    lx = len(x)
    ly = len(y)

    d = {}
    d[(0,0)] = (0, 'None')
    for i in range(lx):
        d[(i+1, 0)] = (d[(i, 0)][0] + delta(x[i], None, case_sensitive = case_sensitive), 'D')
    for j in range(ly):
        d[(0, j+1)] = (d[(0, j)][0] + delta(None, y[j], case_sensitive = case_sensitive), 'I')

    for i in range(lx):
        for j in range(ly):
            d[(i+1, j+1)] = min((d[(i, j)][0] + delta(x[i], y[j], case_sensitive = case_sensitive), 'S'),
                                (d[(i, j+1)][0] + delta(x[i], None, case_sensitive = case_sensitive), 'D'),
                                (d[(i+1, j)][0] + delta(None, y[j], case_sensitive = case_sensitive), 'I'))

    nrm = float(max(lx, ly))
    (md, _) = d[(lx, ly)]
    return (md/nrm, align(d, x, y))


def inv(d):
    r = defaultdict(set)
    for k, v in d.items():
        r[v].add(k)
    return r


def takeuntil(s, q):
    return s.split(q, 1)[0]


def takeafter(s, q):
    return s.split(q, 1)[-1]


def pairs(xs):
    # FIXME: return itertools.combinations(xs, 2)
    return [(x, y) for x in xs for y in xs if x < y]


renewline = re.compile("[\\n\\r]")

def ptab(fn, i=1, spl = "\t"):
    lines = renewline.split(load(fn))[i:]
    li = [tuple([x.strip() for x in l.split(spl)]) for l in lines if l != ""]
    return li


def ptabd(fn, spl = "\t"):
    ll = ptab(fn, i = 0)
    return dict([(l[0], dict(zip(ll[0][1:], l[1:]))) for l in ll[1:]])


def setd3(ds, k1, k2, k3, v = None):
    if ds.has_key(k1):
        if ds[k1].has_key(k2):
            ds[k1][k2][k3] = v
        else:
            ds[k1][k2] = {k3: v}
    else:
        ds[k1] = {k2: {k3: v}}
    return


def setd(ds, k1, k2, v = None):
    if ds.has_key(k1):
        ds[k1][k2] = v
    else:
        ds[k1] = {k2: v}
    return


def fd(ws):
    d = {}
    for w in ws:
        d[w] = d.get(w, 0) + 1
    return d


def fdall(chunks):
    d = {}
    for ws in chunks:
        for w in ws:
            d[w] = d.get(w, 0) + 1
    return d


def opv(d, func):
    n = {}
    for (i, v) in d.iteritems():
        n[i] = func(v)
    return n


def sumds(ds, f = sum):
    return opv(grp2l([(i, v) for d in ds for (i, v) in d.iteritems()]), f)


def grp2fd(l):
    r = {}
    for (a, b) in l:
        if r.has_key(a):
            r[a][b] = r[a].get(b, 0) + 1
        else:
            r[a] = {b: 1}
    return r


def grp2(l):
    r = {}
    for (a, b) in l:
        setd(r, a, b)
    return opv(r, lambda x: x.keys())


def grp2l(l):
    r = {}
    for (a, b) in l:
        r[a] = r.get(a, [])
        r[a].append(b)
    return r


reauthor = {}
reauthor[0] = re.compile("(?P<lastname>[^,]+),\s((?P<jr>[JS]r\.|[I]+),\s)?(?P<firstname>[^,]+)$")
reauthor[1] = re.compile("(?P<firstname>[^{][\S]+(\s[A-Z][\S]+)*)\s(?P<lastname>([a-z]+\s)*[A-Z\\\\][\S]+)(?P<jr>,\s[JS]r\.|[I]+)?$")
reauthor[2] = re.compile("(?P<firstname>\\{[\S]+\\}[\S]+(\s[A-Z][\S]+)*)\s(?P<lastname>([a-z]+\s)*[A-Z\\\\][\S]+)(?P<jr>,\s[JS]r\.|[I]+)?$")
reauthor[3] = re.compile("(?P<firstname>[\s\S]+?)\s\{(?P<lastname>[\s\S]+)\}(?P<jr>,\s[JS]r\.|[I]+)?$")
reauthor[4] = re.compile("\{(?P<firstname>[\s\S]+)\}\s(?P<lastname>[\s\S]+?)(?P<jr>,\s[JS]r\.|[I]+)?$")
reauthor[5] = re.compile("(?P<lastname>[A-Z][\S]+)$")
reauthor[6] = re.compile("\{(?P<lastname>[\s\S]+)\}$")
reauthor[7] = re.compile("(?P<lastname>[aA]nonymous)$")
reauthor[8] = re.compile("(?P<lastname>\?)$")
reauthor[9] = re.compile("(?P<lastname>[\s\S]+)$")

def psingleauthor(n, vonlastname = True):
    for i in sorted(reauthor.iterkeys()):
        o = reauthor[i].match(n)
        if o:
            if vonlastname:
                return lastvon(o.groupdict())
            return o.groupdict()
    if n:
        print "Couldn't parse name:", n
    return None


anonymous = ['Anonymous', 'No Author Stated', 'An\'onimo', 'Peace Corps'] 

def authorhash(author):
    return author['lastname'] + ", " + latexutf8.undiacritic(author.get('firstname', ''))[:1] + "."


rebrackauthor = re.compile("([\s\S]+) \{([\s\S]+)\}$")

def commaauthor(a):
    xos = [(rebrackauthor.match(x), x) for x in a.split(' and ')]
    xs = ["%s, %s" % (xo.group(2), xo.group(1)) if xo else x for (xo, x) in xos]
    return ' and '.join(xs)


def pauthor(s):
    pas = [psingleauthor(a) for a in s.split(' and ')]
    if [a for a in pas if not a]:
        if s:
            print s
    return [a for a in pas if a]


def syncauthor(pa, pb, diacritic_sensitive = False):
    pal = pa['lastname']
    pbl = pb['lastname']
    if not diacritic_sensitive:
        if latexutf8.undiacritic(pal) != latexutf8.undiacritic(pbl):
            return None
    else:
        if pal != pbl:
            return None
    
    fa = pa.get('firstname', '')
    fb = pb.get('firstname', '')
    (l, firstlonger) = max((len(fa), fa), (len(fb), fb))
    (l, lastlonger) = max((len(pal), pal), (len(pbl), pbl))

    if pa.get('jr', '') != pb.get('jr', ''):
        jr = max(pa.get('jr', ''), pb.get('jr', ''))
    else:
        jr = pa.get('jr')
    return {'lastname': lastlonger, 'firstname': firstlonger, 'jr': jr}


def syncauthors((at, af), (bt, bf)):
    paa = pauthor(af.get('author', ''))
    pab = pauthor(bf.get('author', ''))
    sa = [syncauthor(pa, pb) for (pa, pb) in zip(paa, pab)]
    if all(sa):
        return (at, putfield(('author', ' and '.join([yankauthorbib(x) for x in sa])), af))
    print "Authors don't match", sa, paa, pab
    return (at, af)


def standardize_author(s):
    return ' and '.join([yankauthorbib(x) for x in pauthor(s)])


def stdauthor(fields):
    if fields.has_key('author'):
        fields['author'] = standardize_author(fields['author'])
    if fields.has_key('editor'):
        fields['editor'] = standardize_author(fields['editor'])
    return fields


def authalpha(s):
    return ', '.join([latexutf8.undiacritic(unvonstr(x)) for x in pauthor(s)])


#"Adam, A., W.B. Wood, C.P. Symons, I.G. Ord & J. Smith"
#"Karen Adams, Linda Lauck, J. Miedema, F.I. Welling, W.A.L. Stokhof, Don A.L. Flassy, Hiroko Oguri, Kenneth Collier, Kenneth Gregerson, Thomas R. Phinnemore, David Scorza, John Davies, Bernard Comrie & Stan Abbott"

reca = re.compile("\s*[,\&]\s*")

def decommaauthor(a):
    ns = [(n, len(n.split(" "))) for n in reca.split(a)]
    #TODO what is more than the first author is lastname, firstname
    try:
        if [(n, l) for (n, l) in ns if l < 2]:
            return " and ".join(["%s, %s" % (ns[0][0], ns[1][0])] + [n for (n, l) in ns[2:]])
    except IndexError:
         print ns
         raise IndexError
    return " and ".join([n for (n, l) in ns])
       

relu = re.compile("\s+|(d\')(?=[A-Z])")
recapstart = re.compile("\[?[A-Z]")

def lowerupper(s):
    parts = [x for x in relu.split(s) if x]
    lower = []
    upper = []
    for (i, x) in enumerate(parts):
        if not recapstart.match(latexutf8.undiacritic(x)):
            lower.append(x)
        else:
            upper = parts[i:]
            break
    return (lower, upper)


def unvon(author):
    r = {}
    (lower, upper) = lowerupper(author['lastname'])
    r['lastname'] = ' '.join(upper)
    r['firstname'] = (author.get('firstname', '') + ' ' + ' '.join(lower)).strip()
    if not r['firstname']:
        r['firstname'] = None

    if author.has_key('jr') and author['jr']:
        r['jr'] = author['jr']
    
    return r


def lastvon(author):
    if not author.has_key('firstname'):
        return author
    r = {}
    (lower, upper) = lowerupper(author['firstname'])
    r['lastname'] = (' '.join(lower).strip() + ' ' + author['lastname']).strip()
    r['firstname'] = ' '.join(upper)
    if author.has_key('jr') and author['jr']:
        r['jr'] = author['jr']
    
    return r


def unvonstr(author):
    a = unvon(author)
    return ' '.join([a[k] for k in ['lastname', 'firstname', 'jr'] if a.has_key(k) and a[k]])


def lastnamekey(s):
    (_, upper) = lowerupper(s)
    if not upper:
        return ''
    return max(upper)


def yankauthorrev(author):
    author = unvon(author)
    r = author['lastname']
    if author.has_key('firstname') and author['firstname']:
        #if not renafn.search(author['firstname']):
        #    print "Warning:", author
        r += ", " + author['firstname']
    if author.has_key('jr') and author['jr']:
        r += " " + author['jr']
    return r


def yankauthorbib(author):
    r = author['lastname']
    if author.has_key('jr') and author['jr']:
        r += ", " + author['jr']
    if author.has_key('firstname') and author['firstname']:
        #if not renafn.search(author['firstname']):
        #    print "Warning:", author
        r += ", " + author['firstname']
    return r


def yankauthor(author):
    r = ""
    if author.has_key('firstname') and author['firstname']:
        #if not renafn.search(author['firstname']):
        #    print "Warning:", author
        r += author['firstname']

    r += " " + author['lastname']
    if author.has_key('jr') and author['jr']:
        r += " " + author['jr']
    return r


def yankindexauthors(authors, iseditor = False, style = "unified"):
    if authors:
        authstrings = [yankauthorrev(authors[0])] + [yankauthor(x) for x in authors[1:]]
    else:
        authstrings = ["No Author Stated"]
    r = ", ".join(authstrings[:-1])    
    if r != "":
        r += " \& " + authstrings[-1]
    else:
        r += authstrings[-1]

    if iseditor:
        if len(authors) <= 1:
            if style == 'unified':
                r += " (ed.)"
            elif style == 'diachronica':
                r += ", ed."
            else:
                print "UNKNOWN STYLE:", style
        else:
            if style == 'unified':
                r += " (eds.)"
            elif style == 'diachronica':
                r += ", eds."
            else:
                print "UNKNOWN STYLE:", style
    if r.endswith("."):
        return r
    else:
        return r + "."


def yankauthors(authors, iseditor = False, style = "unified"):
    authstrings = [yankauthor(x) for x in authors]
    r = ", ".join(authstrings[:-1])    
    if r != "":
        r += " \& " + authstrings[-1]
    else:
        r += authstrings[-1]

    if iseditor:
        if len(authors) <= 1:
            if style == 'unified':
                r += " (ed.)"
            elif style == 'diachronica':
                r += ", ed."
            else:
                print "UNKNOWN STYLE:", style
        else:
            if style == 'unified':
                r += " (eds.)"
            elif style == 'diachronica':
                r += ", eds."
            else:
                print "UNKNOWN STYLE:", style
    return r


def authoryear((typ, fields)):
    r = ""
    if fields.has_key('author'):
        authors = [x['lastname'] for x in pauthor(fields['author'])]
        r = ', '.join(authors[:-1]) + ' and ' + authors[-1]
    elif fields.has_key('editor'):
        authors = [x['lastname'] for x in pauthor(fields['editor'])]
        r = ', '.join(authors[:-1]) + ' and ' + authors[-1] + " (ed.)"
    if r.startswith(" and "):
        r = r[5:]
    return r + " " + fields.get('year', 'no date')


def rangecomplete(incomplete, complete):
    if len(complete) > len(incomplete):
        return complete[:len(complete)-len(incomplete)] + incomplete
    return incomplete


rebracketyear = re.compile("\[([\d\,\-\/]+)\]")
reyl = re.compile("[\,\-\/\s\[\]]+")

def pyear(s):
    if rebracketyear.search(s):
        s = rebracketyear.search(s).group(1)
    my = [x for x in reyl.split(s) if x.strip()]
    if len(my) == 0:
        return "[nd]"
    if len(my) != 1:
        return my[0] + "-" + rangecomplete(my[-1], my[0])
    return my[-1]


re4y = re.compile("\d\d\d\d$")

def yeartoint(s):
    a = pyear(s)[-4:]
    if re4y.match(a):
        return int(a)
    return None


def getyear((typ, fields), default = lambda x: "no date"):
    return yeartoint(fields.get("year", default((typ, fields))))


def pall(txt):
    return reitem.findall(txt)


refields = re.compile('\s*(?P<field>[a-zA-Z\_]+)\s*=\s*[{"](?P<data>.*)[}"],\n')
refieldsnum = re.compile('\s*(?P<field>[a-zA-Z\_]+)\s*=\s*(?P<data>\d+),\n')
refieldsacronym = re.compile('\s*(?P<field>[a-zA-Z\_]+)\s*=\s*(?P<data>[A-Za-z]+),\n')
#refieldslast = re.compile('\s*(?P<field>[a-zA-Z\_]+)\s*=\s*[{"]*(?P<data>.+?)[}"]*\n}')
refieldslast = re.compile('\s*(?P<field>[a-zA-Z\_]+)\s*=\s*[\{\"]?(?P<data>[^\n]+?)[\}\"]?(?<!\,)[$\n]')
retypekey = re.compile("@(?P<type>[a-zA-Z]+){(?P<key>[^,\s]*)[,\n]")
reitem = re.compile("@[a-zA-Z]+{[^@]+}")

trf = '@Book{g:Fourie:Mbalanhu,\n  author =   {David J. Fourie},\n  title =    {Mbalanhu},\n  publisher =    LINCOM,\n  series =       LWM,\n  volume =       03,\n  year = 1993\n}'

def pitem(item):
    o = retypekey.search(item)
    if not o:
        return None
    key = o.group("key")
    typ = o.group("type")
    fields = refields.findall(item) + refieldsacronym.findall(item) + refieldsnum.findall(item) + refieldslast.findall(item)
    fieldslower = map(lambda (x, y): (x.lower(), y), fields)
    return key, typ.lower(), dict(fieldslower)


def savu(txt, fn):
    with codecs.open(fn, 'w', encoding = "utf-8") as f:
        f.write(txt)


def sav(txt, fn):
    with open(fn, 'w') as f:
        f.write(txt)


def tabtxt(rows):
    return u''.join([u'\t'.join(["%s" % x for x in row]) + u'\n' for row in rows])


def load(fn):
    with open(fn, 'r') as f:
        txt = f.read()
    return txt


def get2(fn=['eva.bib']):
    return get2txt('\n'.join([load(f) for f in (fn if isinstance(fn, list) else [fn])]))


def get(fn=[]):
    return gettxt('\n'.join([load(f) for f in (fn if isinstance(fn, list) else [fn])]))


def gettxt(txt):
    pentries = [pitem(x) for x in pall(txt)]
    entries = [x for x in pentries if x]

    e = {}
    for (key, typ, fields) in entries:
        if e.has_key(key):
            print "Duplicate key: ", key
        e[key] = (typ, fields)

    return e


def get2txt(txt):
    pentries = [pitem(x) for x in pall(txt)]
    entries = [x for x in pentries if x]
    
    e = {}
    i = 0
    for (key, typ, fields) in entries:
        while e.has_key(key):
            i = i + 1
            key = str(i)
            #print "Duplicate key: ", key
        e[key] = (typ, fields)

    return e


reka = re.compile("([A-Z]+[a-z]*)|(?<![a-z])(de|van|von)")

def sepkeyauthor(k):
    return [x for x in reka.split(k) if x and x != "-"]


def sepkeyauthorform(k):
    auths = sepkeyauthor(k)
    xs = []
    c = ''
    for a in auths:
        if a.islower():
            c = c + a
        else:
            xs.append(c + a)
            c = ''
    return [a.lower() for a in xs]


def key_to_author(k):
    i = k.find(":")
    tp = k[:i]
    au = k[i+1:]
    
    i = au.find(":")
    if i == -1:
        return (au, tp)
    else:
        return (au[:i], au[i+1:] + tp)


reabbs = re.compile('@[Ss]tring\{(?P<abb>[A-Za-z]+)\s*\=\s*[\{\"](?P<full>[^\\n]+)[\}\"]\}\\n')

def getabbs(fn):
    txt = load(fn)
    return dict(reabbs.findall(txt))


reabbrep1 = re.compile("\s*\=\s*([A-Za-z]+)\,\n")
reabbrep2 = re.compile("\s*\=\s*([A-Za-z]+)\s*\#\s*\{")
reabbrep3 = re.compile("\}\s*\#\s*([A-Za-z]+)\s*\#\s*\{")
reabbrep4 = re.compile("\}\s*\#\s*([A-Za-z]+)\,\n")

def killabbs(fn, outfn = None):
    def sb(o, ins = " = {%s},\n"):
        z = o.group(1).upper()
        return ins % abbs.get(z, z)
 
    abbs = opk(getabbs(fn), lambda x: x.upper())
    if not outfn:
         outfn = takeuntil(fn, ".") + "_deabb.bib"

    txt = load(fn)
    txt = reabbrep1.sub(lambda x: sb(x, ins = " = {%s},\n"), txt)
    txt = reabbrep2.sub(lambda x: sb(x, ins = " = {%s "), txt)
    txt = reabbrep3.sub(lambda x: sb(x, ins = "%s"), txt)
    txt = reabbrep4.sub(lambda x: sb(x, ins = "%s},\n"), txt)
    return sav(txt, outfn)

#	Author = ac # { and Howard Coate},
#	Author = ad,


bibord = {}
bibord['author'] = 0
bibord['editor'] = 1
bibord['title'] = 2
bibord['booktitle'] = 3
bibord['journal'] = 5
bibord['school'] = 6
bibord['publisher'] = 7
bibord['address'] = 8
bibord['series'] = 9
bibord['volume'] = bibord['series'] + 1
bibord['number'] = bibord['volume'] + 1
bibord['pages'] = 20
bibord['year'] = 30
bibord['issn'] = 40
bibord['url'] = 50


def showbib((key, (typ, bib)), abbs={}):
    r = "@" + typ + "{" + str(key) + ",\n"
    
    order = [(bibord.get(x, 1000), x) for x in bib.keys()]
    order.sort()
    for (_, k) in order:
        v = latexutf8.utf8_to_latex(bib[k].strip()).replace("\\_", "_").replace("\\#", "#").replace("\\\\&", "\\&")
        r = r + "    " + k + " = {" + abbs.get(v, v) + "},\n"
    r = r[:-2] + "\n" + "}\n"
    #print r
    return r


def srtyear(e, descending = True):
    order = [(fields.get('year', '[n.d.]'), k) for (k, (typ, fields)) in e.iteritems()]
    return [(k, e[k]) for (sk, k) in sorted(order, reverse = descending)]


def srtauthor(e):
    order = [(authalpha(fields.get('author', fields.get('editor', '{[No author stated]}'))) + "-" + fields.get('year', '[n.d.]') + "-" + takeafter(k, ":"), k) for (k, (typ, fields)) in e.iteritems()]
    return [(k, e[k]) for (sk, k) in sorted(order)]


def put(e, abbs = {}, srtkey = "author"):
    order = [(fields.get(srtkey, '') + takeafter(k, ":"), k) for (k, (typ, fields)) in e.iteritems()]
    return ''.join([showbib((k, e[k]), abbs) for (sk, k) in sorted(order)])


resplittit = re.compile("[\(\)\[\]\:\,\.\s\-\?\!\;\/\~\=]+")
resplittittok = re.compile("([\(\)\[\]\:\,\.\s\-\?\!\;\/\~\=\'" + '\"' + "])")

def wrds(txt):
    return [x for x in resplittit.split(latexutf8.undiacritic(txt.lower()).replace("'", "").replace('"', "")) if x]


def fdt(e):
    return fdall([wrds(fields['title']) for (typ, fields) in e.itervalues() if fields.has_key('title')])


def etos(e):
    r = {}
    for (k, (typ, fields)) in e.iteritems():
        keyinf = k.split(":")
        if len(keyinf) < 2:
            print keyinf
        for w in sepkeyauthorform(keyinf[1]):
            setd3(r, 'author', w, k)
        for w in wrds(':'.join(keyinf[2:])):
            setd3(r, 'title', w, k)
        for (f, v) in fields.iteritems():
            for w in wrds(v):
                if f == 'volume':
                    w = roman(w).lower()
                setd3(r, f, w, k)
    return r


#If publisher has Place: Publisher, then don't take address
def fuse(dps, union = ['lgcode', 'fn', 'asjp_name', 'hhtype', 'isbn'], onlyifnot = {'address': 'publisher', 'lgfamily': 'lgcode', 'publisher': 'school', 'journal': 'booktitle'}):
    otyp = None
    ofields = {}
    for (typ, fields) in dps:
        if not otyp:
            otyp = typ
        for (k, v) in fields.iteritems():
            if onlyifnot.has_key(k):
                if not ofields.has_key(onlyifnot[k]):
                    ofields[k] = v
            elif not ofields.has_key(k):
                ofields[k] = v
            elif k in union:
                if ofields[k].find(v) == -1:
                    ofields[k] = ofields[k] + ", " + v
            
    return (otyp, ofields)


def add_inlg(into = 'hh.bib'):
    bak(into)
    e = get(into)
    sav(put(add_inlg_e(e), srtkey = 'macro_area'), into)


def renfn(e, ups):
    for (k, field, newvalue) in ups:
        (typ, fields) = e[k]
        #fields['mpifn'] = fields['fn']
        fields[field] = newvalue
        e[k] = (typ, fields)
    return e


def add_inlg_e(e):
    h = {}
    h['English [eng]'] = ['the', 'of', 'and', 'for', 'its', 'among', 'study', 'indians', 'sociolinguistic', 'coast', 'sketch', 'native', 'other', 'literacy', 'among', 'sociolinguistic', 'sketch', 'indians', 'native', 'coast', 'literacy', 'its', 'towards', 'eastern', 'clause', 'southeastern', 'grammar', 'linguistic', 'syntactic', 'morphology', 'spoken', 'dictionary', 'morphosyntax', 'course', 'language', 'primer', 'yourself', 'chrestomathy', 'colloquial', "sentence", "sentences", "phonetics", "phonology", "vocabulary"]
    h['French [fra]'] = ['et', 'du', 'le', 'verbe', 'grammaire', 'sociolinguistique', 'syntaxe', 'dune', 'au', 'chez', 'avec', 'langue', 'langues', 'grammaire', 'au', 'aux', 'chez', 'et', 'le', 'du', 'dune', 'verbe', 'syntaxe', 'grammaire', 'au', 'haut', 'dictionnaire', 'pratique', 'parlons', 'parlers', 'parler', 'lexique', "linguistique"]
    h['German [deu]'] = ['eine', 'das', 'reise', 'beitrag', 'unter', 'die', 'jahren', 'und', 'stellung', 'einer', 'ihrer', 'reise', 'beitrag', 'unter', 'jahren', 'die', 'stellung', 'und', 'eine', 'jahre', 'bemerkungen', 'sprache', 'sprachkontakt', 'untersuchungen', 'zu', 'zur', 'auf', 'aus']
    h['Spanish [spa]'] = ['los', 'las', 'lengua', 'lenguas', 'y', 'pueblos', 'algunos', 'educacion', 'castellano', 'poblacion', 'diccionario', "conversemos", "investigaciones", "consideraciones", "hablado", "vocabulario"]
    h['Portuguese [por]'] = ['do', 'dos', 'os', 'regiao', 'anais', 'povos', 'seus', 'mudanca', 'dicionario', 'falantes']
    h['Italian [ita]'] = ['della', 'dello', 'vocabolario', 'vocaboli', 'dizionario', 'dei', 'lessico', 'linguaggio', 'sulla', 'grammaticali', 'studi', 'degli']
    h['Russian [rus]'] = ['v', 'jazyk', 'yazyk', 'jazyka', 'yazyka', 'slov', 'iazyke', 'okolo', 'jazykach', 'jazyke', 'jazyka', 'yazyki']
    h['Dutch [nld]'] = ['van', 'het', 'kommunikasieaangeleenthede', 'deel', 'morfologie', 'onderzoek', 'gebied', 'spraakleer', 'reis', 'een', 'goede', 'taal', 'taalstudien']
    h['Mandarin Chinese [cmn]'] = ['jianzhi', 'jiu', 'jian', 'qian', 'yan', 'hui', 'wen', 'ci', 'zang', 'dian', "cidian", "zidian"]
    h['Tibetan [bod]'] = ['bod', 'kyi']
    h['Hindi [hin]'] = ['hindi', 'vyakaran']
    h['Thai [tha]'] = ['phasa', 'laksana', 'akson', 'lae', 'siang', 'khong']
    h['Vietnamese [vie]'] = ['viec', 'cach', 'trong', 'phap', 'hien', 'dung', 'nghia', 'dien', 'thong', 'ngu']
    h['Finnish [fin]'] = ['suomen', 'kielen', 'ja']
    h['Turkish [tur]'] = ['turkce', 'uzerine', 'terimleri', 'turkiye', 'hakkinda', 'halk', 'uzerinde', 'turkcede', 'tarihi', 'kilavuzu']
    
    dh = dict([(v, k) for (k, vs) in h.iteritems() for v in vs])
    ts = [(k, wrds(fields['title']) + wrds(fields.get('booktitle', ''))) for (k, (typ, fields)) in e.iteritems() if fields.has_key('title') and not fields.has_key('inlg')]
    print len(ts), "without", 'inlg'
    ann = [(k, set([dh[w] for w in tit if dh.has_key(w)])) for (k, tit) in ts]
    unique = [(k, lgs.pop()) for (k, lgs) in ann if len(lgs) == 1]
    print len(unique), "cases of unique hits"
    fnups = [(k, 'inlg', v) for (k, v) in unique]
    t2 = renfn(e, fnups)
    #print len(unique), "updates"

    newtrain = grp2fd([(lgcodestr(fields['inlg'])[0], w) for (k, (typ, fields)) in t2.iteritems() if fields.has_key('title') and fields.has_key('inlg') if len(lgcodestr(fields['inlg'])) == 1 for w in wrds(fields['title'])])
    #newtrain = grp2fd([(cname(lgc), w) for (lgcs, w) in alc if len(lgcs) == 1 for lgc in lgcs])
    for (lg, wf) in sorted(newtrain.iteritems(), key = lambda x: len(x[1])):
        cm = [(1+f, float(1-f+sum([owf.get(w, 0) for owf in newtrain.itervalues()])), w) for (w, f) in wf.iteritems() if f > 9]
        cms = [(f/fn, f, fn, w) for (f, fn, w) in cm]
        cms.sort(reverse=True)
        ##print lg, cms[:10]
        ##print ("h['%s'] = " % lg) + str([x[3] for x in cms[:10]])
    return t2


def maphhtype(fn = 'hh.bib'):
    bak(fn)
    e = get([fn])
    e2 = dict([(k, (typ, putfield(('hhtype', ';'.join([wcs[x] for x in pcat(takeuntil(k, ":"))])), fields))) for (k, (typ, fields)) in e.iteritems() if k.find(":") != -1])
    e3 = dict([(k, (typ, fields)) for (k, (typ, fields)) in e.iteritems() if k.find(":") == -1])
    if len(e3) > 0:
        print len(e3), "without colon-key-hhtype"
        print e3.keys()[:100]
    sav(put(dict(e2.items() + e3.items())), fn)


rerpgs = re.compile("([xivmcl]+)\-?([xivmcl]*)")
repgs = re.compile("([\d]+)\-?([\d]*)")

def pagecount(pgstr):
    rpgs = rerpgs.findall(pgstr)
    pgs = repgs.findall(pgstr)
    rsump = sum([romanint(b)-romanint(a)+1 for (a, b) in rpgs if b] + [romanint(a) for (a, b) in rpgs if not b])
    sump = sum([int(rangecomplete(b, a))-int(a)+1 for (a, b) in pgs if b] + [int(a) for (a, b) in pgs if not b])
    if rsump !=0 and sump != 0:
        return "%s+%s" % (rsump, sump)
    if rsump ==0 and sump == 0:
        return ''
    return str(rsump+sump)


def fullpage(pgstr):
    def fullify(o):
        (a, b) = (o.group(1), o.group(2))
        if not b:
            return a
        if int(b) < int(a) and len(b) < len(a):
            return a + "-" + a[:(len(a)-len(b))] + b
        return a + "-" + b
    return repgs.sub(fullify, pgstr) 


def putfield((k, v), d):
    r = dict([(x, y) for (x, y) in d.iteritems()])
    r[k] = v
    return r


def introman(i):
    z = {'m': 1000, 'd': 500, 'c': 100, 'l': 50, 'x': 10, 'v': 5, 'i': 1}
    iz = dict([(v, k) for (k, v) in z.iteritems()])
    x = ""
    for (v, c) in sorted(iz.items(), reverse = True):
        (q, r) = divmod(i, v)
        if q == 4 and c != 'm':
            x = x + c + iz[5*v]
        else:
            x = x + ''.join([c for i in range(q)])
        i = r
    return x


def romanint(r):
    z = {'m': 1000, 'd': 500, 'c': 100, 'l': 50, 'x': 10, 'v': 5, 'i': 1}
    i = 0
    prev = 10000
    for c in r:
        zc = z[c]
        if zc > prev:
            i = i - 2*prev + zc
        else:
            i = i + zc
        prev = zc
    return i


rerom = re.compile("(\d+)")

def roman(x):
    return rerom.sub(lambda o: introman(int(o.group(1))), x).upper()


bibe = {}
bibe['title'] = 100
bibe['year'] = 90
bibe['booktitle'] = 80
bibe['author'] = 70
bibe['editor'] = 60
bibe['journal'] = 50
bibe['school'] = 40
bibe['publisher'] = 30
bibe['howpublished'] = 30
bibe['address'] = 20
bibe['pages'] = 10
bibe['typ'] = 10
bibe['series'] = 9
bibe['volume'] = 8
bibe['number'] = 7


rewrdtok = re.compile("[a-zA-Z].+")
reokkey = re.compile("[^a-z\d\-\_\[\]]")

def keyid(fields, fd = {}, ti = 2):
    if not fields.has_key('author'):
        if not fields.has_key('editor'):
            return reokkey.sub("_", ''.join(fields.values()))
        else:
            astring = fields['editor']
    else:
        astring = fields['author']

    authors = pauthor(astring)    
    if len(authors) != len(astring.split(' and ')):
        print "Unparsed author in", authors
        print "   ", astring, astring.split(' and ')
        print fields['title']

    ak = [latexutf8.undiacritic(x) for x in sorted([lastnamekey(a['lastname']) for a in authors])]
    yk = pyear(fields.get('year', '[nd]'))[:4]
    tks = wrds(fields.get("title", "no.title")) #takeuntil :
    tkf = list(sorted([w for w in tks if rewrdtok.match(w)], key = lambda w: fd.get(w, 0), reverse = True))
    tk = tkf[-ti:]
    if fields.has_key('volume') and not fields.has_key('journal') and not fields.has_key('booktitle') and not fields.has_key('series'):
        vk = roman(fields['volume'])
    else:
        vk = ''

    if fields.has_key('extra_hash'):
        yk = yk + fields['extra_hash']

    key = '-'.join(ak) + "_" + '-'.join(tk) + vk + yk
    return reokkey.sub("", key.lower())


reisobrack = re.compile("\[([a-z][a-z][a-z]|NOCODE\_[A-Z][^\s\]]+)\]")
recomma = re.compile("[\,\/]\s?")
reiso = re.compile("[a-z][a-z][a-z]$|NOCODE\_[A-Z][^\s\]]+$")

def lgcode((typ, fields)):
    if not fields.has_key('lgcode'):
        return []
    return lgcodestr(fields['lgcode'])


def lgcodestr(lgcstr):
    lgs = reisobrack.findall(lgcstr)
    if lgs:
        return lgs
    
    parts = [p.strip() for p in recomma.split(lgcstr)]
    codes = [p for p in parts if reiso.match(p)]
    if len(codes) == len(parts):
        return codes
    return []


ret = {}
respcomma = re.compile(",\s*")
respdash = re.compile("\s*[\-]+\s*")
ret['subject_headings'] = lambda x: [tuple(respdash.split(x)) for z in respcomma.split(x)]
#subject_headings comma serated then subcats -- separated

rekillparen = re.compile(" \([^\)]*\)")

respcomsemic = re.compile("[;,]\s?")
ret['hhtype'] = lambda x: respcomsemic.split(rekillparen.sub("", x))
#wcs = {"h": 'handbook/overview', "el": 'endangered language', "w": 'wordlist', "typ": '(typological) study of a specific feature', "b": 'bibliographically oriented', "e": 'ethnographic work', "g": 'grammar', "d": 'dictionary', "s": 'grammar sketch', "v": 'comparative-historical study', "phon": 'phonology', "soc": 'sociolinguistically oriented', "ld": 'some very small amount of data/information on a language', "dial": 'dialectologically oriented', "t": 'text', "nt": 'new testament'}

reinbrack = re.compile("\[([^\]]+)]\]") 
ret['subject'] = reinbrack.findall

ret['keywords'] = lambda x: [z for z in respcomsemic.split(x) if z]
ret['lgcode'] = lgcodestr
ret['macro_area'] = lambda x: [x]


#siltype, hhtype, mahotype, evatype, macro_area
def bibtoann((typ, fields)):
    return [(k, ann) for (k, v) in ret.iteritems() if fields.has_key(k) for ann in v(fields[k])]


def hhtypestr(s):
    return ret['hhtype'](s)


def hhtype((t, f)):
    return hhtypestr(f.get("hhtype", "unknown"))


def matchtrig(ws, t):
    return all([(w in ws) == stat for (stat, w) in t])


def matchtrigsig((typ, fields), ts):
    ws = set(wrds(fields.get('title', '')))
    chks = [(t, matchtrig(ws, t)) for t in ts]
    ms = [t for (t, m) in chks if m]
    mstr = ';'.join([' and '.join([ifel(stat, '', 'not ') + w for (stat, w) in m]) for m in ms])
    return mstr


def indextrigs(ts):
    return grp2([(tuple(sorted(disj)), clslab) for (clslab, t) in ts.iteritems() for disj in t])


def sd(es):
    #most signficant piece of descriptive material
    #hhtype, pages, year
    mi = [(k, (hhtypestr(fields.get('hhtype', 'unknown')), fields.get('pages', ''), fields.get('year', ''))) for (k, (typ, fields)) in es.iteritems()]
    d = accd(mi)
    ordd = [sorted([(p, y, k, t) for (k, (p, y)) in d[t].iteritems()], reverse = True) for t in hhtyperank if d.has_key(t)]
    return ordd


def pcy(pagecountstr):
    #print pagecountstr
    if not pagecountstr:
        return 0
    return eval(pagecountstr) #int(takeafter(pagecountstr, "+"))


def getpages((typ, fields)):
    return pcy(pagecount(fields.get("pages", "")))

def accd(mi):
    r = {}
    for (k, (hhts, pgs, year)) in mi:
        #print k
        pci = pcy(pagecount(pgs))
        for t in hhts:
            setd(r, t, k, (pci/float(len(hhts)), year))
    return r


def byid(es, idf = lgcode, unsorted = False):
    def tftoids(tf):
        z = idf(tf)
        if unsorted and not z:
            return ['!Unsorted']
        return z
    return grp2([(cfn, k) for (k, tf) in es.iteritems() for cfn in tftoids(tf)])


hhtypes = {}
hhtypes['unknown'] = (1, 'unknown', 'U', 'unknown')
hhtypes['bibliographical'] = (2, 'bibliographically oriented', 'B', 'b')
hhtypes['ethnographic'] = (3, 'ethnographic work', 'E', 'e')
hhtypes['overview'] = (4, 'handbook/overview', 'O', 'h')
hhtypes['dialectology'] = (5, 'dialectologically oriented', 'X', 'dial')
hhtypes['socling'] = (6, 'sociolinguistically oriented', 'SL', 'soc')
hhtypes['minimal'] = (8, 'some very small amount of data/information on a language', 'M', 'numbers')
hhtypes['comparative'] = (9, 'comparative-historical study', 'C', 'v')
hhtypes['wordlist'] = (10, 'wordlist', 'W', 'w')
hhtypes['new_testament'] = (11, 'new testament', 'N', 'nt')
hhtypes['text'] = (12, 'text', 'T', 't')
hhtypes['phonology'] = (13, 'phonology', 'P', 'phon')
hhtypes['specific_feature'] = (14, '(typological) study of a specific feature', 'F', 'typ')
hhtypes['dictionary'] = (15, 'dictionary', 'D', 'd')
hhtypes['grammar_sketch'] = (16, 'grammar sketch', 'S', 's')
hhtypes['grammar'] = (17, 'grammar', 'G', 'g')


wcs = dict([(bibabbv, hht) for (hht, (n, expl, abbv, bibabbv)) in hhtypes.iteritems()])
hhtyperank = [hht for (n, expl, abbv, bibabbv, hht) in sorted([info + (hht,) for (hht, info) in hhtypes.iteritems()], reverse=True)]
#wcrank = [hhtypes[hht][-1] for hht in hhtyperank]
#hhcats = wcrank
#hhtype_to_n = dict([(hht, n) for (i, hht, (n, expl, abbv, bibabbv)) in hhtypes.iteritems()])
hhtype_to_n = dict([(x, len(hhtyperank)-i) for (i, x) in enumerate(hhtyperank)])
hhtype_to_expl = dict([(hht, expl) for (hht, (n, expl, abbv, bibabbv)) in hhtypes.iteritems()])
expl_to_hhtype = dict([(expl, hht) for (hht, (n, expl, abbv, bibabbv)) in hhtypes.iteritems()])
hhtype_to_abbv = dict([(hht, abbv) for (hht, (n, expl, abbv, bibabbv)) in hhtypes.iteritems()])


def sdlgs(e, unsorted = False):
    eindex = byid(e, unsorted = unsorted)
    fes = opv(eindex, lambda ks: dict([(k, e[k]) for k in ks]))
    fsd = opv(fes, sd)
    return (fsd, fes)


def pcat(ok):
    r = []
    k = ok
    while k:
        try:
            # FIXME: hhcats not defined!
            (_, m) = max([(len(x), x) for x in hhcats if k.startswith(x)])
        except ValueError:
            print ok, k
            
        r = r + [m]
        k = k[len(m):]
    return r


def lstat(e, unsorted = False):
    (lsd, lse) = sdlgs(e, unsorted = unsorted)
    return opv(lsd, lambda xs: (xs + [[[None]]])[0][0][-1])


def lstat_numeric(e, unsorted = False):
    (lsd, lse) = sdlgs(e, unsorted = unsorted)
    lsdd = opv(lsd, lambda xs: (xs + [[(0, "", "", None)]])[0][0])
    return opv(lsdd, lambda (p, y, k, t): (hhtype_to_n.get(t, 0), p, t, k))


def lstat_witness(e, unsorted = False):
    def statwit(xs):
        if len(xs) == 0:
            return (None, [])
        [(typ, ks)] = grp2([(t, k) for [p, y, k, t] in xs[0]]).items()
        return (typ, ks)
    (lsd, lse) = sdlgs(e, unsorted = unsorted)
    return opv(lsd, statwit)


def mrg(fs = []):
    if type(fs) == type([]):
        fs = dict([(f, f) for f in fs])
    e = {}
    r = {}
    for (f, fullpath) in fs.iteritems():
        e[f] = get2(fullpath)
        print f, len(e[f])
        
    ft = sumds([fdt(e[f]) for f in fs])
    
    for f in fs:
        rp = len(r)
        bk = [(keyid(fields, ft), (f, k)) for (k, (typ, fields)) in e[f].iteritems()]
        for (hk, k) in bk:
            setd(r, hk, k)
        print len(r) - rp, "new from total", len(e[f])
    return (e, r)


reyear = re.compile("\d\d\d\d")

def same23((at, af), (bt, bf)):
    alastnames = [x['lastname'] for x in pauthor(latexutf8.undiacritic(af.get("author", "")))]
    blastnames = [x['lastname'] for x in pauthor(latexutf8.undiacritic(bf.get("author", "")))]
    ay = reyear.findall(af.get('year', ""))
    by = reyear.findall(bf.get('year', ""))
    ta = latexutf8.undiacritic(takeuntil(af.get("title", ""), ":"))
    tb = latexutf8.undiacritic(takeuntil(bf.get("title", ""), ":"))
    if ta == tb and set(ay).intersection(by):
        return True
    if set(ay).intersection(by) and set(alastnames).intersection(blastnames):
        return True
    if ta == tb and set(alastnames).intersection(blastnames):
        return True
    return False

