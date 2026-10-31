# -*- coding: utf-8 -*-
import json, urllib.request

def vep_region_post(variants):
    payload = json.dumps({"variants": variants}).encode()
    url = "https://rest.ensembl.org/vep/human/region?gnomad=1&dbNSFP=1&merged=1&refseq=1"
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import sys
    variants = sys.argv[1:]
    print(json.dumps(vep_region_post(variants), ensure_ascii=False, indent=2))
