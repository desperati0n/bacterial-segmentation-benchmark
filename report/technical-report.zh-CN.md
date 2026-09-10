[English](technical-report.md) | **简体中文**

# 细菌显微图像实例分割技术调研与模型实测报告

> **公开仓库版说明**：本仓库保留完整四模型对比画廊、报告图表和指标 CSV，不分发全量原始图片、可视化增强数据、模型权重及批量预测掩膜。

**调研对象**：细菌显微图像的自动实例分割、定量测量与人工复核流程
**日期**：2026-08-20
**测试硬件**：NVIDIA GeForce RTX 4060 Laptop GPU
**现有数据**：在已扫描“人工、传统算法、传统图像分割、分割后、分割较好、mask”等目录后，得到 2,902 张可靠原图–既有处理 mask 配对（明场/相差 1,691 张，荧光 1,211 张）；另有 576 个处理文件未找到可靠原图配对，保留在清单中但不纳入主统计。四模型全量实例标签均已完成：Cellpose-SAM 2,902、MicroSAM DeepBacs 2,902、Omnipose `bact_phase` 1,691、Omnipose `bact_fluor` 1,211（目录中另有 3 个早期跨模态诊断文件）。人工/人工候选掩码清单仍为 15 张，其中 11 张通过质量核对、可直接作为定量 GT，另 4 张需要修复或复核后再纳入准确率测试。

## 1. 调研结论

本调研不预设单一业务场景，因此不把“分出来多少个细菌”作为唯一目标，而是从 **检出、实例分离、边界、形态定量、荧光定量、鲁棒性、效率和人工复核成本** 多个维度考察模型。GUI 只是运行和人工修正的一种落地入口，不是本调研的主题；正式批量比较应以固定参数的脚本/API为主。

- 在当前 11 张可用荧光人工 GT 上，Cellpose-SAM `cpsam_v2` 的平均 **AP@0.50 = 0.3322**、前景 **Dice = 0.6693** 和中位相对计数误差 **0.0460** 最好，但有 284 次 split，AP@0.75 和 Boundary F1 偏低，说明“总数接近”并不等于每个菌体切割正确。
- MicroSAM DeepBacs 的 **AP@0.75 = 0.0655、Boundary F1 = 0.5512** 最好，split/merge 总量最低。在 IoU≥0.50 的匹配实例上，它的面积、长度、宽度和积分荧光强度中位相对误差也最低。它的优势是边界和单菌测量更稳，不是整体覆盖或视觉效果最好；当前四模型画廊中，Cellpose-SAM 才是视觉完整度和覆盖最好的基线。
- Omnipose 的细菌专用模型具有明确的明场/相差和荧光分工；本批荧光数据中 `bact_fluor` 的前景 Dice 为 0.5989，但出现 278 次 merge，主要风险是密集菌体粘连。
- 当前没有明场人工 GT，因此明场结果只能用于流程一致性和失败模式观察，不能给出真实准确率。没有具体业务场景时，也不应宣称一个模型在所有任务上“最好”。
- 许可证方面，Cellpose-SAM `cpsam_v2` 和 MicroSAM DeepBacs 可以用于商业应用，但应保留相应版权、许可证和模型署名；本次实际测试的 Omnipose 1.1.4 使用 University of Washington 的 NonCommercial License，商业使用前需要另行取得 UW CoMotion 授权。训练数据许可证、软件代码许可证和模型权重许可证必须分开判断。

## 2. 技术路线与项目来源

| 项目 | 官方仓库 | 本次模型/权重 | 调研中的角色 |
|---|---|---|---|
| Cellpose / Cellpose-SAM | [MouseLand/cellpose](https://github.com/MouseLand/cellpose) | `cpsam_v2` | 通用强基线，考察跨模态泛化和快速全图分割 |
| Omnipose | [kevinjohncutler/omnipose](https://github.com/kevinjohncutler/omnipose) | `bact_phase_omnitorch_0`、`bact_fluor_omnitorch_0` | 细菌专用基线，分别面向明场/相差与荧光 |
| microSAM | [computational-cell-analytics/micro-sam](https://github.com/computational-cell-analytics/micro-sam) | DeepBacs Specialist：`vit_l.pt` + `vit_l_decoder.pt` | 自动实例分割与交互修正候选 |

### 2.1 为什么选择这些模型

**Cellpose-SAM `cpsam_v2`** 是非细菌专用的通用模型。将它纳入可以回答：通用基础模型在未针对本地细菌形态训练时，能否提供足够强的起点，以及后续是否值得用本地 GT 微调。

**Omnipose `bact_phase` / `bact_fluor`** 针对细长、弯曲、分支或密集对象设计，适合研究普通细胞模型容易粘连的细菌实例。两个权重按成像模态分开，避免用荧光先验处理相差图，或反过来。

**MicroSAM DeepBacs Specialist** 使用显微图像分割框架和 DeepBacs 专精权重，既可自动产生实例，也能通过点、框、笔刷等提示进行修正。它适合“模型初分割—人工复核—保留可追溯标签”的实验室工作流。

## 3. 现有人工真值实测

### 3.1 评估口径

人工掩码清单共 15 张：其中 11 张已通过空间配对、前景形态和颜色/渲染质量检查，可直接用于定量；1 张与原图空间错位，3 张含渲染伪影或异常颜色，暂不把它们当作“正确答案”。这 15 张候选图目前都已经有四个模型的预测掩码（共 60 份），所以扩充测试集不需要重新推理，主要工作是修复并复核 4 张参考掩码，然后按同一函数追加准确率计算。由于当前四模型批量推理和评估统一使用 512×512 输入窗口：大于 512×512 的原图先做中心裁剪，已经是 512×512 的图像直接使用；对应 GT/传统 mask 使用完全相同的裁剪框，当前不做整图缩放。预测与 GT 因此处于相同的 512×512 坐标；实例指标通过 IoU 阈值下的一对一匹配计算。`cpsam_v2` 使用现有四模型掩码按同一函数重算，所有模型均采用统一定量评估口径。后续若纳入小于 512×512 的图片，需要先按同一输入规范补边或调整尺寸。

**人工掩码覆盖审计**：当前测试不是只“挑了 11 张有 mask 的图”，而是先把清单中的 15 张人工/人工候选掩码逐张检查，再将 11 张合格样本纳入准确率计算。剩余 4 张仍保留在审计表中，后续修复后可无缝追加，避免把有明显错位或渲染伪影的标签误当成真值。详见 [人工掩码覆盖审计](../results/detailed/人工掩码覆盖审计.csv) 和 [汇总](../results/manual_gt_audit_summary.csv)。

#### 关键指标怎么读

- **`n`**：参与统计的人工 GT 图像数量，不是模型性能分数；样本越多，抽样偶然性通常越小。
- **AP@0.50**：预测实例与 GT 的 IoU 至少达到 0.50 时的平均精度，兼顾检出和实例重叠；越高越好，适合看“菌体有没有被正确找到”。
- **AP@0.75**：更严格的实例平均精度，要求预测轮廓与 GT 重叠更充分；越高越好，更能暴露边界偏移、过分割和粘连。
- **前景 IoU / 前景 Dice**：把所有实例合并成前景后，与 GT 的像素重叠；越高越好，但看不出实例是否互相串在一起，Dice 通常比 IoU 更宽容。
- **Boundary F1**：预测轮廓与 GT 轮廓的 precision/recall 综合分数；越高越好，代表边界位置更贴近。
- **中位相对计数误差**：`|预测实例数−GT实例数| / GT实例数` 的逐图中位数；越低越好，0 表示计数完全一致，但计数接近仍可能存在 split/merge。
- **split**：一个 GT 菌体被预测成多个实例的过分割事件；越低越好，否则单菌面积、强度和计数解释会受影响。
- **merge**：多个 GT 菌体被合成一个预测实例的粘连/欠分割事件；越低越好，否则会漏掉单菌并混合其形态与荧光信号。

因此，模型不能按单一列排序：AP/Dice 看覆盖和检出，AP@0.75/Boundary F1 看轮廓，计数误差看总体数量，split/merge 则解释数量为什么会偏差。

**核心质量指标**（越高越好）：

| 模型 | n | AP@0.50 | AP@0.75 | 前景 IoU | 前景 Dice | Boundary F1 |
|---|---:|---:|---:|---:|---:|---:|
| Cellpose-SAM `cpsam_v2` | 11 | **0.3322** | 0.0183 | **0.5099** | **0.6693** | 0.3496 |
| MicroSAM DeepBacs AIS | 11 | 0.3174 | **0.0655** | 0.4063 | 0.5251 | **0.5512** |
| Omnipose `bact_fluor` | 11 | 0.1892 | 0.0188 | 0.4501 | 0.5989 | 0.4842 |

**错误结构指标**（越低越好）：

| 模型 | 中位相对计数误差 | split | merge |
|---|---:|---:|---:|
| Cellpose-SAM `cpsam_v2` | **0.0460** | 284 | 121 |
| MicroSAM DeepBacs AIS | 0.1519 | **69** | **99** |
| Omnipose `bact_fluor` | 0.3663 | 82 | 278 |

`bact_phase_omnitorch_0` 是明场/相差专用权重，不应在这 11 张可用荧光人工 GT 上参与准确率排名。

![人工GT准确率指标](../figures/metrics/准确率指标_人工GT_11张荧光.png)

### 3.2 视觉最佳与定量最佳不是同一件事：模型输出的形态与荧光量

先给出直观结论：从本报告的四模型画廊看，**Cellpose-SAM `cpsam_v2` 是本批视觉完整度、前景覆盖和计数表现最好的基线**，尤其在密集荧光图中更容易看到连续、完整的菌体轮廓。因此，本节不是要把 MicroSAM 宣称为“总体最好”，而是解释它在另一条评价轴上的优势。

MicroSAM DeepBacs 的优势主要是 **严格重叠和单菌实例保真**：它的 AP@0.75、Boundary F1 最高，split/merge 总量最低，说明留下的实例边界和分离关系更可靠。代价是它在部分密集图中检出的实例更少，视觉上不如 Cellpose“铺得满”，所以它不应被解释为更高召回或更好计数的模型。实际选型应按任务分工：看全图覆盖、快速计数和视觉初筛优先 Cellpose；看单菌边界、形态测量、荧光定量或人工修正优先 MicroSAM。

这里还要区分两类信息：当前人工图片/人工参考主要用于核对 **count、实例是否对应以及分割区域是否重合**；我们没有一份独立的“人工逐菌长度、宽度、方向和荧光强度测量表”。因此，下面的面积、长轴、短轴、长宽比、方向、平均强度和积分强度，都是把模型输出的实例标签映射回原始图像后得到的 **模型派生测量量**，不是从人工图片直接读出的人工定量真值。

对每个预测实例和人工参考实例建立 IoU≥0.50 的一对一匹配，再在原始荧光图上计算这些模型派生量，并观察它们相对参考区域的偏差。下表均为匹配实例的中位数；相对误差越低越好。这样做的意义是回答“模型切出的区域是否足以支撑后续形态/荧光分析”，而不是声称人工已经逐菌测量过这些数值。

| 模型 | 匹配实例数* | 匹配 IoU | 面积误差 | 长度误差 | 宽度误差 | 长宽比误差 | 平均强度误差 | 积分强度误差 | 方向误差 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cellpose-SAM `cpsam_v2` | 1197 | 0.585 | 61.1% | 19.6% | 32.7% | 15.3% | 3.2% | 55.3% | **3.7°** |
| MicroSAM DeepBacs | 838 | **0.678** | **17.8%** | **9.8%** | **10.8%** | **13.1%** | **1.3%** | **16.8%** | 4.0° |
| Omnipose `bact_fluor` | 595 | 0.604 | 45.5% | 17.8% | 24.7% | 13.5% | 2.9% | 41.1% | **3.7°** |

\*“匹配实例数”受召回率、过分割和匹配阈值共同影响，不是独立准确率；未匹配的漏检和误检已由 AP、precision/recall 与 split/merge 反映。形态与强度表只回答“成功匹配后，定量值保真到什么程度”，存在匹配样本选择偏差。

形态表中，**匹配 IoU 越高越好**；面积、长度、宽度、长宽比、平均强度、积分强度和方向误差均为绝对相对误差或角度误差，**越低越好，0 表示与 GT 完全一致**。积分强度误差还会同时受到实例面积和像素强度误差影响。

![匹配实例形态与荧光定量误差](../figures/metrics/匹配实例_形态与荧光定量误差.png)

这组结果揭示了 count 看不到的问题：Cellpose-SAM 总数和视觉覆盖最好，但模型派生的匹配实例面积和积分强度误差较大，与其高 split 相互印证；DeepBacs 的匹配数量不是最高，却更能保存单个菌体的几何和荧光定量。由此得到的是“任务分工”而不是单一冠军：**Cellpose 负责覆盖/计数基线，MicroSAM 负责边界/单菌测量候选**。

### 3.3 逐图波动和错误结构

![逐图AP50与相对计数误差](../figures/metrics/逐图_AP50与相对计数误差分布.png)

![split与merge错误](../figures/metrics/实例级错误结构_split_merge.png)

平均数会掩盖通道、密度和图像质量造成的波动。正式结论应至少同时报告逐图分布、中位数、四分位区间和 bootstrap 置信区间，并按成像模态、通道、密度、信噪比、菌体大小与批次分层。

### 3.4 与传统 `-mask` 的一致性

当前明场没有人工 GT，只有旧流程掩码。以下数值只说明新模型与旧流程有多相似，不能称为真实准确率：

| 模态 | 参照图数 | 模型 | 前景 Dice | Boundary F1 |
|---|---:|---|---:|---:|
| 明场 | 3 | MicroSAM DeepBacs AIS | **0.8966** | **0.9344** |
| 明场 | 3 | Cellpose-SAM `cpsam_v2` | 0.6159 | 0.6397 |
| 明场 | 3 | Omnipose `bact_phase` | 0.1408 | 0.4825 |
| 荧光 | 6 | MicroSAM DeepBacs AIS | **0.7841** | **0.7786** |
| 荧光 | 6 | Cellpose-SAM `cpsam_v2` | 0.6766 | 0.5877 |
| 荧光 | 6 | Omnipose `bact_fluor` | 0.7097 | 0.5074 |

Cellpose 已补入这张表。它在这里表示“与旧流程 mask 的相似程度”，不是人工真值准确率；因此不能直接拿这组数和上面的 11 张可用人工 GT 结果混排。

![传统mask一致性](../figures/metrics/传统mask一致性_明场与荧光.png)

### 3.5 全量扩展集：与已有处理 mask 的一致性

为了解决 11 张高质量人工 GT 难以覆盖真实资料目录的问题，进一步扫描并配对了 2,902 张原图–既有处理结果：明场/相差 1,691 张，荧光 1,211 张。扫描规则覆盖目录名含“人工、传统算法、传统图像分割、分割后、分割较好、mask”等处理结果；只有能通过文件名/尺寸/路径规则可靠回溯到原图的记录才进入配对清单，另外 576 个未可靠配对的处理文件只在清单中说明，不强行纳入。

这一扩展集的参考对象来自人工、传统算法或既有分割流程，质量和来源并不统一，所以下表只能称为**与已有处理 mask 的一致性**，不能称为人工 GT 准确率。11 张高质量人工 GT 的真实准确率仍只由第 3.1 节单独报告；两类结果不合并排名。

Omnipose 按模态分流：`bact_phase_omnitorch_0` 只对明场/相差 1,691 张统计，`bact_fluor_omnitorch_0` 只对荧光 1,211 张统计；Cellpose-SAM 与 MicroSAM 面向全部 2,902 张。目录中最早试跑留下的 3 个跨模态 Omnipose 文件仅作诊断，已通过清单 `modality` 字段排除。

| 模态 | 参考图数 | 模型 | 前景 Dice | Boundary F1 | 中位相对计数误差 | split | merge |
|---|---:|---|---:|---:|---:|---:|---:|
| 明场/相差 | 1,691 | Cellpose-SAM `cpsam_v2` | 0.0109 | 0.4992 | 15.0 | 0 | 0 |
| 明场/相差 | 1,691 | MicroSAM DeepBacs | 0.0097 | **0.6164** | 16.0 | 0 | 0 |
| 明场/相差 | 1,691 | Omnipose `bact_phase` | **0.0801** | 0.4357 | 51.0 | 1 | 0 |
| 荧光 | 1,211 | Cellpose-SAM `cpsam_v2` | **0.0488** | 0.3155 | 9.0 | 339 | 145 |
| 荧光 | 1,211 | MicroSAM DeepBacs | 0.0277 | 0.2955 | **8.0** | **90** | **116** |
| 荧光 | 1,211 | Omnipose `bact_fluor` | 0.0480 | **0.3675** | **8.0** | 187 | 315 |

这些均值受到参考 mask 来源、渲染方式、批次和连续序列长度的影响，不能替代独立人工标注。除总体汇总外，报告还提供按资料目录/批次的样本数、目录等权汇总和逐图箱线图；目录等权的荧光前景 Dice 分别为 Cellpose 0.2583、MicroSAM 0.1915、`bact_fluor` 0.2371，说明总体均值不应脱离分层结果解读。

![全量数据覆盖](../figures/metrics/全量数据覆盖_按模态.png)

![四模型完成数量](../figures/metrics/全量四模型完成数量.png)

![明场相差逐图一致性](../figures/metrics/全量参考mask一致性_明场相差_逐图分布.png)

![荧光逐图一致性](../figures/metrics/全量参考mask一致性_荧光_逐图分布.png)

![资料目录批次分层](../figures/metrics/全量样本数_按资料目录批次分层.png)

逐图明细、总体汇总、目录分层汇总和异常读取清单分别见：`全量已处理图_参考mask一致性逐图.csv`、`全量已处理图_参考mask一致性汇总.csv`、`全量已处理图_按资料目录分层汇总.csv` 和 `全量已处理图_参考mask一致性跳过清单.csv`。本次异常清单为空；历史 BMP/JPEG 内容已通过图像解码回退纳入统计。

## 4. 无具体业务场景时的全面评估体系

### 4.1 能得到哪些数据，以及怎么得到

| 维度 | 推荐指标/数据 | 获取方法 | 当前状态 |
|---|---|---|---|
| 像素覆盖 | IoU、Dice、像素 precision/recall、specificity、MCC | 将实例标签转为前景二值图，与同坐标 GT 逐像素比较 | 11 张可用荧光 GT 已可计算；已有 IoU/Dice |
| 实例检出 | AP@0.50:0.95、实例 precision/recall/F1、漏检/误检 | 计算 GT×预测 IoU 矩阵，按阈值一对一匹配 | 已有 AP50/AP75；可从现有掩码补 AP 曲线和实例 P/R/F1 |
| 实例综合质量 | Panoptic Quality（PQ）、Segmentation Quality（SQ）、Recognition Quality（RQ）、AJI/AJI+ | 基于一对一实例匹配，将识别与轮廓质量合并统计 | 现有荧光 GT 可直接补算 |
| 边界质量 | Boundary F1、平均对称表面距离（ASSD）、Hausdorff 95%、轮廓偏移 | 提取 GT/预测轮廓，用距离变换计算双向距离 | 已有 Boundary F1；其余可补算 |
| 拆分/粘连 | split、merge、每个 GT 对应预测数、每个预测包含 GT 数 | 分析实例重叠图而非只比较总数 | 已计算；Cellpose 偏 split，Omnipose 偏 merge |
| 拓扑与中心线 | clDice、骨架重叠、端点/分支点误差、Euler 数、断裂数 | 对杆状/弯曲菌体骨架化后比较中心线和连通性 | 可由现有 GT/预测补算，适合长菌和链状菌 |
| 单菌形态 | 面积、周长、长度、宽度、长宽比、偏心率、方向、圆度、solidity、曲率、骨架长度 | 对模型输出的整数标签图逐实例做 region properties 和骨架分析 | 面积/长宽/方向等模型派生量已实算；其余可从现有标签补出 |
| 荧光定量 | 背景校正的均值/中位数/最大值、积分强度、CV、通道比值、沿长轴强度曲线 | 用模型实例标签索引原始 16-bit 像素；先做暗场/平场及局部背景校正 | 模型派生的均值和积分强度偏差已实算；需保留原始位深与曝光元数据 |
| 空间群体结构 | 菌体密度、覆盖率、最近邻距离、取向一致性、聚集度、菌落边缘/中心差异 | 从每个实例的质心、方向和邻接图统计 | 现有标签可计算，但正确性依赖分割质量 |
| 鲁棒性 | 按模态、通道、密度、大小、SNR、模糊、曝光和批次的指标；扰动退化曲线 | 对数据分层；复制图像并加入可控噪声、模糊、亮度/对比度扰动 | 45 张图可先做探索；可靠结论需扩大分层样本和 GT |
| 不确定性/OOD | 像素熵、模型/参数集成分歧、测试时增强方差、低置信实例比例 | 保存概率图，或对同图多模型/多参数重复推理后计算分歧 | 现有最终标签只能做模型间分歧；完整分析需保存概率/日志 |
| 计算成本 | 单图延迟、吞吐量、峰值显存/RAM、启动时间、模型大小、CPU降级速度 | 固定图像尺寸与批量大小，预热后重复计时并记录系统资源 | 当前仅证明 RTX 4060 可运行；需标准化 benchmark 日志 |
| 人工复核成本 | 每图修正时间、点击/笔刷次数、需修实例比例、最终接受率 | GUI/napari 记录操作事件；修正前后再计算指标 | 尚未记录，是判断交互式方案价值的关键数据 |
| 标注可靠性 | 标注者间 Dice/AP、争议率、复核后变更率 | 至少双人独立标注一个分层子集，再由第三方仲裁 | 当前 GT 经核对，但尚无独立双标一致性数据 |
| 时间序列与生物学 | 生长率、分裂时刻、谱系连续性、IDF1/HOTA、轨迹断裂和身份切换 | 对 time-lapse 连续帧分割并建立实例关联，人工校验事件 | 当前为静态图，需补采时间序列和轨迹 GT |

### 4.2 推荐的数据产物

为了让一次分割既能做模型评估，也能支撑未来未知业务，建议每张图保留以下可追溯产物：

1. 原始图像：保留位深、像素尺寸、通道、曝光、显微镜、批次和样本信息，不只保留显示用 PNG。
2. 整数实例标签 TIFF：背景为 0，每个菌体为唯一正整数；不要只保存彩色叠加图。
3. 模型运行记录：模型名、权重哈希、软件版本、参数、随机种子、输入归一化、裁剪/缩放和运行时间。
4. 逐图指标表：像素、实例、边界、split/merge、PQ/AJI、效率和不确定性。
5. 逐实例长表：`image_id、gt_id、pred_id、match_iou、面积、长度、宽度、方向、强度、是否漏检/误检`，一行一个菌体。
6. 人工修正日志：修正前/后标签、用时和操作数，使“自动准确率”和“达到可用结果的总成本”可以同时评估。

### 4.3 建议的统一计算流程

`原始图与元数据 → 人工 GT / 模型实例标签同坐标化 → 质量检查 → 实例一对一匹配 → 像素/实例/边界/拓扑指标 → 单菌形态与强度回填 → 按模态和质量分层 → bootstrap 置信区间 → 失败案例画廊与可追溯 CSV`

其中，模型排名必须建立在独立留出 GT 上；调阈值用的图不能再次作为最终测试集。传统 mask 可以作为流程参照，但不能代替人工真值。

## 5. 代表性效果与失败模式

### 人工 GT 高密度 sfGFP

该场景用于观察过分割、漏检和密集粘连。彩色块看起来丰富并不代表实例正确，必须结合 AP、split/merge 和单菌形态误差。

![sfGFP dense](../figures/gallery/GT_sfGFP_00025_1_四模型对比.png)

### 人工 GT mScarletI

用于检查不同荧光通道下的短杆边界、相邻菌体分离和单菌强度保真。

![mScarletI](../figures/gallery/GT_mScarletI_00219_1_四模型对比.png)

### 明场密集和低对比场景

以下没有人工 GT，只能用于发现失败模式和制定补标计划，不进入真实准确率排名。

![BF dense](../figures/gallery/GEN_BF_Dense_01_四模型对比.png)

![Low contrast](../figures/gallery/GEN_FAIL_LowContrast_01_四模型对比.png)

## 6. 当前落地配置与执行方式

### 6.1 当前配置

| 项目 | 当前配置 |
|---|---|
| GPU | RTX 4060 Laptop，PyTorch CUDA 可用 |
| 输入尺寸 | 当前批量评估统一采用 512×512 窗口；大图中心裁剪，GT/传统 mask 同步裁剪，小图需先补边或调整尺寸 |
| Cellpose | `.venv-benchmark`，Cellpose 4.2.1.1，模型位于 `models/cellpose/cpsam_v2` |
| Omnipose | `.venv-benchmark`，Omnipose 1.1.4，phase/fluor 权重位于 `models/omni`；使用 Qt 兼容启动器 |
| microSAM | `.venv-microsam` 的 micro-sam 1.8.9；复用 napari 0.8.0 / PyQt6；自动加载 ViT-L 与 AIS decoder |
| GUI 缓存 | 统一放在 `gui/config`，避免散落到系统用户目录 |
| 评估 | 先修正重复样本、错配、裁剪和前景反相，再区分人工 GT 准确率与传统 mask 一致性 |

### 6.2 对应技术文档与操作入口

下面的链接直接对应当前配置中的模型和运行方式：

| 模型/组件 | 模型技术说明 | 运行/操作说明 |
|---|---|---|
| Cellpose-SAM `cpsam_v2` | [Cellpose 模型说明](https://cellpose.readthedocs.io/en/latest/models.html) | [Cellpose GUI 与手动分割](https://cellpose.readthedocs.io/en/latest/gui.html) |
| Omnipose `bact_phase_omnitorch_0` / `bact_fluor_omnitorch_0` | [Omnipose 预训练模型与输入参数](https://omnipose.readthedocs.io/models.html) | [Omnipose 官方文档](https://omnipose.readthedocs.io/) |
| MicroSAM DeepBacs | [microSAM 安装、模型与 CLI/API 文档](https://computational-cell-analytics.github.io/micro-sam/micro_sam.html) | [napari 2D annotator 操作/API](https://computational-cell-analytics.github.io/micro-sam/micro_sam/sam_annotator/annotator_2d.html) |
| napari + microSAM | [microSAM Quickstart 与插件入口](https://computational-cell-analytics.github.io/micro-sam/) | [microSAM 图像序列批处理 annotator](https://computational-cell-analytics.github.io/micro-sam/micro_sam/sam_annotator/image_series_annotator.html) |

使用时可按“模型说明 → 运行入口 → 本地启动器”的顺序核对：先确认模态和模型名，再确认输入通道/尺寸及 GPU 设置，最后用本地 `.bat` 启动器执行。报告中的本地启动器只负责把这些官方入口固定成当前工作区的可复现实验配置。

### 6.3 推荐执行方式

- **批量调研与正式评估**：采用脚本/API固定模型、预处理和参数，批量导出整数标签、概率图、逐图日志和运行耗时。这是可重复比较的主流程。
- **单图检查与人工修正**：采用 Cellpose GUI、Omnipose GUI 或 microSAM + napari。GUI 用于查看参数效果、修正困难实例和建立高质量 GT。
- **模型选择**：明场/相差优先测试 `bact_phase_omnitorch_0` 与 DeepBacs；荧光同时比较 `bact_fluor_omnitorch_0`、DeepBacs 和 `cpsam_v2`。本批数据可先按任务分工：Cellpose 用作视觉覆盖/计数基线，MicroSAM 用作边界和单菌测量候选，Omnipose fluor 重点观察密集粘连；最终仍按具体任务指标选型，而不是只按彩色叠加图主观选择。

### 6.4 GUI 作为一种落地入口

Cellpose 中选择 `cpsam_v2`、GPU 后点击 `run`；Omnipose 中按模态选择细菌模型后点击 `Segment image`；microSAM + napari 通过 annotator 自动分割并使用提示工具修正。

界面截图不随公开仓库分发；GUI 仅作为人工检查和修正入口，正式批量评估仍以固定参数的脚本/API为准。

## 7. 许可证与商业使用分析

本节按 2026-08-21 的实际安装版本和模型来源核对。判断时必须把 **软件代码、预训练权重、训练数据、上游依赖** 四层分开；“训练数据含 NonCommercial 限制”不等于“训练后的权重自动继承 NonCommercial”，但也不能在没有权重许可或权利人说明时自行假定可商用。以下是工程合规分析，不替代公司法务的正式法律意见。

| 本次模型 | 代码/运行框架 | 权重或上游许可 | 商业使用判断 | 主要义务与风险 |
|---|---|---|---|---|
| Cellpose-SAM `cpsam_v2` | Cellpose：BSD-3-Clause | 官方 Cellpose-SAM Hugging Face 仓库标注 BSD-3-Clause；上游 SAM 为 Apache-2.0 | **可以商用** | 保留版权和许可证文本，不暗示 HHMI/作者为产品背书；保存模型来源与版本记录 |
| Omnipose `bact_phase_omnitorch_0` | 本次 Omnipose 1.1.4：Omnipose NonCommercial License | 本次权重随该旧版 Omnipose 路线使用，未获得独立商业授权 | **当前不可直接商用** | 商业使用应联系 University of Washington CoMotion：`license@uw.edu`；不能用当前主分支 MIT 反推旧版 1.1.4 和旧权重已自动重许可 |
| Omnipose `bact_fluor_omnitorch_0` | 本次 Omnipose 1.1.4：Omnipose NonCommercial License | 本次权重随该旧版 Omnipose 路线使用，未获得独立商业授权 | **当前不可直接商用** | 同上；取得书面授权或迁移到权重许可明确、性能重新验证的替代版本 |
| MicroSAM DeepBacs Specialist | microSAM：MIT；Segment Anything：Apache-2.0 | DeepBacs Specialist Zenodo 权重：CC BY 4.0 | **可以商用** | 保留 MIT/Apache-2.0 文本；对 DeepBacs 权重给出作者、名称、来源、CC BY 4.0 链接，并标明是否修改 |

### 逐模型证明地址

- **Cellpose-SAM `cpsam_v2`（可以商用）**：代码 [BSD-3-Clause LICENSE](https://github.com/MouseLand/cellpose/blob/main/LICENSE)；官方权重仓库 [BSD-3-Clause](https://huggingface.co/mouseland/cellpose-sam)；作者/HHMI 关于商业应用的沟通记录 [CellSeg licensing chapter](https://kemal.yaylali.uk/cellseg-v0-1-0-is-out/)。
- **Omnipose `bact_phase_omnitorch_0`（本次 1.1.4 不可直接商用）**：[Omnipose v1.1.4 NonCommercial License](https://github.com/kevinjohncutler/omnipose/blob/v1.1.4/LICENSE)。
- **Omnipose `bact_fluor_omnitorch_0`（本次 1.1.4 不可直接商用）**：[Omnipose v1.1.4 NonCommercial License](https://github.com/kevinjohncutler/omnipose/blob/v1.1.4/LICENSE)；当前主分支 [MIT License](https://github.com/kevinjohncutler/omnipose/blob/main/LICENSE) 不追溯旧版权重。
- **MicroSAM DeepBacs Specialist（可以商用）**：microSAM [MIT LICENSE](https://github.com/computational-cell-analytics/micro-sam/blob/main/LICENSE)；Segment Anything [Apache-2.0 LICENSE](https://github.com/facebookresearch/segment-anything/blob/main/LICENSE)；DeepBacs Specialist 权重 [Zenodo CC BY 4.0](https://zenodo.org/records/11115827)。

### 7.1 Cellpose-SAM：训练数据是 CC-BY-NC，但 `cpsam_v2` 权重可商用

Cellpose 源代码采用 [BSD-3-Clause](https://github.com/MouseLand/cellpose/blob/main/LICENSE)，允许使用、修改、二进制分发和商业集成，条件是保留版权声明、许可证条款和免责声明，且未经书面许可不得用 HHMI 或贡献者名称为产品背书。更关键的是，官方 [Cellpose-SAM Hugging Face 模型仓库](https://huggingface.co/mouseland/cellpose-sam)本身也明确标注 `BSD-3-Clause`，这直接覆盖本次 `cpsam_v2` 权重的公开分发许可。

容易误读的是 Cellpose README 中“All Cellpose models are trained on data that is licensed under CC-BY-NC”的提醒。这里描述的是**训练数据的来源和许可**，并不是把 Cellpose-SAM 权重宣布为 NonCommercial。image.sc 的[许可讨论帖](https://forum.image.sc/t/question-about-cellpose-sam-pretrained-model-licensing-in-commercial-bioimage-software/121128/6)最初正是围绕这一点产生疑问。随后，一个实际进行 Cellpose 商业/开源集成的开发者记录了与 Cellpose 作者 Marius Pachitariu 以及 HHMI Janelia Director of Innovations & Open Science Mike Perham 的沟通：[CellSeg v0.1.0 licensing chapter](https://kemal.yaylali.uk/cellseg-v0-1-0-is-out/)。该记录给出的澄清是：上游 Cellpose-SAM/SAM 权重许可链允许 commercial applications；CC-BY-NC 提醒针对用于再训练的图像和标注数据，并不会自动传递到训练后的模型权重。

因此，本报告对 `cpsam_v2` 的结论是：**可以集成进收费、闭源或其他商业显微图像软件，也可以在商业服务中运行**。但不要把这个结论扩展为“Cellpose 训练数据也可商用”：若复制、再分发或直接使用 Cellpose annotated dataset 进行商业训练，仍必须遵守数据自身的 CC-BY-NC 等条款。早期 Cellpose 2 文档曾明确把部分 `tissuenet` / `livecell` 模型写为 non-commercial use only，这种明确的模型限制与当前“trained on CC-BY-NC data”的来源说明不是同一种表述，也不应混用。

### 7.2 Omnipose：本次 1.1.4 和旧权重不能直接用于商业产品

本次环境实际安装的是 Omnipose 1.1.4。其随安装包提供的 LICENSE 与 [v1.1.4 官方许可证](https://github.com/kevinjohncutler/omnipose/blob/v1.1.4/LICENSE)一致，名称为 **Omnipose NonCommercial License**，明确限定只能用于非商业目的，并要求商业使用权联系 University of Washington CoMotion（`license@uw.edu`）。因此，本次测试的 `bact_phase_omnitorch_0` 和 `bact_fluor_omnitorch_0` 不能仅凭开源仓库可访问就直接装入商业产品。

Omnipose 当前主分支后来改为 [MIT License](https://github.com/kevinjohncutler/omnipose/blob/main/LICENSE)，但许可证变更具有版本和对象边界：不能自动证明 1.1.4 二进制、历史代码及本次两个旧预训练权重已经被追溯重许可。若要商用，有三条稳妥路线：取得 UW CoMotion 对当前版本/权重的书面商业授权；向维护者确认新 MIT 版本及对应预训练权重的明确许可后迁移并重新验证性能；或者改用许可链明确的自训练/替代模型。

### 7.3 MicroSAM DeepBacs：允许商用，重点是署名和许可证传递

microSAM 代码采用 [MIT License](https://github.com/computational-cell-analytics/micro-sam/blob/main/LICENSE)，其上游 Meta Segment Anything 代码/基础权重采用 Apache-2.0。本次使用的 `vit_l.pt` 与 `vit_l_decoder.pt` 来自 [Zenodo：MicroSAM-DeepBacs-LM-Specialist](https://zenodo.org/records/11115827)，该记录明确标注 **CC BY 4.0**。这三种许可证都允许商业使用和分发，因此 MicroSAM DeepBacs 可以进入商业软件或商业推理服务。

合规重点是：随产品保留 MIT 和 Apache-2.0 许可证/NOTICE 要求；在文档或 Third-Party Notices 中写明 DeepBacs Specialist 的作者（Anwai Archit、Constantin Pape）、模型名称、Zenodo DOI `10.5281/zenodo.11115827`、CC BY 4.0 链接，并说明是否对权重或模型格式做过修改。论文引用是科研规范，许可证署名则是分发合规义务，两者最好同时保留。

### 7.4 建议的商业交付清单

正式产品应维护一份 Third-Party Software / Model Notices，至少包含：

1. 精确的软件版本、权重文件名、下载地址、校验哈希和获取日期。
2. Cellpose BSD-3-Clause、Cellpose-SAM 模型仓库 BSD-3-Clause及 Segment Anything Apache-2.0 文本。
3. microSAM MIT、Segment Anything Apache-2.0、DeepBacs Specialist CC BY 4.0 的署名和许可证链接。
4. Omnipose 1.1.4 的 NonCommercial License，以及商业授权文件或“未进入商业发行包”的隔离说明。
5. 明确区分“仅在服务器内部运行”“随安装包分发权重”“允许用户动态下载”“重新训练并分发新权重”等部署方式；不同方式的复制和分发义务可能不同。
6. 在产品发布前由公司法务复核模型权重、训练数据、依赖库、商标/署名和医疗或科研用途免责声明。

## 参考资料

- [Cellpose 官方仓库](https://github.com/MouseLand/cellpose)
- [Cellpose BSD-3-Clause LICENSE](https://github.com/MouseLand/cellpose/blob/main/LICENSE)；[Cellpose-SAM 官方模型仓库（BSD-3-Clause）](https://huggingface.co/mouseland/cellpose-sam)；[Cellpose-SAM 商用许可沟通记录](https://kemal.yaylali.uk/cellseg-v0-1-0-is-out/)
- [Omnipose 官方仓库](https://github.com/kevinjohncutler/omnipose)；[Omnipose 论文](https://www.nature.com/articles/s41592-022-01639-4)
- [Omnipose v1.1.4 NonCommercial License](https://github.com/kevinjohncutler/omnipose/blob/v1.1.4/LICENSE)；[Omnipose 当前主分支 MIT License](https://github.com/kevinjohncutler/omnipose/blob/main/LICENSE)
- [microSAM 官方仓库](https://github.com/computational-cell-analytics/micro-sam)；[microSAM 论文](https://www.nature.com/articles/s41592-024-02580-4)
- [microSAM MIT License](https://github.com/computational-cell-analytics/micro-sam/blob/main/LICENSE)；[MicroSAM DeepBacs Specialist 权重与 CC BY 4.0](https://zenodo.org/records/11115827)
- [Panoptic Segmentation / PQ](https://arxiv.org/abs/1801.00868)
- [clDice：拓扑保持分割指标](https://arxiv.org/abs/2003.07311)
