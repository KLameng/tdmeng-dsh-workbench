# -*- coding: utf-8 -*-
import json, urllib.request

def q(vid, ds="gnomad_r2_1", endpoint="v2"):
    query = '{ variant(id: "%s", dataset: %s) { variant_id rsid allele_freq } }' % (vid, ds)
    body = json.dumps({"query": query}).encode()
    url = "https://gnomad.broadinstitute.org/api/gnomad/%s/variant" % endpoint
    req = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode()
    except Exception as e:
        return "ERR: %s" % e

if __name__ == "__main__":
    import sys
    # 已知 gnomAD 收录变异：GJB2 35delG? 或 CFTR F508del chr7:117199644 (hg38) 3bp del
    tests = ["7-117199644-CTT-CT", "13-51974225-TC-T"]
    for t in tests:
        print("==", t, "==")
        print(q(t))
