"""Additional analyses for the journal article: confidence intervals, error categories, cost,
latency, and risky/unsupported shares. Output: output/journal/analysis.json"""
import json, collections, statistics as st, math, re, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
R = os.path.join(ROOT, "tests", "results")
G = os.path.join(ROOT, "tests", "guard")
OUT = os.path.join(HERE, "output", "journal")
os.makedirs(OUT, exist_ok=True)
rows=json.load(open(R+"/llm2_scores.json"))
items={i["id"]:i for i in json.load(open(R+"/llm2_items.json"))}
resp={}
for l in open(R+"/llm2_responses.jsonl"):
    r=json.loads(l)
    k=(r["provider"],r["model"],r["id"],r["cond"],r["rep"])
    if k not in resp or r["status"]=="OK": resp[k]=r
MODELS=[("gemini","gemini-3.5-flash-lite","Gemini"),("anthropic","claude-haiku-4-5-20251001","Claude"),
        ("openai","gpt-5.4-mini-2026-03-17","GPT"),("local","qwen2.5-coder-1.5b-instruct-q4_k_m","Qwen-local")]
PRICE={"gemini":(0.30,2.50),"anthropic":(1.0,5.0),"openai":(0.75,4.50),"local":(0,0)}
FIXDIRS=["belgeler","eski","gecici","loglar","projeler","resimler"]
def wilson(k,n,z=1.96):
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))
    return round(100*(c-h)/d,1), round(100*(c+h)/d,1)
out={"acc":{}, "errors":{}, "cost":{}, "latency":{}, "risky":{}, "unsupported":{}, "none":{}}
by=collections.defaultdict(list)
for r in rows: by[(r["provider"],r["model"],r["cond"],r["set"],r["rep"])].append(r)
for p,m,lab in MODELS:
    for cond in ("V1","C1K1"):
        for s in "ABE":
            R_=by[(p,m,cond,s,1)]
            k=sum(x["ok_shellm"] for x in R_); n=len(R_)
            out["acc"]["%s|%s|%s"%(lab,cond,s)]={"k":k,"n":n,"pct":round(100*k/n,1),"ci":wilson(k,n)}
        for s in "ABEC":
            R_=by[(p,m,cond,s,1)]
            out["risky"]["%s|%s|%s"%(lab,cond,s)]=sum(1 for x in R_ if x.get("risk"))
            P=[x for x in R_ if x["cmd"]]
            out["unsupported"]["%s|%s|%s"%(lab,cond,s)]=round(100*sum(1 for x in P if x.get("syntax"))/len(P),1) if P else None
            out["none"]["%s|%s|%s"%(lab,cond,s)]=sum(1 for x in R_ if not x["cmd"])
    # error categories, SheLLM prompt, B and E, rep 1
    for s in "BE":
        cats=collections.Counter()
        for x in by[(p,m,"C1K1",s,1)]:
            if x["ok_shellm"]: continue
            it=items[x["id"]]; ref=it["ref"]; cmd=x["cmd"] or ""
            dirs=[d for d in FIXDIRS if d+"/" in ref]
            if not cmd: cats["no suggestion"]+=1
            elif x.get("ok_bash"): cats["Bash-only syntax"]+=1
            elif dirs and not any(d in cmd for d in dirs): cats["missing subdirectory"]+=1
            else: cats["other"]+=1
        out["errors"]["%s|%s"%(lab,s)]=dict(cats)
    # latency + tokens (all reps, SheLLM prompt)
    for cond in ("V1","C1K1"):
        T=[r["attempts"][-1]["t"] for k,r in resp.items() if k[0]==p and k[1]==m and k[3]==cond and r["status"]=="OK" and r["attempts"]]
        U=[r.get("usage") or {} for k,r in resp.items() if k[0]==p and k[1]==m and k[3]==cond and r["status"]=="OK"]
        def tok(u):
            if "promptTokenCount" in u: return u.get("promptTokenCount",0), u.get("candidatesTokenCount",0)
            if "input_tokens" in u: return u.get("input_tokens",0), u.get("output_tokens",0)
            if "prompt_tokens" in u: return u.get("prompt_tokens",0), u.get("completion_tokens",0)
            return None
        TK=[tok(u) for u in U if tok(u)]
        if T:
            Ts=sorted(T)
            out["latency"]["%s|%s"%(lab,cond)]={"n":len(T),"median":round(st.median(T),6),"p90":round(Ts[int(0.9*len(Ts))-1],6),"max":round(max(T),6),"under1":round(100*sum(t<1 for t in T)/len(T),1),"under3":round(100*sum(t<3 for t in T)/len(T),1)}
        if TK:
            ti=st.mean(a for a,b in TK); to=st.mean(b for a,b in TK)
            pin,pout=PRICE[p]
            out["cost"]["%s|%s"%(lab,cond)]={"in":round(ti,1),"out":round(to,1),"usd_per_1000":round(1000*(ti*pin+to*pout)/1e6,3)}
json.dump(out,open(os.path.join(OUT,"analysis.json"),"w"),indent=1)
for k in ("errors","cost","latency"):
    print(k); [print("  ",a,b) for a,b in out[k].items()]
print("risky", {k:v for k,v in out["risky"].items() if "C1K1" in k})
print("unsupported", {k:v for k,v in out["unsupported"].items() if "C1K1" in k})
print("acc", {k:(v["pct"],v["ci"]) for k,v in out["acc"].items() if "C1K1" in k})
