import latexcodec
import re


debracket = re.compile("\{(.)\}")
def latex_to_utf8(s, verbose = True):
    us = s.decode("latex")
    us = debracket.sub("\\1", us)
    if verbose:
        remaininglatex(us)
    return us

def utf8_to_latex(s, verbose = True):
    return s.encode("latex")


import unicodedata
def undiacritic_utf8(input_str):
    nkfd_form = unicodedata.normalize('NFKD', unicode(input_str))
    return u"".join([c for c in nkfd_form if not unicodedata.combining(c)])

spcud = {}
spcud["\\AA"] = "A"
spcud["\\AE"] = "Ae"
spcud["\\aa"] = "a"
spcud["\\ae"] = "e"
spcud["\\O"] = "O"
spcud["\\o"] = "o"
spcud["\\oslash"] = "o"
spcud["\\Oslash"] = "O"
spcud["\\L"] = "L"
spcud["\\l"] = "l"
spcud["\\OE"] = "OE"
spcud["\\oe"] = "oe"
spcud["\\i"] = "i"
spcud['\\NG'] = "NG"
spcud['\\ng'] = "ng"
spcud['\\texteng'] = "ng"
spcud['\\ss'] = "ss"
spcud['\\textbari'] = "i"
spcud['\\textbaru'] = "u"
spcud['\\textbarI'] = "I"
spcud['\\textbarU'] = "U"
spcud['\\texthtd'] = "d"
spcud['\\texthtb'] = "b"
spcud['\\textopeno'] = "o"
def undiacritic(txt, resub = re.compile("\\\\[\S]+\{|\\\\.|\}|(?<!\S)\{")):
    for (k, v) in spcud.iteritems():
        txt = txt.replace(k + "{}", v)
    for (k, v) in spcud.iteritems():
        txt = txt.replace(k, v)
    return resub.sub("", txt)

platexspc = {}
platexspc[0] = re.compile("\\\\(?P<typ>[^\%\'\`\^\~\=\_" + '\\"' + "\s\{]+)\{(?P<ch>[a-zA-Z]?)\}")
platexspc[1] = re.compile("\\\\(?P<typ>[\'\`\^\~\=\_" + '\\"' + "]+?)\{(?P<ch>[a-zA-Z])\}")
platexspc[2] = re.compile("\\\\(?P<typ>[^a-zA-Z\s\%\_])(?P<ch>[a-zA-Z])")
platexspc[3] = re.compile("\\\\(?P<typ>[^a-zA-Z\s\%\{\_]+)(?P<ch>[a-zA-Z])")
platexspc[4] = re.compile("\\\\(?P<typ>[^\{\%\_]+)\{(?P<ch>[^\}]+)\}")
platexspc[5] = re.compile("\\\\(?P<typ>[^\{\_\\\\\s\%]+)(?P<ch>\s)")


def remaininglatex(txt):
    for i in sorted(platexspc.iterkeys()):
        o = platexspc[i].findall(txt)
        if o:
            print o[:100] #txt[o.start()-10:o.start()+10], o.groups()
    return
