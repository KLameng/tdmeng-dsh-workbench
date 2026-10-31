# -*- coding: utf-8 -*-
from pyliftover import LiftOver
lo = LiftOver('hg38', 'hg19')
res = lo.convert_coordinate('chr13', 51974225)
print(res)
