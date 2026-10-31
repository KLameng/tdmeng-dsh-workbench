# -*- coding: utf-8 -*-
import json, urllib.request

def q(vid, ds="gnomad_r4"):
    query = """{ variant(id: "%s", dataset: %s) { variant_id rsid chrom pos ref alt allele_freq } }""" % (vid, ds)
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request("https://gnomad.broadinstitute.org/api/gnomad/v4/variant", data=body,
                                 headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode()
    except Exception as e:
        return "ERR: %s" % e

if __name__ == "__main__":
    import sys
    # 测试已知变异 H1069Q ATP7B: chr13:51958082? 用 rs1801177 试试
    vids = sys.argv[1:] if len(sys.argv) > 1 else ["13-51974225-TC-T", "13-51953112-G-A"]
    for v in vids:
        print("==", v, "==")
        print(q(v))
