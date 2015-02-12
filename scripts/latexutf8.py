import re

import latexcodec
assert r'\"a'.decode('latex') == u'\xe4'

__all__ = ['latex_to_utf8']


def latex_to_utf8(s, verbose=True, debracket=re.compile("\{(.)\}")):
    us = s.decode("latex")
    us = debracket.sub("\\1", us)
    if verbose:
        remaininglatex(us)
    return us


platexspc = [re.compile(pattern) for pattern in [
    r'''\\(?P<typ>[^\%'\`\^\~\=\_\"\s\{]+)\{(?P<ch>[a-zA-Z]?)\}''',
    r'''\\(?P<typ>['\`\^\~\=\_\"]+?)\{(?P<ch>[a-zA-Z])\}''',
    r'\\(?P<typ>[^a-zA-Z\s\%\_])(?P<ch>[a-zA-Z])',
    r'\\(?P<typ>[^a-zA-Z\s\%\{\_]+)(?P<ch>[a-zA-Z])',
    r'\\(?P<typ>[^\{\%\_]+)\{(?P<ch>[^\}]+)\}',
    r'\\(?P<typ>[^\{\_\\\s\%]+)(?P<ch>\s)',
]]


def remaininglatex(txt):
    for pattern in platexspc:
        o = pattern.findall(txt)
        if o:
            print o[:100] #txt[o.start()-10:o.start()+10], o.groups()
