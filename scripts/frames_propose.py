"""Spec vs frame data for one Trekker: python scripts/frames_propose.py <char id> (after python -m ssr.frames extract)."""
import sys, yaml, collections
from ssr.frames import load, clip_hits, auto_chain, prefab_hits
from ssr.data import GameData
gd = GameData()
def bucket(h):
    r = gd.table("HitDamage").get(str(h)); return {1:"A",2:"S",3:"U",7:"M"}.get(r.get("DamageType"),"?") if r else "x"
def summarize(hits):
    by = collections.OrderedDict()
    for t,h,src in hits:
        by.setdefault((h,src if h=="script" else ""),[]).append(t)
    out=[]
    for (h,s),ts in by.items():
        if h=="script": out.append(f"script {s!r}@{','.join(str(t) for t in ts[:6])}"); continue
        iv = round((ts[-1]-ts[0])/(len(ts)-1),3) if len(ts)>1 else None
        out.append(f"{h}{bucket(h)} x{len(ts)} @{ts[0]}" + (f" iv {iv}" if iv else "") + (f" [{','.join(str(t) for t in ts)}]" if len(ts)<=8 and len(ts)>1 else ""))
    return out
cid=int(sys.argv[1]); d=load(cid); y=yaml.safe_load(open(f"specs/trekkers/{cid}.yaml"))
print(f"##### {cid} {gd.char_name(cid)}")
for role in ("main","support"):
    sec=y.get(role)
    if not sec: continue
    print(f"--- spec {role} untimed={sec.get('untimed')} on_field={sec.get('on_field')}")
    for a,act in (sec.get("actions") or {}).items():
        print(f"  {a}: dur={act.get('duration')} lock={act.get('lock')}")
        for h in act.get("hits",[]): print(f"     {h.get('hit')} x{h.get('count',1)} @{h.get('offset',0)} iv {h.get('interval','')} {h.get('tags','')}")
ac=auto_chain(d)
print(f"--- data auto chain period {ac['period']} strikes {ac['strikes']}")
for s in summarize(ac['hits']): print("     ",s)
for c in d["groups"][0]["combos"]:
    if c["kind"] in ("skill","ult","0") or (c['kind']=='auto' and c['tag'] not in [s[0] for s in ac['strikes']]):
        t=0; hits=[]; parts=[]
        for n in c["clips"]:
            k=d["clips"].get(n)
            if not k: continue
            hits+=clip_hits(k,t); parts.append(f"{k['duration']}/{k['combo'][1]}"); t+=k['duration']
        print(f"--- {c['kind']} {c['tag']!r} keys {c['keys']} clips(dur/comboEnd) {parts}  {[x.replace('ComboClip_','') for x in c['clips']]}")
        for s in summarize(hits): print("     ",s)
print("--- script weapons (hit id: delay/interval/area duration)")
for n,p in d["script_weapons"].items():
    hs=prefab_hits(p,0.0)
    if hs: print(f"     {n}: "+"; ".join(summarize(hs)))
