# -*- coding: utf-8 -*-
import json, urllib.request

def q(vid, ds="gnomad_r4"):
    query = '{ variant(id: "%s", dataset: %s) { variant_id rsid allele_freq } }' % (vid, ds)
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
    for v in sys.argv[1:]:
        print("==", v, "==")
        print(q(v))
