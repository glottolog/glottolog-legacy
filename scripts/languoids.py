# coding=utf8
import os
from io import open
from csv import DictReader
from collections import defaultdict
from types import StringTypes

import yaml

from clld.lib.bibtex import unescape

# https://bitbucket.org/xi/pyyaml/issue/13/loading-and-then-dumping-an-omap-is-broken


def split(s, sep=',', count=None):
    args = [sep]
    if count:
        args.append(count)
    return [ss.strip() for ss in s.split(*args) if ss.strip()]


def unescape_dict(d):
    for o, n in [(r'Cura\c{c}ao', "Curaçao"), ("Saint Barth\\'elemy", "Saint-Barthélemy")]:
        if o in d:
            d[n.decode('utf8')] = d[o]
            del d[o]
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = unescape_dict(v)
        elif isinstance(v, StringTypes):
            d[k] = unescape(v).replace("Barth\\'elemy", "Barthélemy".decode('utf8'))
    return d


def convert(key, value):
    #if key == 'code+name':
    #    return value.replace('\\', "\\\\")
    if key == 'coordinates':
        lon, lat = eval(value)
        return dict(latitude=lat, longitude=lon)
    if key == 'population_numeric':
        return int(value)
    if key in [
        'alternate_names',
        'classification',
        'classification-hh',
        'country',
        'dialects',
    ]:
        return split(unescape(value))
    if key == 'typology':
        return split(unescape(value), sep=';')
    if key == 'writing':
        return split(unescape(value), sep='.')
    if key == 'also_spoken_in':
        return unescape_dict(eval(value))
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


def normalize_hh_name(n):
    if ',' in n:
        n1, n2 = split(n, count=1)
        return '%s %s' % (n2, n1)
    return n


def equal_sets(hh, gl):
    return set(hh) == set([split(s, sep='[')[0] for s in gl])


def enriched(d, glottolog):
    if 'name' in glottolog:
        #if glottolog['name'] != normalize_hh_name(d['name']):
        #    print 'different name: gl: %s, hh: %s' % (glottolog['name'], d['name'])
        if glottolog['name'] != d['name']:
            d['name-gl'] = glottolog['name']

    for attr in ['latitude', 'longitude']:
        if attr not in glottolog:
            continue
        if 'coordinates' not in d:
            d['coordinates'] = {}
        if attr not in d['coordinates']:
            d['coordinates'][attr] = glottolog[attr]
            continue
        assert abs(glottolog[attr] - d['coordinates'][attr]) <= 0.001

    if 'macroarea' in glottolog:
        d['macroarea-gl'] = glottolog['macroarea']

    if 'classification' in glottolog:
        d['classification-gl'] = glottolog['classification']

    if 'country' in glottolog:
        if 'country' in d \
                and not equal_sets(d['country'], glottolog['country']):
            d['country-gl'] = glottolog['country']
        else:
            d['country'] = glottolog['country']

    return glottolog['glottocode'], d


def _read_csv(fname):
    with open('../languoids/' + fname, 'rb') as fp:
        rows = [row for row in DictReader(fp)]
    return rows


def read_glottolog():
    d = defaultdict(dict)

    for row in _read_csv('glottocodes_and_coordinates.csv'):
        d[row['hid']]['longitude'] = float(row['longitude'])
        d[row['hid']]['latitude'] = float(row['latitude'])

    for row in _read_csv('glottocodes_and_countries.csv'):
        d[row['hid']]['country'] = split(row['string_agg'].decode('utf8'), sep=';')

    for row in _read_csv('glottocodes_and_macroareas.csv'):
        assert ',' not in row['string_agg']
        d[row['hid']]['macroarea'] = row['string_agg']

    languoids = {int(r['pk']): r for r in _read_csv('glottocodes_names_by_pk.csv')}
    for row in _read_csv('glottocodes_names_and_classification.csv'):
        d[row['hid']]['glottocode'] = row['id']
        d[row['hid']]['name'] = row['name'].decode('utf8')
        classification = eval(row['array_agg'])
        if len(classification) > 1:
            d[row['hid']]['classification'] = [
                '%s [%s]' % (languoids[pk]['name'].decode('utf8'), languoids[pk]['id'])
                for pk in classification[:0:-1]]

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
    data = []

    not_in_gl = []
    gl = read_glottolog()

    for r in read_hh('../languoids/hh17.txt'):
        hid = r['iso_639-3']
        if hid in gl:
            data.append(enriched(r, gl[hid]))
        else:
            not_in_gl.append(hid)
            r['note'] = 'NOT IN GLOTTOLOG'
            data.append((hid, r))

    print len(not_in_gl), 'languages not in glottolog'

    with open('../languoids/languages.yaml', 'w') as fp:
        yaml.safe_dump(dict(data), fp, indent=4, allow_unicode=True, default_flow_style=False)

    with open('../languoids/languages.yaml') as fp:
        data = yaml.load(fp)

    with open('../languoids/languages.roundtrip.yaml', 'w') as fp:
        yaml.safe_dump(data, fp, indent=4, allow_unicode=True, default_flow_style=False)

    os.system("diff ../languoids/languages.yaml ../languoids/languages.roundtrip.yaml")
