#!/usr/bin/env python3
import os, sys, json, signal, time, math, traceback, datetime as dt
from collections import defaultdict

BASE_DIR = os.environ.get("BASE_DIR", "/opt/sb-simple")
LEVELS_PATH = os.environ.get("LEVELS_PATH", f"{BASE_DIR}/data/levels.json")
DATASET = os.environ.get("DATASET", "GLBX.MDP3")
SYMBOL  = os.environ.get("SYMBOL", "NQZ5")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")
SEND_LIVE = os.environ.get("SEND_LIVE_ALERTS", "").lower() in ("1","true","yes")
PRICE_DIVISOR = float(os.environ.get("PRICE_DIVISOR", "1e2"))

def post_to_discord(m): 
    if not (SEND_LIVE and DISCORD_WEBHOOK): return
    try:
        import urllib.request as u; u.urlopen(
          u.Request(DISCORD_WEBHOOK, json.dumps({"content":m}).encode(),
          {"Content-Type":"application/json"}), timeout=5)
    except: pass

def load_levels():
    try:
        with open(LEVELS_PATH,"r") as f: d=json.load(f); lv=d.get("levels",d)
        return {k:float(v) for k,v in lv.items()}
    except: return {}

class Bar:
    def __init__(self,m,p,s): self.m=m;self.o=p;self.h=p;self.l=p;self.c=p;self.v=s
    def update(self,p,s): self.h=max(self.h,p);self.l=min(self.l,p);self.c=p;self.v+=s

def floor_m(t): return t.replace(second=0,microsecond=0)
def extract(tr):
    p = getattr(tr,"price",None); s = getattr(tr,"size",getattr(tr,"qty",0))
    for t in ("ts_event","ts_recv","ts_exchange","ts"):
        ns=getattr(tr,t,None)
        if ns: return float(p)/PRICE_DIVISOR,float(s),dt.datetime.utcfromtimestamp(ns/1e9).replace(tzinfo=dt.timezone.utc)
    return None

def run():
    lv=load_levels(); print("[LEVELS]",lv); post_to_discord(f"LIVE stream start {SYMBOL}")
    class LA:
        def __init__(self,lv): self.lv=lv; self.hit={k:False for k in lv}
        def chk(self,b):
            for k,v in self.lv.items():
                if not self.hit[k] and ((k.find("high")>-1 and b.c>=v) or (k.find("low")>-1 and b.c<=v)):
                    self.hit[k]=True; msg=f"⚡ {SYMBOL} {k} hit {v:.2f} (c={b.c:.2f})"; print(msg); post_to_discord(msg)
    alerts=LA(lv); bar=None; cur=None
    key=os.environ.get("DB_API_KEY") or os.environ.get("DB_KEY")
    try:
        from databento_live import Live
    except:
        from databento import Live
    live=Live(key=key)
    stop={"go":True}
    signal.signal(signal.SIGINT,lambda *_:stop.update(go=False))
    signal.signal(signal.SIGTERM,lambda *_:stop.update(go=False))
    while stop["go"]:
        try:
sess = getattr(live, "_session", None)
if sess is None:
    sess = getattr(live, "session", None)
if callable(sess):
    sess = sess()
try:
                sess.subscribe(dataset=DATASET, schema="trades", symbols=[SYMBOL])
                for msg in sess:
                    if not stop["go"]: break
                    rows = msg if isinstance(msg,list) else getattr(msg,"data",[msg])
                    for r in rows:
                        t=extract(r)
                        if not t: continue
                        p,s,ts=t; m=floor_m(ts)
                        if cur is None: cur=m; bar=Bar(m,p,s)
                        elif m==cur: bar.update(p,s)
                        else:
                            alerts.chk(bar)
                            print(f"[BAR] {bar.m:%H:%M} O:{bar.o} H:{bar.h} L:{bar.l} C:{bar.c} V:{bar.v}")
                            cur=m; bar=Bar(m,p,s)
        except Exception as e:
            print("[ERR]",e); traceback.print_exc(); time.sleep(3)
    post_to_discord(f"🟡 LIVE stream stopped {SYMBOL}")

if __name__=="__main__": run()
finally:
    try:
        sess.close()
    except Exception:
        pass