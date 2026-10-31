# -*- coding: utf-8 -*-
import json, urllib.request, urllib.parse

def myvariant(hgvs_or_vcf):
    url = "https://myvariant.info/v1/variant/%s?fields=dbnsfp,gnomad_exome,gnomad_genome,clinvar,1000g,esp_exac,rsid" % urllib.parse.quote(hgvs_or_vcf)
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode()
    except Exception as e:
        return "ERR: %s" % e

if __name__ == "__main__":
    import sys
    for v in sys.argv[1:]:
        print("==", v, "==")
        print(myvariant(v))
