# ev-pp4 CHANGELOG

2026-10-15 description 瘦身整改：version 变更日志从 SKILL.md frontmatter 下沉至此；同日修复版本序列非单调（原 1.3.0 在 1.1.0/1.2.1 之前，现已按版本号单调升序重排）。

## v1.4.0（PP4 VCEP 基因特异档位路由 + 先查数值后匹配，2026-10-20）

- **新增第 3.5 步 VCEP 基因特异档位路由协议**（与 ev-pm2/ev-bs1-bs2/ev-pp1/ev-pp3-bp4/ev-pm3 同源）：PP4 判定先查 clingen-vcep/VCEP-<gene>.md 的 `#### PP4` 段原文规则，按该基因特异档位定档，优先于通用口径。
- **PP4 证据本质澄清（用户确认 2026-10-20）**：PP4 是"**先查文献/临床数据拿数值 → 再拿数值对照 VCEP 特异规则匹配档位**"的证据链。VCEP 规则只定义"多少数值→哪档"，数值本身必须由执行者先查取（受检者表型/生化值/酶活%/肿瘤计数/多因素 LR，来源：送检信息/病历 + ev-disease-info 表型谱 + 文献数值）。取不到数值就写"查不到"，不得默认给档。
- **新增引擎 `acmg_evidence.py::pp4_vcep_band`**（只做"数值→档位"确定性映射，不做取数）：支持 points 点数型 / count 计数型 / lr 似然比型三数值形态 + phenotype 条件式回退（引擎不判数值，返回需执行者按 VCEP 原文核临床条件）；spec 缺省→通用表型特异 Supporting（行为零变化）；max_band 封顶。
- **PP4 六类形态（85 含 PP4 段基因，全量探查）**：①纯表型特异（~35，耳聋基因等，通用 Supporting）；②点数型（~22，ADA/DCLRE1C/IL2RG/JAK3/IL7R 免疫缺陷 1-<2/2-<6/≥6、RPGR/RPE65/GUCY2D 表型分、GAMT/GATM/OTC）；③表型+生化条件式（~15，GALT 酶活<10%/ACADVL C14:1/VWF 检验值/IDUA/ETHE1/PAH）；④肿瘤 MSI 计数（MLH1/MSH2/MSH6/PMS2 1/2/≥3）；⑤多因素 LR 型（BRCA1/BRCA2 ≥2.08/4.3/18.7:1）；⑥其他条件式（~33 混合，ACTA1/ANO5/DICER1/TP53）。
- 与 v1.3.0 通用表型特异规则一致（通用基因行为零变化）；未引入新矛盾，特异=特异、通用=通用。

## v1.1.0

- 新增遗传方式前置判定硬步骤——判定前必须先调用 `arad-inheritance-judgment` 确认该变异遗传方式，作为"家族史与疾病遗传方式一致"及表型特异性的判定前提，禁止默认遗传方式；遗传方式以 ClinVar 患者基因型+PubMed报道+GenCC MOI 三方交叉为准。

## v1.2.1

- 表型四要素闸就位——①临床表现询问（无表型→PP4 不成立）；②特异性反证检查（多基因异质→不用，判例 HPS3/CNGA3/ETFDH/GRHPR/PKHD1/ERCC4/SLC25A13/G6PD）；③强制搜文献（OMIM/ClinGen/文献 + 按用途提取 + 可疑上报）；④不以 PP4 弱码顶替可取得的 PM3/PP3/PS3（以弱代强违规，HEXB/SLC22A5-51 教训）。

## v1.3.0

- 新增跨技能调用声明——判定表型特异性/外显率/发病率须调用 `ev-disease-info`（NCBI Books GeneReviews 通道，books/medgen/clingen 子命令）获取结构化疾病信息，输出写明子命令与标准疾病名。
