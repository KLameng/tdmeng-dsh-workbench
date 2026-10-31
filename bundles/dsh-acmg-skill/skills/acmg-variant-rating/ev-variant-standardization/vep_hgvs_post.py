# -*- coding: utf-8 -*-
import json, urllib.request

def vep_hgvs_post(hgvs_list):
    payload = json.dumps({"hgvs_notations": hgvs_list}).encode()
    url = "https://rest.ensembl.org/vep/human/hgvs?refseq=1&gnomad=1&dbNSFP=1&merged=1"
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import sys
    hgvs = sys.argv[1:] or ["NM_000053.4:c.994delG"]
    print(json.dumps(vep_hgvs_post(hgvs), ensure_ascii=False, indent=2))
