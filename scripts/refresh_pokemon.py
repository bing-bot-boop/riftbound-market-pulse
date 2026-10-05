"""Refresh public English Pokemon catalogue and curated singles. No sales ranks inferred."""
import json, urllib.request, re
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
IDS = '''swsh7-215 swsh7-218 swsh7-212 swsh7-209 swsh7-205 swsh8-269 swsh8-270 swsh11-186 swsh12-186 swsh12-193 swsh12.5gg-GG70 swsh12.5gg-GG69 swsh12.5gg-GG68 swsh12.5gg-GG67 sv03.5-199 sv03.5-198 sv03.5-200 sv03.5-202 sv04-262 sv06-214 sv06-204 sv08-238 sv08-239 sv08.5-161 sv08.5-156 sv08.5-167 sv02-269 sv01-251 base1-4'''.split()
def now(): return datetime.now(timezone.utc).isoformat()
def fetch(path):
    request = urllib.request.Request('https://api.tcgdex.net/v2/en/' + path, headers={'User-Agent':'MarketPulse/1.0','Accept':'application/json'})
    with urllib.request.urlopen(request, timeout=25) as response: return json.load(response)
def read(name, fallback):
    try: return json.loads((DATA/name).read_text())
    except (OSError, ValueError): return fallback
def write(name, value):
    DATA.mkdir(exist_ok=True)
    temp = DATA/(name+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, separators=(',',':')))
    temp.replace(DATA/name)
def refresh():
    previous = read('pokemon.json', {'cards':[]})
    old = {c['id']:c for c in previous['cards']}
    try:
        catalogue = fetch('cards')
        if not isinstance(catalogue,list) or len(catalogue)<1000: raise ValueError('Invalid catalogue')
        # Pocket printings have their own numbering and market; exclude them.
        catalogue = [c for c in catalogue if not re.match(r'^[AB]\d|^P-[AB]', c['id'])]
        write('pokemon-catalogue.json', {'checkedAt':now(),'source':'https://api.tcgdex.net/v2/en/cards','cards':catalogue})
    except Exception as error: print('Catalogue retained:',str(error))
    def get(card_id):
        try:
            card = fetch('cards/'+card_id)
            if card.get('id')!=card_id or card.get('category') not in ('Pokemon','Trainer','Energy'): raise ValueError('Invalid card')
            card['_checkedAt']=now()
            card['_status']='ok'
            return card
        except Exception as error:
            print(card_id,str(error))
            if card_id in old: return {**old[card_id], '_status':'retained'}
            return None
    with ThreadPoolExecutor(max_workers=4) as pool: cards=[c for c in pool.map(get,IDS) if c]
    if not cards: raise RuntimeError('No Pokemon cards available')
    write('pokemon.json',{'checkedAt':now(),'source':'https://tcgdex.dev/en/markets-prices','selection':'Curated featured singles; not sales-volume rankings','requested':len(IDS),'cards':cards})
    print('Saved',len(cards),'featured cards')
if __name__=='__main__': refresh()
