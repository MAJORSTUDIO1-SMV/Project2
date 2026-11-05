#!/usr/bin/env python3
"""Plain-count scoring: python3 -I score_against_gold.py gold_v2.json observations_v2.json"""
import json,sys
gold=json.load(open(sys.argv[1])); obs=json.load(open(sys.argv[2]))
tot=dict(gold=0,matched=0,missing=0,extra=0,wrong_value=0,wrong_scale=0,wrong_avail=0)
for g in gold:
    lo,hi=g["rows_covered"]
    mine={(o["row_no"],o["market_place"]):o for o in obs if o["block_uid"]==g["block_uid"] and o["table_no"]==0 and lo<=o["row_no"]<=hi}
    exp={(x["row_no"],x["market_place"]):x for x in g["expected"]}
    print("==",g["block_uid"][-40:])
    for k,x in exp.items():
        tot["gold"]+=1
        o=mine.get(k)
        if not o: tot["missing"]+=1; print("  MISSING",k); continue
        tot["matched"]+=1
        for f in ("price_low","price_high"):
            a,b=x[f],o[f]
            if (a is None)!=(b is None) or (a is not None and abs(a-b)>1e-6):
                tot["wrong_value"]+=1; print("  VALUE",k,f,"gold",a,"parser",b)
        if x["price_scale"] and x["price_scale"]!=o["price_scale"]:
            tot["wrong_scale"]+=1; print("  SCALE",k,"gold",x["price_scale"],"parser",o["price_scale"])
        if x["availability_note"] and x["availability_note"].lower() not in (o["availability_note"] or "").lower():
            tot["wrong_avail"]+=1; print("  AVAIL",k,"gold",x["availability_note"],"parser",o["availability_note"])
    for k in mine:
        if k not in exp: tot["extra"]+=1; print("  EXTRA",k,mine[k]["item_as_printed"][:40])
print(tot)
