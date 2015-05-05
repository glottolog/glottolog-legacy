# latexscaping.py

"""TODO: replace in source files OR add de-/encoding rule

\texthooktop{
\textpolhook{
\textbari{
\textsubbar{
\textsubdot{
\textsubwedge{
\textsubline{
\textsuperscript{ c
\textvertline
\textraiseglotstop{

\textemdash
\textendash
\textasciiacute
\textthreequarters
\texthooktopd
\textupsilon
\textglotstop
\textrevglotstop
\;
\:

---, --, ``'', {}, \textdot, \textsubdot,  \v{j} -> \v\j

see also:
  undiacritic.py rules
  http://github.com/clld/clld/blob/master/clld/lib/bibtex.py
  http://github.com/clld/clld/blob/master/clld/lib/latex.py
  http://github.com/mcmtroffaes/latexcodec/blob/develop/latexcodec/codec.py#L97

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
}

_TABLES = (latexcodec.codec._LATEX_UNICODE_TABLE,)

for unicode_text, latex_text in TABLE.iteritems():
    for table in _TABLES:
        table.register(unicode_text, latex_text)
