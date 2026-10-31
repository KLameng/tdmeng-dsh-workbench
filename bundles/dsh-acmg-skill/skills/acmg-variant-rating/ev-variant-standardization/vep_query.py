# -*- coding: utf-8 -*-
import json, urllib.request

def vep_region(region, ref, alt):
    url = "https://rest.ensembl.org/vep/human/region/%s/%s/%s?refseq=1" % (region, ref, alt)
    req = urllib.request.Request(url, headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import sys
    region = sys.argv[1]; ref = sys.argv[2]; alt = sys.argv[3]
    res = vep_region(region, ref, alt)
    print(json.dumps(res, ensure_ascii=False, indent=2))
