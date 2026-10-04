"""Fetch public published data; never estimate missing results or bypass access controls."""
import json, re, time, urllib.request, urllib.error, urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
ZONE = 'https://riftbound.zone/en/meta-stats/'
KLX = 'https://klxcards.com'
AGENT = 'RiftboundMarketPulse/1.0 (+https://github.com/bing-bot-boop/riftbound-market-pulse)'

def now(): return datetime.now(timezone.utc).isoformat()
def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': AGENT, 'Accept': 'application/json,text/html'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode('utf-8')
def number(text):
    match = re.search(r'[\d]+(?:[.,][\d]+)?', text)
    return float(match.group().replace(',', '.')) if match else None

def read(name, default):
    try: return json.loads((DATA / name).read_text())
    except (OSError, ValueError): return default

def write(name, value):
    DATA.mkdir(exist_ok=True)
    temp = DATA / (name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')))
    temp.replace(DATA / name)

def parse_zone(html):
    s = BeautifulSoup(html, 'html.parser')
    usage = {}
    for table in s.select('.rbz-ms-table'):
        heading = table.find_previous('h2').get_text(' ', strip=True)
        zone = 'Rune' if 'runes' in heading else 'Battlefield' if 'battlefields' in heading else 'Main'
        for row in table.select('tbody tr'):
            cells = row.select('td')
            if len(cells) != 5: continue
            name = cells[1].get_text(' ', strip=True)
            link = cells[1].select_one('a[href]')
            usage[name] = {'decks': int(number(cells[2].text)), 'pct': number(cells[3].text),
                           'avg': number(cells[4].text), 'zone': zone,
                           'url': urllib.parse.urljoin(ZONE, link['href']) if link else ZONE}
    # Legends/champions use bar rows rather than a table.
    for row in s.select('.rbz-ms-lrow'):
        label = row.select_one('.rbz-ms-bar-name')
        name = ''.join(str(x) for x in label.find_all(string=True, recursive=False)).strip()
        counts = re.findall(r'\d+', row.select_one('.rbz-ms-bar-meta').text)
        link = row.select_one('.rbz-ms-det-link')
        usage[name] = {'decks': int(counts[0]), 'pct': number(row.select_one('.rbz-ms-val').text),
                       'avg': None, 'zone': 'Legend', 'url': urllib.parse.urljoin(ZONE, link['href']) if link else ZONE}
    for row in s.select('.rbz-ms-bar:not(.rbz-ms-toggle)'):
        label = row.select_one('.rbz-ms-bar-name')
        meta = row.select_one('.rbz-ms-bar-meta')
        val = row.select_one('.rbz-ms-val')
        if not label or not meta or not val: continue
        name = ''.join(str(x) for x in label.find_all(string=True, recursive=False)).strip()
        heading = row.find_previous('h2').get_text(' ', strip=True)
        if 'battlefields' not in heading and 'runes' not in heading: continue
        zone = 'Rune' if 'runes' in heading else 'Battlefield'
        counts = re.findall(r'[\d]+(?:[.,][\d]+)?', meta.text)
        usage[name] = {'decks': int(counts[0]), 'pct': number(val.text),
            'avg': float(counts[1].replace(',', '.')) if zone == 'Rune' and len(counts) > 1 else None,
            'zone': zone, 'url': urllib.parse.urljoin(ZONE, row.get('href') or '')}
    for row in s.select('.rbz-ms-cell'):
        name = row.select_one('.rbz-ms-cell-name').get_text(' ', strip=True)
        usage[name] = {'decks': int(number(row.select_one('.rbz-ms-cell-sub').text)),
            'pct': number(row.select_one('.rbz-ms-cell-pct').text), 'avg': None, 'zone': 'Champion',
            'url': urllib.parse.urljoin(ZONE, row['href'])}
    archetypes = []
    for row in s.select('.rbz-ms-wrrow'):
        name_el = row.select_one('.rbz-ms-bar-name')
        meta = row.select_one('.rbz-ms-bar-meta')
        name = ''.join(str(x) for x in name_el.find_all(string=True, recursive=False)).strip()
        counts = re.findall(r'\d+', meta.get_text())
        if len(counts) >= 2:
            archetypes.append([name, number(row.select_one('.rbz-ms-val').get_text()), int(counts[0]), int(counts[1]), urllib.parse.urljoin(ZONE, row['href'])])
    winners = []
    for row in s.select('.rbz-ms-win'):
        event = row.select_one('.rbz-ms-win-ev').get_text(' ', strip=True).replace('🏆', '').strip()
        location, date = event.split(' · ', 1)
        winners.append([location, date, row.select_one('.rbz-ms-win-player').get_text(' ', strip=True),
                        row.select_one('.rbz-ms-win-legend').get_text(' ', strip=True),
                        row.select_one('.rbz-ms-win-champ').get_text(' ', strip=True).removeprefix('with '), ZONE])
    if len(usage) < 20 or not archetypes or not winners: raise ValueError('Riftbound Zone layout changed; preserving last successful data')
    counts = re.findall(r'\d+', s.select_one('.rbz-ms-sub').text)
    return {'usage': usage, 'archetypes': archetypes, 'winners': winners, 'officialDecks': int(counts[0]), 'officialEvents': int(counts[1])}

def parse_card(html, url):
    s = BeautifulSoup(html, 'html.parser')
    module = s.select_one('.competitive-card-module')
    if not module: raise ValueError('No published competitive history at ' + url)
    name = s.find('h1').get_text(' ', strip=True)
    metrics = {p.select_one('span').get_text(' ', strip=True): p.select_one('strong').get_text(' ', strip=True)
               for p in module.select('.competitive-card-metrics p')}
    ev = {'allDecks': int(metrics['Published decks']), 'allTournaments': int(metrics['Tournaments']),
          'best': metrics.get('Best finish'), 'first': metrics.get('First appearance'), 'latest': metrics.get('Latest appearance'),
          'typical': next((number(v) for k, v in metrics.items() if k.startswith('Typical ')), None),
          'archetypes': [], 'placements': [], 'alongside': [], 'url': url, 'checkedAt': now()}
    years = []
    for a in module.select('.competitive-history-grid a'):
        yr = a.select_one('strong').text.strip()
        counts = re.search(r'(\d+)\s+decks\s*·\s*(\d+)\s+tournaments', a.get_text(' ', strip=True))
        if counts: years.append((int(yr), int(counts[1]), int(counts[2])))
    if years:
        yr, decks, tournaments = max(years)
        ev['latestYear'] = yr
        ev['yearDecks'] = decks
        ev['yearTournaments'] = tournaments
    for section in module.select('.competitive-card-subsection'):
        title = section.find('h3').get_text(' ', strip=True)
        if 'using this card' in title or 'seen alongside' in title:
            target = 'archetypes' if 'using this card' in title else 'alongside'
            for a in section.select('.competitive-chip-links a'):
                label = ''.join(str(x) for x in a.find_all(string=True, recursive=False)).strip()
                count = number(a.select_one('span').text)
                ev[target].append([label, int(count), urllib.parse.urljoin(KLX, a['href'])])
        if 'published decks featuring' in title:
            for article in section.select('article'):
                a = article.select_one('h4 a')
                label = a.get_text(' ', strip=True).split(' · ', 1)
                event_a = article.select_one('div > p a')
                context = article.select_one('div > p').get_text(' ', strip=True).split(' · ')
                ev['placements'].append([article.select_one('.competitive-placement').text.strip(), label[0], label[-1],
                    event_a.get_text(' ', strip=True), context[1], number(context[2]),
                    urllib.parse.urljoin(KLX, a['href']), urllib.parse.urljoin(KLX, event_a['href'])])
    return name, ev

def candidates(card):
    rid = (card.get('riftbound_id') or card.get('riftboundId') or '').lower()
    set_name = card.get('set_name') or card.get('setName') or ''
    set_slug = re.sub(r'[^a-z0-9]+', '-', set_name.lower()).strip('-')
    rarity = (card.get('rarity') or '').lower()
    if not rid or not set_slug: return []
    # Candidates are only accepted after the source returns a matching card name.
    return [f'{KLX}/card-library/riftbound/{set_slug}/{rid}-{rarity}-{finish}-{rid}/' for finish in ('standard', 'foil')]

def main():
    previous = read('competitive.json', {'cards': {}, 'sources': {}})
    state = {'cards': previous.get('cards', {}), 'sources': previous.get('sources', {}), 'checkedAt': now(), 'errors': []}
    try:
        zone = parse_zone(fetch(ZONE))
        state.update(zone)
        state['sources']['zone'] = {'url': ZONE, 'checkedAt': now(), 'status': 'ok'}
    except Exception as e:
        state.update({k: previous.get(k, {} if k == 'usage' else []) for k in ('usage', 'archetypes', 'winners')})
        state['officialDecks'] = previous.get('officialDecks')
        state['officialEvents'] = previous.get('officialEvents')
        state['sources']['zone'] = {**previous.get('sources', {}).get('zone', {}), 'status': 'stale', 'error': str(e)}
        state['errors'].append(str(e))
    # Once per day, maintain a hosted backup; visitors may also request current prices directly.
    for kind in ('cards', 'prices'):
        old = read(kind + '.json', {})
        checked = old.get('_checkedAt', '')
        if checked[:10] == now()[:10]: continue
        try:
            data = json.loads(fetch(f'https://api.rifthunt.com/bulk/{kind}'))
            if not isinstance(data.get(kind), list) or not data[kind]: raise ValueError('Empty bulk export')
            data['_checkedAt'] = now()
            write(kind + '.json', data)
        except Exception as e: state['errors'].append(f'{kind}: {e}')
    cards = read('cards.json', {}).get('cards', [])
    representatives = {}
    for c in cards:
        name = c.get('oracle_name') or c.get('name')
        if c.get('alt') or c.get('sig') or c.get('over') or c.get('variant'): continue
        if name not in representatives or (c.get('set') or '').lower() in ('ogn', 'sfd', 'unl'):
            representatives[name] = c
    targets = [n for n,v in state.get('usage', {}).items() if v['zone'] == 'Main']
    targets += [name for name in previous.get('cards', {}) if name not in targets]
    discovered = {}
    success = 0
    # Track the source's published most-played cards; coverage is reported explicitly.
    for name in targets:
        c = next((c for n, c in representatives.items() if n.casefold() == name.casefold()), None)
        old = state['cards'].get(name, {})
        urls = [old['url']] if old.get('url') else [discovered[name.casefold()]] if name.casefold() in discovered else candidates(c) if c else []
        error = None
        for url in urls:
            try:
                found, entry = parse_card(fetch(url), url)
                if found.casefold() != name.casefold(): raise ValueError('Card name mismatch')
                state['cards'][name] = entry
                discovered.update({x[0].casefold(): x[2] for x in entry['alongside']})
                success += 1
                print('Checked ' + name, flush=True)
                break
            except Exception as e: error = str(e)
            finally: time.sleep(0.75)
        else:
            if old: state['cards'][name] = {**old, 'error': error or 'No source link'}
    state['sources']['klx'] = {'url': KLX + '/decks/riftbound/', 'checkedAt': now(),
        'status': 'ok' if success == len(targets) and success else 'partial' if success else 'stale', 'cardsChecked': success, 'cardsRequested': len(targets),
        'coverage': 'Published most-played cards; source shows selected best finishes and top archetypes, not every deck.'}
    try:
        s = BeautifulSoup(fetch(KLX + '/decks/riftbound/'), 'html.parser')
        description = s.select_one('meta[name=description]')
        totals = re.search(r'(\d+) published .*?decklists from (\d+) events', description.get('content', '') if description else '')
        if totals: state['archiveDecks'], state['archiveEvents'] = map(int, totals.groups())
        latest = []
        for article in s.select('.competitive-deck-card'):
            a = article.select_one('h3 a'); ctx = article.select_one('.competitive-card-context'); event_a = ctx.select_one('a')
            latest.append({'placement': article.select_one('.competitive-placement').text.strip(), 'archetype': a.text.strip(),
                'player': article.select('p')[1].text.strip(), 'event': event_a.text.strip(),
                'date': list(ctx.stripped_strings)[-1], 'url': urllib.parse.urljoin(KLX, a['href']),
                'eventUrl': urllib.parse.urljoin(KLX, event_a['href'])})
        if not latest: raise ValueError('KLX results layout changed')
        state['latestResults'] = latest
        state['sources']['results'] = {'url': KLX + '/decks/riftbound/', 'checkedAt': now(), 'status': 'ok'}
    except Exception as e:
        state['latestResults'] = previous.get('latestResults', [])
        state['sources']['results'] = {**previous.get('sources', {}).get('results', {}), 'status': 'stale', 'error': str(e)}
    state['checkedAt'] = now()
    write('competitive.json', state)
    print(json.dumps({'checkedAt': state['checkedAt'], 'trackedCards': len(state['cards']), 'sources': state['sources'], 'errors': state['errors']}))

if __name__ == '__main__': main()
