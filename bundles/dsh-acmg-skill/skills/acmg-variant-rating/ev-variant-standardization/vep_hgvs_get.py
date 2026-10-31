# -*- coding: utf-8 -*-
import json, urllib.request, urllib.parse

def vep_get(path):
    url = "https://rest.ensembl.org" + path
    req = urllib.request.Request(url, headers={"Content-Type":"application/json","Accept":"application/json","User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import sys
    # 正确 VEP region 格式: /vep/human/region/{chr}:{start}-{end}:{strand}/{ref}/{alt}?...
    # 删除变异: chr13 删除 C 于 51974226 => region 13:51974226-51974226:1/C/T 不对; 用 hgvs
    hgvs = sys.argv[1] if len(sys.argv) > 1 else "NM_000053.4:c.994delG"
    path = "/vep/human/hgvs/" + urllib.parse.quote(hgvs, safe="") + "?gnomad=1&refseq=1"
    print(json.dumps(vep_get(path), ensure_ascii=False, indent=2))
