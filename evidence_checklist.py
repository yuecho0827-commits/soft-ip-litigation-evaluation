"""
商标权标准取证清单 —— 固化数据（任务 #1 产物）

作为 LLM 盘点证据的 prompt 输入。LLM 对照本清单，逐项判断用户证据
「充足 / 不足 / 缺失」，并输出理由。

- 案由：商标侵权（Soft IP）
- 最小单元：构成要件
- 法律依据：北大法宝检索核验，均现行有效（商标法为 2019 修正版），已走防幻觉验证。
- 三案由（商标、著作权、不正当竞争）清单均已固化到本模块。
"""
from typing import List, Dict

# 五大证据类别（顺序即盘点顺序）
CATEGORIES = ['权利基础证据', '侵权认定证据', '损害赔偿证据', '抗辩应对证据', '取证技术规范']

# 商标法（2019 修正）北大法宝链接
_TRADEMARK_LAW_URL = 'https://pkulaw.com/chl/937235cafaf2a66fbdfb.html'
# 法释〔2020〕19号 商标民事纠纷司法解释 链接
_TRADEMARK_INTERPRETATION_URL = 'https://pkulaw.com/chl/f0888a28b6f170dabdfb.html'
# 法释〔2020〕12号 知产证据规定 链接
_IP_EVIDENCE_RULE_URL = 'https://pkulaw.com/chl/61b460a9dc465f70bdfb.html'
# 民诉证据规定（2019 修正）链接
_CIVIL_EVIDENCE_RULE_URL = 'https://pkulaw.com/chl/e2cef8c231095c1bbdfb.html'
# 著作权法（2020 修正）北大法宝链接
_COPYRIGHT_LAW_URL = 'https://pkulaw.com/chl/a3b3a54bea64f090bdfb.html'
# 著作权民事纠纷司法解释（2020 修正）链接
_COPYRIGHT_INTERPRETATION_URL = 'https://pkulaw.com/chl/015c74c9e3b16325bdfb.html'
# 反不正当竞争法（2025 修订）北大法宝链接
_ANTI_UNFAIR_COMPETITION_LAW_URL = 'https://pkulaw.com/chl/1d79285621ad7295bdfb.html'
# 反不正当竞争法司法解释（法释〔2022〕9号）链接
_ANTI_UNFAIR_COMPETITION_INTERPRETATION_URL = 'https://pkulaw.com/chl/a9b0263acdb137fabdfb.html'


def _basis(law: str, article: str, url: str) -> Dict:
    """构建单项法律依据"""
    return {'law': law, 'article': article, 'url': url}


# 商标权取证清单（11 项）
TRADEMARK_EVIDENCE_CHECKLIST: List[Dict] = [
    {
        'category': '权利基础证据',
        'element': '商标权有效',
        'standard_evidence': '商标注册证、续展证明、商标转让核准证明',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第三十九条', _TRADEMARK_LAW_URL),
            _basis('中华人民共和国商标法(2019修正)', '第四十条', _TRADEMARK_LAW_URL),
        ],
        'impact_if_missing': 'block',
        'check_points': [
            '注册号是否清晰可查',
            '有效期是否届满、是否已续展、是否仍在宽展期',
            '注册人是否与原告一致（不一致需有转让/变更证明）',
            '核定商品/服务类别是否覆盖被诉侵权商品',
        ],
    },
    {
        'category': '权利基础证据',
        'element': '商标实际使用（防撤三）',
        'standard_evidence': '近三年使用证据（销售合同、发票、广告宣传、参展记录、电商销售链接、媒体报道）',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第四十九条', _TRADEMARK_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '使用时间是否落在近三年内',
            '使用主体是否为注册人本人或经许可的被许可人（须有许可证明）',
            '是否为真实商业使用（实际销售/广告/展览，而非象征性使用）',
            '是否使用在核定的商品/服务上',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '被告构成商标性使用',
        'standard_evidence': '被告使用标识的网页/商品截图、购买取证的实物、店铺门头/包装照片',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第五十七条', _TRADEMARK_LAW_URL),
        ],
        'impact_if_missing': 'block',
        'check_points': [
            '标识是否被突出、显著地使用',
            '是否起到区分商品/服务来源的作用',
            '是否属于描述性使用而落入正当使用（商标法第59条）',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '商品/服务相同或类似',
        'standard_evidence': '双方商品/服务比对材料（类目、用途、渠道、消费对象、实物对照）',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第五十七条', _TRADEMARK_LAW_URL),
            _basis('最高人民法院关于审理商标民事纠纷案件适用法律若干问题的解释(2020修正)', '第十一条', _TRADEMARK_INTERPRETATION_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '是否属于同一种商品/服务',
            '功能、用途、生产部门、销售渠道、消费对象是否相同或类似',
            '相关公众是否一般认为存在特定联系、容易混淆',
            '可参考《类似商品和服务区分表》',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '商标相同或近似',
        'standard_evidence': '双方商标图样比对材料（文字、图形、组合的整体对比图）',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第五十七条', _TRADEMARK_LAW_URL),
            _basis('最高人民法院关于审理商标民事纠纷案件适用法律若干问题的解释(2020修正)', '第九条', _TRADEMARK_INTERPRETATION_URL),
            _basis('最高人民法院关于审理商标民事纠纷案件适用法律若干问题的解释(2020修正)', '第十条', _TRADEMARK_INTERPRETATION_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '以相关公众的一般注意力为标准',
            '整体比对 + 主要部分比对（隔离状态下分别进行）',
            '文字（字形/读音/含义）、图形（构图/颜色）、组合结构、立体形状、颜色组合的近似程度',
            '考虑请求保护商标的显著性和知名度',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '混淆可能性',
        'standard_evidence': '消费者实际混淆证据、市场调查报告、相关公众认知材料',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第五十七条', _TRADEMARK_LAW_URL),
            _basis('最高人民法院关于审理商标民事纠纷案件适用法律若干问题的解释(2020修正)', '第九条', _TRADEMARK_INTERPRETATION_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '相关公众的注意程度',
            '商标的显著性和知名度',
            '有无实际混淆实例（消费者投诉、误购记录）',
            '侵权人的主观意图',
        ],
    },
    {
        'category': '损害赔偿证据',
        'element': '判赔计算依据',
        'standard_evidence': '被告销售数据/账簿、原告损失证明、许可费合同、侵权规模（销量/评价数/店铺数）',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第六十三条', _TRADEMARK_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '实际损失（销量减少、利润损失的直接证据）',
            '侵权获利（被告销量×单价×利润率）',
            '许可费倍数（有无商标许可合同可参照）',
            '举证救济（可申请法院责令被告提交账簿，第63条第2款）',
        ],
    },
    {
        'category': '损害赔偿证据',
        'element': '惩罚性赔偿依据（如主张）',
        'standard_evidence': '侵权故意证据、情节严重证据（重复侵权、规模大、后果严重）',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第六十三条', _TRADEMARK_LAW_URL),
        ],
        'impact_if_missing': 'optional',
        'check_points': [
            '恶意（明知故犯、曾受警告函/行政处罚、重复侵权）',
            '情节严重（侵权规模、持续时间、造成的后果）',
        ],
    },
    {
        'category': '抗辩应对证据',
        'element': '三年使用证据（应对未使用抗辩）',
        'standard_evidence': '近三年真实使用证据（与防撤三证据共用一套材料）',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第六十四条', _TRADEMARK_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '近三年内真实使用',
            '因侵权受到损失的证明',
        ],
    },
    {
        'category': '抗辩应对证据',
        'element': '被告主观明知证据（应对合法来源抗辩）',
        'standard_evidence': '权利人警告函、被告曾接触品牌、行业知名度材料等"明知"证据',
        'legal_basis': [
            _basis('中华人民共和国商标法(2019修正)', '第六十四条', _TRADEMARK_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '被告能否证明其主观"不知道"',
            '被告能否说明合法来源（供货商、进货渠道）',
            '我方"明知"证据（警告函、既往交涉、品牌知名度）',
        ],
    },
    {
        'category': '取证技术规范',
        'element': '证据固定方式',
        'standard_evidence': '公证取证、可信时间戳、区块链存证、第三方平台存证（IP360 等）',
        'legal_basis': [
            _basis('最高人民法院关于知识产权民事诉讼证据的若干规定', '法释〔2020〕12号', _IP_EVIDENCE_RULE_URL),
            _basis('最高人民法院关于民事诉讼证据的若干规定(2019修正)', '第九十四条', _CIVIL_EVIDENCE_RULE_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '线上侵权 → 可信时间戳/区块链存证/IP360 等第三方存证',
            '线下侵权 → 公证购买/公证取证',
            '电子数据真实性（是否由中立第三方平台提供或确认、是否公证）',
        ],
    },
]


# 著作权取证清单（10 项）
COPYRIGHT_EVIDENCE_CHECKLIST: List[Dict] = [
    {
        'category': '权利基础证据',
        'element': '著作权权属',
        'standard_evidence': '创作底稿/原件、著作权登记证书、合法出版物、取得权利的合同、认证机构出具的证明',
        'legal_basis': [
            _basis('中华人民共和国著作权法(2020修正)', '第三条', _COPYRIGHT_LAW_URL),
            _basis('中华人民共和国著作权法(2020修正)', '第十一条', _COPYRIGHT_LAW_URL),
            _basis('中华人民共和国著作权法(2020修正)', '第十二条', _COPYRIGHT_LAW_URL),
            _basis('最高人民法院关于审理著作权民事纠纷案件适用法律若干问题的解释(2020修正)', '第七条', _COPYRIGHT_INTERPRETATION_URL),
        ],
        'impact_if_missing': 'block',
        'check_points': [
            '独创性（是否具备独创性的智力成果，非公有领域/通用表达）',
            '署名（作品上署名是否指向我方；署名推定权属，但有相反证明除外）',
            '登记证书（是否已办理作品登记，登记时间）',
            '权利链条（职务作品/委托创作/转让，是否有相应合同或证明）',
        ],
    },
    {
        'category': '权利基础证据',
        'element': '作品已发表/公开',
        'standard_evidence': '首次发表记录、发表时间证明、公开传播范围（出版、上线、发布）',
        'legal_basis': [
            _basis('中华人民共和国著作权法(2020修正)', '第十二条', _COPYRIGHT_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '发表时间是否早于被告使用时间',
            '公开传播范围（是否已广泛传播，可据此推定被告接触）',
            '首次发表的载体与留痕',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '被告接触作品（接触要件）',
        'standard_evidence': '被告曾接触作品的证据（投稿记录、合作往来、作品已公开发表广泛传播、访问/下载记录）',
        'legal_basis': [
            _basis('中华人民共和国著作权法(2020修正)', '第五十二条', _COPYRIGHT_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '作品已公开发表且广泛传播 → 可推定接触',
            '特殊接触渠道（投稿、合作、雇佣关系）→ 需直接证据',
            '被告是否具备接触作品的时间与条件',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '实质性相似',
        'standard_evidence': '作品比对材料（文字/图像/音视频的相似性比对、鉴定报告、逐段对比）',
        'legal_basis': [
            _basis('中华人民共和国著作权法(2020修正)', '第五十二条', _COPYRIGHT_LAW_URL),
        ],
        'impact_if_missing': 'block',
        'check_points': [
            '是否在"表达"层面实质性相似（思想、公有领域元素应排除）',
            '独创性部分的相似程度（非独创部分相似不构成侵权）',
            '相似的比例、篇幅、关键情节/结构/代码的对应程度',
            '可借助专业鉴定（文字查重、音视频比对）',
            '软件作品：源代码/目标代码、界面、功能、权利管理信息、设计缺陷、冗余设计等特有信息的比对（源代码比对并非侵权判断的必备环节）',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '非合理使用（应对合理使用抗辩）',
        'standard_evidence': '证明被告使用不属于合理使用（商业性使用、超出引用限度、未指明作者/作品名）',
        'legal_basis': [
            _basis('中华人民共和国著作权法(2020修正)', '第二十四条', _COPYRIGHT_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '是否商业性使用（营利目的）',
            '是否"适当引用"（引用数量与比例是否超出必要）',
            '是否影响作品正常使用、不合理损害权利人合法权益',
            '是否指明作者姓名/作品名称',
        ],
    },
    {
        'category': '损害赔偿证据',
        'element': '判赔计算依据',
        'standard_evidence': '被告违法所得、原告实际损失、权利使用费、侵权规模（销量/传播量/下载量）',
        'legal_basis': [
            _basis('中华人民共和国著作权法(2020修正)', '第五十四条', _COPYRIGHT_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '实际损失（作品销量减少、许可费损失）',
            '违法所得（被告因侵权获利，销量×单价×利润率）',
            '权利使用费（有无许可合同可参照）',
            '举证救济（可申请法院责令被告提交账簿，第54条第4款）',
        ],
    },
    {
        'category': '损害赔偿证据',
        'element': '惩罚性赔偿依据（如主张）',
        'standard_evidence': '侵权故意证据、情节严重证据（重复侵权、规模大、后果严重）',
        'legal_basis': [
            _basis('中华人民共和国著作权法(2020修正)', '第五十四条', _COPYRIGHT_LAW_URL),
        ],
        'impact_if_missing': 'optional',
        'check_points': [
            '故意（明知故犯、曾受警告/通知、重复侵权）',
            '情节严重（侵权规模、持续时间、造成后果）',
        ],
    },
    {
        'category': '抗辩应对证据',
        'element': '独创性证据（应对无独创性抗辩）',
        'standard_evidence': '创作过程留痕、创作独特性说明、与其他作品的差异对比',
        'legal_basis': [
            _basis('中华人民共和国著作权法(2020修正)', '第三条', _COPYRIGHT_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '创作过程的独立性与独特性留痕（底稿、版本记录、时间戳）',
            '与其他在先作品的差异',
            '独创性表达的具体体现',
        ],
    },
    {
        'category': '抗辩应对证据',
        'element': '独立创作/合法来源应对',
        'standard_evidence': '被告无法提供独立创作证明、无合法授权的反证材料',
        'legal_basis': [
            _basis('中华人民共和国著作权法(2020修正)', '第五十二条', _COPYRIGHT_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '我方已初步证明"实质性相似 + 接触可能性"，举证责任可转移至被告',
            '被告是否主张"独立创作"或"合法授权"（需其举证）',
            '被告是否提供合法来源（授权合同、来源渠道）',
        ],
    },
    {
        'category': '取证技术规范',
        'element': '证据固定方式',
        'standard_evidence': '公证取证、可信时间戳、区块链存证、第三方平台存证（IP360 等）',
        'legal_basis': [
            _basis('最高人民法院关于知识产权民事诉讼证据的若干规定', '法释〔2020〕12号', _IP_EVIDENCE_RULE_URL),
            _basis('最高人民法院关于民事诉讼证据的若干规定(2019修正)', '第九十四条', _CIVIL_EVIDENCE_RULE_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '线上侵权 → 可信时间戳/区块链存证/IP360 等第三方存证',
            '线下侵权 → 公证购买/公证取证',
            '电子数据真实性（是否由中立第三方平台提供或确认、是否公证）',
        ],
    },
]


# 不正当竞争取证清单（9 项）
UNFAIR_COMPETITION_EVIDENCE_CHECKLIST: List[Dict] = [
    {
        'category': '权利基础证据',
        'element': '有一定影响的商业标识',
        'standard_evidence': '知名度证据（销售时间/区域/数额/对象、宣传持续时间/程度/地域、媒体报道、获奖记录、标识受保护情况）',
        'legal_basis': [
            _basis('中华人民共和国反不正当竞争法(2025修订)', '第七条', _ANTI_UNFAIR_COMPETITION_LAW_URL),
            _basis('最高人民法院关于适用《中华人民共和国反不正当竞争法》若干问题的解释', '第四条', _ANTI_UNFAIR_COMPETITION_INTERPRETATION_URL),
        ],
        'impact_if_missing': 'block',
        'check_points': [
            '市场知名度（是否具有一定的市场知名度）',
            '区别商品来源的显著特征（是否具备显著性）',
            '销售的时间、区域、数额和对象',
            '宣传的持续时间、程度和地域范围',
            '标识受保护情况',
        ],
    },
    {
        'category': '权利基础证据',
        'element': '商业秘密构成（如案由涉及商业秘密）',
        'standard_evidence': '保密措施证明（保密协议、保密制度、技术保护措施）、商业价值证明、不为公众所知悉的证明',
        'legal_basis': [
            _basis('中华人民共和国反不正当竞争法(2025修订)', '第十条', _ANTI_UNFAIR_COMPETITION_LAW_URL),
        ],
        'impact_if_missing': 'block',
        'check_points': [
            '秘密性（不为公众所知悉，非公知信息）',
            '价值性（具有商业价值）',
            '保密性（是否采取相应保密措施：保密协议、保密制度、权限管理、技术措施）',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '混淆行为（擅自使用相同或近似标识）',
        'standard_evidence': '被告使用相同/近似标识的证据（商品/包装/装潢/名称/域名/新媒体账号等）、消费者误认证据',
        'legal_basis': [
            _basis('中华人民共和国反不正当竞争法(2025修订)', '第七条', _ANTI_UNFAIR_COMPETITION_LAW_URL),
        ],
        'impact_if_missing': 'block',
        'check_points': [
            '标识是否相同或近似（商品名称、包装装潢、企业名称/字号、域名、网站名称、网页、新媒体账号名称、应用程序名称/图标等）',
            '是否"引人误认为是他人商品或者与他人存在特定联系"',
            '是否将他人注册商标/驰名商标作为字号使用、或设置为搜索关键词',
            '被告主观（是否明知、是否帮助他人实施混淆）',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '商业秘密侵权（如案由涉及商业秘密）',
        'standard_evidence': '被告不正当获取/披露/使用商业秘密的证据、第三人明知而获取的证据',
        'legal_basis': [
            _basis('中华人民共和国反不正当竞争法(2025修订)', '第十条', _ANTI_UNFAIR_COMPETITION_LAW_URL),
        ],
        'impact_if_missing': 'block',
        'check_points': [
            '是否以不正当手段获取（盗窃、贿赂、欺诈、胁迫、电子侵入）',
            '是否披露、使用或允许他人使用',
            '是否违反保密义务或保密要求',
            '第三人是否明知或应知仍获取、使用',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '商业诋毁（如涉及）',
        'standard_evidence': '被告编造、传播虚假信息或误导性信息的证据、损害商业信誉/商品声誉的证据',
        'legal_basis': [
            _basis('中华人民共和国反不正当竞争法(2025修订)', '第十二条', _ANTI_UNFAIR_COMPETITION_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '是否编造、传播或指使他人编造、传播虚假信息或误导性信息',
            '是否损害其他经营者的商业信誉、商品声誉',
            '传播范围与影响',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '虚假宣传（如涉及）',
        'standard_evidence': '被告作虚假或引人误解的商业宣传的证据（虚假描述、虚构交易/评价、误导性对比）',
        'legal_basis': [
            _basis('中华人民共和国反不正当竞争法(2025修订)', '第九条', _ANTI_UNFAIR_COMPETITION_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '是否对商品性能、功能、质量、销售状况、用户评价、曾获荣誉等作虚假或引人误解的宣传',
            '是否通过组织虚假交易、虚假评价等方式帮助他人虚假宣传',
            '是否欺骗、误导消费者和其他经营者',
        ],
    },
    {
        'category': '侵权认定证据',
        'element': '网络不正当竞争（互联网专条，如涉及）',
        'standard_evidence': '被告妨碍/破坏网络产品服务的证据（插入链接、强制跳转、误导卸载、恶意不兼容、不正当获取数据、滥用平台规则）',
        'legal_basis': [
            _basis('中华人民共和国反不正当竞争法(2025修订)', '第十三条', _ANTI_UNFAIR_COMPETITION_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '是否妨碍、破坏其他经营者网络产品/服务正常运行（插入链接、强制跳转、误导修改/关闭/卸载、恶意不兼容）',
            '是否以不正当方式获取、使用其他经营者合法持有的数据',
            '是否滥用平台规则（虚假交易、虚假评价、恶意退货）',
        ],
    },
    {
        'category': '损害赔偿证据',
        'element': '判赔计算依据',
        'standard_evidence': '原告实际损失、被告侵权获利、合理开支凭证、侵权规模',
        'legal_basis': [
            _basis('中华人民共和国反不正当竞争法(2025修订)', '第二十二条', _ANTI_UNFAIR_COMPETITION_LAW_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '实际损失（因侵权受到的实际损失）',
            '侵权获利（侵权人因侵权获得的利益）',
            '合理开支（制止侵权行为的开支）',
            '混淆/互联网专条可适用法定赔偿 500 万以下；商业秘密故意侵权可主张 1-5 倍',
        ],
    },
    {
        'category': '取证技术规范',
        'element': '证据固定方式',
        'standard_evidence': '公证取证、可信时间戳、区块链存证、第三方平台存证（IP360 等）',
        'legal_basis': [
            _basis('最高人民法院关于知识产权民事诉讼证据的若干规定', '法释〔2020〕12号', _IP_EVIDENCE_RULE_URL),
            _basis('最高人民法院关于民事诉讼证据的若干规定(2019修正)', '第九十四条', _CIVIL_EVIDENCE_RULE_URL),
        ],
        'impact_if_missing': 'warning',
        'check_points': [
            '线上侵权 → 可信时间戳/区块链存证/IP360 等第三方存证',
            '线下侵权 → 公证购买/公证取证',
            '电子数据真实性（是否由中立第三方平台提供或确认、是否公证）',
        ],
    },
]


def render_checklist_prompt(checklist: List[Dict] = None) -> str:
    """
    把取证清单渲染成 LLM 盘点证据的 prompt 文本。

    供 evaluate_evidence_readiness 等评估函数注入 prompt 使用。
    """
    items = checklist if checklist is not None else TRADEMARK_EVIDENCE_CHECKLIST
    lines = []
    for idx, item in enumerate(items, 1):
        lines.append('【{}】{}'.format(idx, item['element']))
        lines.append('标准证据：{}'.format(item['standard_evidence']))
        basis = '；'.join(['《{}》{}'.format(b['law'], b['article']) for b in item['legal_basis']])
        lines.append('法律依据：{}'.format(basis))
        lines.append('缺失影响：{}'.format(item['impact_if_missing']))
        lines.append('判断要点：{}'.format('；'.join(item['check_points'])))
        lines.append('')
    return '\n'.join(lines)
