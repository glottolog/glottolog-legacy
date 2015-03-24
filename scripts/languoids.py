from io import open
from collections import OrderedDict

import yaml

from clld.lib.bibtex import unescape

# https://bitbucket.org/xi/pyyaml/issue/13/loading-and-then-dumping-an-omap-is-broken


def split(s, sep=',', count=None):
    args = [sep]
    if count:
        args.append(count)
    return [ss.strip() for ss in s.split(*args)]


def convert(key, value):
    if key == 'coordinates':
        return list(eval(value))
    if key == 'population_numeric':
        return int(value)
    if key in ['alternate_names', 'classification', 'classification-hh', 'country']:
        return split(unescape(value))
    if key == 'also_spoken_in':
        return eval(value)
    return unescape(value)


def normalized_key(k):
    if k == 'Locations':
        k = 'Location'
    return k.lower().replace(' ', '_')


def to_dict(record):
    d = {} #OrderedDict()
    for k, v in record:
        k = normalized_key(k)
        d[k] = convert(k, v)
    return d


def read_hh(fname):
    """
    name: 
    ISO 639-3: hid
    Alternate Names: csv
    Classification: csv
    Classification-HH: csv
    Coordinates: lon-lat-tuple e.g. (23.06596, 67.252745), turn into list see http://geojson.org/geojson-spec.html#positions
    Coordinates Source: tex-encoded text, possibly containing refs
    Coordinates source: typo!
    Country: csv
    Also spoken in: python dict, e.g. 
        {
            u'Finland': {
                u'Status': u'4 (Educational).', 
                u'Language name': u'Finnish, Tornedalen', 
                u'Population': u'30,000 in Finland (1997 B. Winsa).'
            }
        }
    Dialects: cs tex-encoded strings
    Language Development: semi-structured text.
    Language Maps: text, e.g. "Denmark, Finland, Norway and Sweden"
    Language Status: semi-structured text, e.g. 
        "2 (Provincial). Statutory provincial language in administrative area municipalities: G\"allivare, Haparanda, Kiruna, Pajala, \"Overtone\aa{} (2009, NMNML Act No. 724, Art, 6)."
    Language Use: semi-structured text, e.g.
        "Many Saami speak as L2. Mainly older adults. Positive attitudes. Also use Swedish [swe] or Finnish [fin]."
    Location: tex-encoded text
    Locations: typo!
    Other Comments: text, including refs to other languoids as "[iso]"
    Population: text, including refs
    Population Numeric: int
    Population_Old: just one! occurrence
    Timespan: year or year-range, e.g. "1113 AD", "600-400 BC"
    Writing: dot-separated script names, e.g.:
        "Arabic script. Coptic script, Old Nubian variant. Latin script."
    Typology: semikolon-separated facts.
    code+name: 

    add:
    - glottocode
    - classification glottolog
    - countries from glottolog, list of IDs
    - macroarea
    - year of extinction?
    - med?

    """
    with open(fname, encoding='latin1') as fp:
        records = fp.read().split("\n\n\n\n")

    for record in [[split(line, sep=':', count=1) for line in e.split("\n") if line.strip()] for e in records]:
        yield to_dict(record)


if __name__ == '__main__':
    data = {r['iso_639-3']: r for r in list(read_hh('../languoids/hh17.txt'))}
    with open('../languoids/languages.yaml', 'w') as fp:
        yaml.safe_dump(data, fp, indent=4, allow_unicode=True, default_flow_style=False)

    #with open('../languoids/languages.yaml') as fp:
    #    data = yaml.load(fp)

    #with open('../languoids/languages.roundtrip.yaml', 'w') as fp:
    #    yaml.safe_dump(data, fp, indent=4, allow_unicode=True, default_flow_style=False)

