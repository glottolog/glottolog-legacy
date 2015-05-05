# latexscaping.py

"""TODO: replace in source files OR add de-/encoding rule

\textsubdot{
\textsubbar{
\textsuperscript{ c
\~e
\textsubline{
\texthtd
\textvertline
\textesh
\textbaru
\textsubring
\textgamma
\textupsilon


\texthooktop{
\textsubwedge{
\textemdash
\textendash
\textthreequarters
\texthooktopd
\textrevglotstop
\;
\:

---, --, ``'', {}, \textdot, \textsubdot,  \v{j} -> \v\j

see also:
  undiacritic.py rules
  http://github.com/clld/clld/blob/master/clld/lib/bibtex.py
  http://github.com/clld/clld/blob/master/clld/lib/latex.py
  http://github.com/mcmtroffaes/latexcodec/blob/develop/latexcodec/codec.py#L97

\textpolhook{ -> \k{}?
\&
"""

import latexcodec

assert u'\xe4'.encode('latex') == r'\"a'
assert r'\"a'.decode('latex') == u'\xe4'

TABLE = {
    u'\N{LATIN SMALL LETTER ENG}': br'\ng',
    u'\N{LATIN CAPITAL LETTER ENG}': br'\NG',
    u'\N{LATIN SMALL LETTER OPEN O}': br'\textopeno',
    u'\N{LATIN SMALL LETTER THORN}': br'\textthorn',
    u'\N{LATIN SMALL LETTER GLOTTAL STOP}': br'\textglotstop',
    u'\N{MODIFIER LETTER GLOTTAL STOP}': br'\textraiseglotstop',
    u'\N{LATIN SMALL LETTER I WITH STROKE}': br'\textbari',
}

_TABLES = (latexcodec.codec._LATEX_UNICODE_TABLE,)

for unicode_text, latex_text in TABLE.iteritems():
    for table in _TABLES:
        table.register(unicode_text, latex_text)
