"""Bulk sorting signals from published decklists and buyer-advertised category quotes."""
import json, re, html, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
BASE='https://limitlesstcg.com'
SETS={'TEF':'sv05','TWM':'sv06','SFA':'sv06.5','SCR':'sv07','SSP':'sv08','PRE':'sv08.5','JTG':'sv09','DRI':'sv10','BLK':'sv10.5b','WHT':'sv10.5w','MEG':'me01','PFL':'me02','ASC':'me02.5','POR':'me03','CHA':'me04','PBL':'me05','PAL':'sv02','SVI':'sv01','OBF':'sv03','PAR':'sv04','PAF':'sv04.5'}
BASIC={'Grass Energy','Fire Energy','Water Energy','Lightning Energy','Psychic Energy','Fighting Energy','Darkness Energy','Metal Energy','Fairy Energy'}
RARITIES={'Common','Uncommon','Rare','Holo Rare','Rare Holo'}
def now():return datetime.now(timezone.utc).isoformat()
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'MarketPulse/1.0 (+https://github.com/bing-bot-boop/riftbound-market-pulse)','Accept':'text/html,application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:return response.read().decode('utf-8')
def clean(s):return html.unescape(re.sub('<[^>]+>','',s)).strip()
def attrs(s):return dict(re.findall(r'([\w-]+)="([^"]*)"',s))
def write(value):
    temp=DATA/'pokemon-bulk.json.tmp';temp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')));temp.replace(DATA/'pokemon-bulk.json')
def events_from(s):
    out=[]
    for tag,body in re.findall(r'<tr([^>]*data-date[^>]*)>(.*?)</tr>',s,re.S):
        a=attrs(tag);link=re.search(r'href="(/tournaments/\d+)"',body)
        if a.get('data-format')!='standard' or a.get('data-country') not in {'US','CA','DE','GB','FR','AU','AT','NL','ES','IT','BR','CL','MX'} or int(a.get('data-players','0'))<500 or not link:continue
        date=datetime.fromisoformat(a['data-date']).replace(tzinfo=timezone.utc)
        if 0<=(datetime.now(timezone.utc)-date).days<=90:out.append({'name':html.unescape(a['data-name']),'date':a['data-date'],'url':BASE+link[1]+'/decklists','players':int(a['data-players'])})
    return out[:3]
def decks_from(s):
    out=[];seen=set()
    for match in re.finditer(r'<div class="decklist" data-id="([^"]+)">(.*?)(?=<div class="decklist" data-id=|\Z)',s,re.S):
        if match[1] in seen:continue
        seen.add(match[1]);b=match[2].split('data-image-decklist')[0]
        title=re.search(r'<div class="decklist-title">\s*([^<]+)',b);archetype=clean(title[1]) if title else 'Unspecified'
        entries=[]
        for m in re.finditer(r'<div class="decklist-card"([^>]*)>(.*?)</div>',b,re.S):
            a=attrs(m[1]);body=m[2];name=re.search(r'class="card-name">([^<]+)',body);count=re.search(r'class="card-count">([^<]+)',body)
            if not name or not count or not count[1].isdigit():continue
            headings=re.findall(r'class="decklist-column-heading">([^<]+)',b[:m.start()]);kind=clean(headings[-1]).split(' (')[0] if headings else 'Unknown'
            price=re.search(r'class="card-price usd"[^>]*>\$([\d.]+)',body);href=re.search(r'class="card-price usd" href="([^"]+)"',body)
            market_url=None
            if href:
                query=urllib.parse.parse_qs(urllib.parse.urlparse(html.unescape(href[1])).query)
                u=query.get('u',[''])[0]
                if u.startswith('https://www.tcgplayer.com/product/'):market_url=u
            entries.append({'name':clean(name[1]),'copies':int(count[1]),'set':a.get('data-set'),'number':a.get('data-number'),'kind':kind,'price':float(price[1]) if price else None,'marketUrl':market_url})
        # Reject partial pages rather than reporting misleading percentages.
        if sum(c['copies'] for c in entries)==60:out.append({'archetype':archetype,'cards':entries})
    return out

def refresh():
    try:previous=json.loads((DATA/'pokemon-bulk.json').read_text())
    except (OSError,ValueError):previous={}
    records=defaultdict(lambda:{'decks':0,'copies':0,'archetypes':set(),'prints':{},'kind':None});events=[];total=0;issues=[]
    try:recent=events_from(fetch(BASE+'/tournaments'))
    except Exception as e:recent=[];issues.append('Tournament index unavailable: '+str(e))
    for event in recent:
        try:
            decks=decks_from(fetch(event['url']))
            if not decks:raise ValueError('No complete 60-card decklists parsed')
            events.append({**event,'decklists':len(decks)});total+=len(decks)
            for deck in decks:
                names=set()
                for c in deck['cards']:
                    r=records[c['name']];r['kind']=c['kind'];r['copies']+=c['copies'];r['archetypes'].add(deck['archetype']);names.add(c['name'])
                    key=c['set']+'/'+c['number'];p=r['prints'].setdefault(key,{**c,'copies':0,'decks':0});p['copies']+=c['copies'];p['decks']+=1
                for name in names:records[name]['decks']+=1
        except Exception as e:issues.append(event['name']+': '+str(e))
    old={c['card']['id']:c['card'] for c in previous.get('cards',[])}
    candidates=[]
    for name,r in sorted(records.items(),key=lambda x:(-x[1]['decks'],-x[1]['copies'],x[0])):
        if name in BASIC or re.search(r' (ex|EX|GX|V|VMAX|VSTAR)$',name):continue
        p=max(r['prints'].values(),key=lambda p:p['decks'])
        prefix=SETS.get(p['set'])
        if not prefix:continue
        candidates.append((name,r,p,prefix+'-'+p['number']))
        if len(candidates)>=65:break
    def metadata(item):
        name,r,p,card_id=item;retained=False
        try:
            card=json.loads(fetch('https://api.tcgdex.net/v2/en/cards/'+card_id))
            if card.get('id')!=card_id or card.get('name')!=name:raise ValueError('Printing mismatch')
        except Exception:
            card=old.get(card_id);retained=True
        if not card or card.get('rarity') not in RARITIES:return None
        return {'name':name,'kind':r['kind'],'decks':r['decks'],'pct':round(r['decks']/total*100,2),'copies':r['copies'],'avgCopies':round(r['copies']/r['decks'],2),'archetypes':sorted(r['archetypes']),'card':{'id':card['id'],'name':card['name'],'localId':card['localId'],'image':card.get('image'),'rarity':card['rarity'],'category':card.get('category'),'set':card.get('set'),'pricing':card.get('pricing'),'metadataRetained':retained},'displayedPrice':p['price'],'marketUrl':p['marketUrl'],'printings':[{'set':x['set'],'number':x['number'],'decks':x['decks'],'url':BASE+'/cards/'+x['set']+'/'+x['number']} for x in sorted(r['prints'].values(),key=lambda x:-x['decks'])],'cardUrl':BASE+'/cards/'+p['set']+'/'+p['number']}
    with ThreadPoolExecutor(max_workers=4) as pool:cards=[c for c in pool.map(metadata,candidates) if c]
    buyers=[]
    try:
        s=fetch('https://bulkmon.gg/buylist');decoded=s.replace('\\"','"')
        found=re.findall(r'"name":"([^"]+)"\s*,"buyRateMils":(\d+)',decoded)
        rates=[{'category':html.unescape(n),'usd':int(rate)/1000} for n,rate in dict(found).items()]
        if len(rates)<5:raise ValueError('Category rate schema unavailable')
        buyers.append({'name':'Bulkmon','url':'https://bulkmon.gg/buylist','checkedAt':now(),'status':'ok','terms':'Advertised English NM/LP categories; energies separated; final quote confirmed by buyer.','rates':rates})
    except Exception as e:issues.append('Bulkmon: '+str(e))
    try:
        s=clean(fetch('https://pokemonbulk.com/'));labels=[('VMAX / VSTAR',r'Vmax\s*/\s*Vstar'),('V/EX/GX',r'V/EX/GX'),('Textured',r'Textured'),('WoTC',r'WoTC'),('Reverse & Holo',r'Reverse\s*&\s*Holo')];rates=[]
        for name,pat in labels:
            m=re.search(pat+r'\s*\$([\d.]+)',s,re.I)
            if m:rates.append({'category':name,'usd':float(m[1])})
        if len(rates)<3:raise ValueError('Rates unavailable')
        buyers.append({'name':'Pokemonbulk','url':'https://pokemonbulk.com/','checkedAt':now(),'status':'ok','terms':'Advertised English Near Mint buylist. Confirm accepted printings and shipping before submitting.','rates':rates})
    except Exception as e:issues.append('Pokemonbulk: '+str(e))
    for buyer in previous.get('buyers',[]):
        if buyer['name'] not in {b['name'] for b in buyers}:buyers.append({**buyer,'status':'retained'})
    if not cards:
        if not previous.get('cards'):raise RuntimeError('No verified bulk candidates')
        previous['lastAttemptAt']=now();previous['status']='retained';previous['issues']=issues;previous['buyers']=buyers;write(previous);return
    out={'checkedAt':now(),'status':'partial' if issues else 'ok','selection':'Latest three eligible completed Standard events with published decklists; ordinary Common/Uncommon/Rare printings only.','totalDecklists':total,'events':events,'cards':cards[:40],'candidatesChecked':len(candidates),'buyers':buyers,'issues':issues}
    write(out);print('Bulk signals:',len(out['cards']),'cards,',total,'complete published decks');print([(c['name'],c['decks'],c['pct']) for c in out['cards'][:8]])
if __name__=='__main__':refresh()
