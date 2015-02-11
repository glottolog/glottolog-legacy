import re
import unicodedata

import latexcodec
assert r'\"a'.decode('latex') == u'\xe4'

__all__ = ['latex_to_utf8', 'undiacritic']


def latex_to_utf8(s, verbose=True, debracket=re.compile("\{(.)\}")):
    us = s.decode("latex")
    us = debracket.sub("\\1", us)
    if verbose:
        remaininglatex(us)
    return us


platexspc = [re.compile(pattern) for pattern in [
    "\\\\(?P<typ>[^\%\'\`\^\~\=\_" + '\\"' + "\s\{]+)\{(?P<ch>[a-zA-Z]?)\}",
    "\\\\(?P<typ>[\'\`\^\~\=\_" + '\\"' + "]+?)\{(?P<ch>[a-zA-Z])\}",
    "\\\\(?P<typ>[^a-zA-Z\s\%\_])(?P<ch>[a-zA-Z])",
    "\\\\(?P<typ>[^a-zA-Z\s\%\{\_]+)(?P<ch>[a-zA-Z])",
    "\\\\(?P<typ>[^\{\%\_]+)\{(?P<ch>[^\}]+)\}",
    "\\\\(?P<typ>[^\{\_\\\\\s\%]+)(?P<ch>\s)",
]]

def remaininglatex(txt):
    for pattern in platexspc:
        o = pattern.findall(txt)
        if o:
            print o[:100] #txt[o.start()-10:o.start()+10], o.groups()


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
def undiacritic(txt, resub=re.compile("\\\\[\S]+\{|\\\\.|\}|(?<!\S)\{")):
    for (k, v) in spcud.iteritems():
        txt = txt.replace(k + "{}", v)
    for (k, v) in spcud.iteritems():
        txt = txt.replace(k, v)
    return resub.sub("", txt)


def undiacritic_utf8(input_str):
    nkfd_form = unicodedata.normalize('NFKD', unicode(input_str))
    return u"".join(c for c in nkfd_form if not unicodedata.combining(c))
