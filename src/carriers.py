# -*- coding: utf-8 -*-
"""
船公司映射表：飞驼官方文档"业务覆盖范围-100+船司"中全部 113 家船司。

为什么要这张表？
  用户日常填写的"船司英文简称" ≠ 飞驼接口认识的"API传参代码"。
  例如：APL 简称的船，接口要传 CMA；ACI 要传 MSK；MEL 要传 MARIANA。
  所以这里内置一张对照表，程序根据简称自动翻译成接口要的代码。

字段说明（每个船司一个字典）：
  name_cn    中文名
  scac       SCAC 代码（国际船司代码，仅作展示）
  api_code   调用飞驼接口时实际要传的 carrierCode
  booking    是否支持订舱号(BK)查询：True=支持
  bl         是否支持提单号(BL)查询：True=支持
  container  是否支持箱号查询：True=支持
  note       备注（特殊要求，比如必须"提单号+箱号+POL+POD"）
"""

CARRIERS = {
    "ACI": {"name_cn": "亚利安莎", "scac": "ACIC", "api_code": "MSK", "booking": True, "bl": True, "container": True, "note": ""},
    "ALX": {"name_cn": "阿拉丁", "scac": "ALXU", "api_code": "ALX", "booking": True, "bl": True, "container": True, "note": ""},
    "ANL": {"name_cn": "澳航", "scac": "ANNU", "api_code": "ANL", "booking": True, "bl": True, "container": True, "note": ""},
    "APL": {"name_cn": "美国总统", "scac": "APLU", "api_code": "CMA", "booking": True, "bl": True, "container": True, "note": "简称APL，接口传CMA"},
    "ARKAS": {"name_cn": "阿尔卡斯", "scac": "ARKU", "api_code": "ARKAS", "booking": True, "bl": True, "container": True, "note": ""},
    "ASL": {"name_cn": "亚海", "scac": "ASLU", "api_code": "ASL", "booking": True, "bl": True, "container": True, "note": ""},
    "CCN": {"name_cn": "智利航运", "scac": "CCNR", "api_code": "MSK", "booking": True, "bl": True, "container": True, "note": "简称CCN，接口传MSK"},
    "CKL": {"name_cn": "天敬", "scac": "CKLC", "api_code": "CKL", "booking": True, "bl": True, "container": False, "note": ""},
    "CMA": {"name_cn": "达飞", "scac": "CMDU", "api_code": "CMA", "booking": True, "bl": True, "container": True, "note": ""},
    "CNC": {"name_cn": "正利", "scac": "CNCL", "api_code": "CNC", "booking": True, "bl": True, "container": True, "note": ""},
    "COSCO": {"name_cn": "中远", "scac": "COSU", "api_code": "COSCO", "booking": True, "bl": True, "container": True, "note": ""},
    "CROWLEY": {"name_cn": "克劳利海运", "scac": "CMCU", "api_code": "CROWLEY", "booking": True, "bl": True, "container": True, "note": ""},
    "CUL": {"name_cn": "中联", "scac": "CULU", "api_code": "CUL", "booking": True, "bl": True, "container": True, "note": ""},
    "DEL": {"name_cn": "达贸", "scac": "DELC", "api_code": "CMA", "booking": True, "bl": True, "container": True, "note": "简称DEL，接口传CMA"},
    "DJS": {"name_cn": "东进", "scac": "DJSL", "api_code": "DJS", "booking": True, "bl": True, "container": True, "note": ""},
    "DSV": {"name_cn": "得斯威", "scac": "DSVF", "api_code": "DSV", "booking": True, "bl": True, "container": True, "note": ""},
    "DYS": {"name_cn": "东映", "scac": "DYSL", "api_code": "DYS", "booking": False, "bl": True, "container": True, "note": ""},
    "EMC": {"name_cn": "长荣", "scac": "EGLV", "api_code": "EMC", "booking": True, "bl": True, "container": True, "note": ""},
    "ESL": {"name_cn": "阿联酋", "scac": "EMIV", "api_code": "ESL", "booking": True, "bl": True, "container": True, "note": ""},
    "FESCO": {"name_cn": "俄远东", "scac": "FESO", "api_code": "FESCO", "booking": True, "bl": True, "container": True, "note": ""},
    "FMS": {"name_cn": "富迈迅", "scac": "FMSU", "api_code": "FMS", "booking": True, "bl": True, "container": False, "note": ""},
    "GSL": {"name_cn": "金星", "scac": "GOSU", "api_code": "GSL", "booking": False, "bl": True, "container": True, "note": ""},
    "HAL": {"name_cn": "兴亚", "scac": "HALC", "api_code": "HAL", "booking": False, "bl": True, "container": True, "note": ""},
    "HAS": {"name_cn": "海华", "scac": "HASU", "api_code": "HASCO", "booking": False, "bl": True, "container": False, "note": "简称HAS，接口传HASCO"},
    "HBS": {"name_cn": "汉堡南美", "scac": "SUDU", "api_code": "MSK", "booking": True, "bl": True, "container": True, "note": "简称HBS，接口传MSK"},
    "HEDE": {"name_cn": "合德", "scac": "HDUJ", "api_code": "HEDE", "booking": False, "bl": True, "container": True, "note": ""},
    "HMM": {"name_cn": "现代", "scac": "HDMU", "api_code": "HMM", "booking": True, "bl": True, "container": True, "note": ""},
    "HPL": {"name_cn": "赫伯罗特", "scac": "HLCU", "api_code": "HPL", "booking": True, "bl": True, "container": True, "note": ""},
    "HSL": {"name_cn": "韩星", "scac": "HSLU", "api_code": "HSL", "booking": False, "bl": True, "container": True, "note": ""},
    "IAL": {"name_cn": "运达", "scac": "IALU", "api_code": "IAL", "booking": False, "bl": True, "container": True, "note": ""},
    "JIHANG": {"name_cn": "吉航", "scac": "JIHA", "api_code": "JIHANG", "booking": False, "bl": True, "container": True, "note": ""},
    "JINJIANG": {"name_cn": "锦江", "scac": "JINX", "api_code": "JINJIANG", "booking": False, "bl": True, "container": False, "note": ""},
    "KANWAY": {"name_cn": "建华", "scac": "UNKN", "api_code": "KANWAY", "booking": False, "bl": False, "container": True, "note": ""},
    "KKC": {"name_cn": "神原汽船", "scac": "KMBU", "api_code": "KKC", "booking": True, "bl": True, "container": True, "note": ""},
    "KMTC": {"name_cn": "高丽", "scac": "KMTC", "api_code": "KMTC", "booking": True, "bl": True, "container": True, "note": ""},
    "KN": {"name_cn": "德迅", "scac": "KHNN", "api_code": "KN", "booking": True, "bl": True, "container": True, "note": ""},
    "KWE": {"name_cn": "近铁", "scac": "KWEU", "api_code": "KWE", "booking": True, "bl": False, "container": False, "note": ""},
    "MATS": {"name_cn": "美森", "scac": "MATS", "api_code": "MATS", "booking": True, "bl": True, "container": True, "note": ""},
    "MCC": {"name_cn": "MCC", "scac": "MCPU", "api_code": "MSK", "booking": True, "bl": True, "container": True, "note": "简称MCC，接口传MSK"},
    "MEL": {"name_cn": "玛里亚那", "scac": "MELL", "api_code": "MARIANA", "booking": True, "bl": True, "container": True, "note": "简称MEL，接口传MARIANA"},
    "MSC": {"name_cn": "地中海", "scac": "MEDU", "api_code": "MSC", "booking": True, "bl": True, "container": True, "note": ""},
    "MSK": {"name_cn": "马士基", "scac": "MAEU", "api_code": "MSK", "booking": True, "bl": True, "container": True, "note": ""},
    "MSS": {"name_cn": "民生", "scac": "MSKM", "api_code": "MINSHENG", "booking": False, "bl": True, "container": True, "note": "简称MSS，接口传MINSHENG"},
    "NDS": {"name_cn": "尼罗河", "scac": "NDSU", "api_code": "HPL", "booking": True, "bl": True, "container": True, "note": "简称NDS，接口传HPL"},
    "NGP": {"name_cn": "太古船务", "scac": "NGPL", "api_code": "NGPL", "booking": True, "bl": True, "container": False, "note": ""},
    "NNL": {"name_cn": "新新航运", "scac": "NNSP", "api_code": "NNL", "booking": True, "bl": True, "container": True, "note": ""},
    "NOS": {"name_cn": "宁波远洋外贸", "scac": "NOSC", "api_code": "NOSCO", "booking": False, "bl": True, "container": False, "note": ""},
    "NSS": {"name_cn": "南星", "scac": "NSSC", "api_code": "NSS", "booking": False, "bl": True, "container": True, "note": ""},
    "NZL": {"name_cn": "新西兰", "scac": "NZLU", "api_code": "NZL", "booking": True, "bl": True, "container": True, "note": ""},
    "ONE": {"name_cn": "海洋网联", "scac": "ONEY", "api_code": "ONE", "booking": True, "bl": True, "container": True, "note": ""},
    "OOCL": {"name_cn": "东方海外", "scac": "OOLU", "api_code": "OOCL", "booking": True, "bl": True, "container": True, "note": ""},
    "OSL": {"name_cn": "海上丝路", "scac": "OSLU", "api_code": "OSL", "booking": True, "bl": True, "container": False, "note": ""},
    "OVP": {"name_cn": "海液通", "scac": "OVPB", "api_code": "OVP", "booking": False, "bl": True, "container": False, "note": ""},
    "PCL": {"name_cn": "泛洲", "scac": "PCLC", "api_code": "PCL", "booking": True, "bl": True, "container": True, "note": ""},
    "PES": {"name_cn": "山东远洋", "scac": "SMCU", "api_code": "PES", "booking": True, "bl": True, "container": True, "note": ""},
    "PIL": {"name_cn": "太平", "scac": "PABV", "api_code": "PIL", "booking": True, "bl": True, "container": True, "note": ""},
    "QNL": {"name_cn": "卡塔尔", "scac": "QNLU", "api_code": "QNL", "booking": True, "bl": True, "container": True, "note": ""},
    "RCL": {"name_cn": "宏海", "scac": "RCLC", "api_code": "RCL", "booking": True, "bl": True, "container": True, "note": ""},
    "SACO": {"name_cn": "中美合作", "scac": "SACO", "api_code": "SACO", "booking": True, "bl": True, "container": True, "note": ""},
    "SAF": {"name_cn": "萨非", "scac": "SEAU", "api_code": "MSK", "booking": True, "bl": True, "container": True, "note": "简称SAF，接口传MSK"},
    "SAMUDERA": {"name_cn": "萨姆达拉", "scac": "SIKU", "api_code": "SAMUDERA", "booking": False, "bl": True, "container": False, "note": ""},
    "SETH": {"name_cn": "狮富海运", "scac": "SSPH", "api_code": "SETH", "booking": True, "bl": True, "container": True, "note": ""},
    "SHIPCO": {"name_cn": "世舶科", "scac": "SHCO", "api_code": "SHIPCO", "booking": True, "bl": True, "container": False, "note": ""},
    "SIF": {"name_cn": "仁川", "scac": "SIMP", "api_code": "SIF", "booking": True, "bl": True, "container": True, "note": ""},
    "SINO": {"name_cn": "中外运", "scac": "SNTU", "api_code": "SINO", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号】一起传"},
    "SINOKOR": {"name_cn": "长锦", "scac": "SKMC", "api_code": "SINOKOR", "booking": False, "bl": True, "container": True, "note": ""},
    "SITC": {"name_cn": "海丰", "scac": "SITC", "api_code": "SITC", "booking": False, "bl": True, "container": True, "note": ""},
    "SLG": {"name_cn": "海杰航运", "scac": "SLGS", "api_code": "SLG", "booking": True, "bl": True, "container": True, "note": ""},
    "SML": {"name_cn": "森罗商船", "scac": "SMLM", "api_code": "SML", "booking": True, "bl": True, "container": True, "note": ""},
    "STX": {"name_cn": "世腾", "scac": "POBU", "api_code": "STX", "booking": True, "bl": True, "container": True, "note": ""},
    "TAR": {"name_cn": "塔罗斯", "scac": "GETU", "api_code": "TARROS", "booking": False, "bl": True, "container": True, "note": "简称TAR，接口传TARROS"},
    "TSH": {"name_cn": "泰赢", "scac": "TSHG", "api_code": "TAILWIND", "booking": True, "bl": True, "container": True, "note": "简称TSH，接口传TAILWIND"},
    "TSL": {"name_cn": "德翔", "scac": "TSYN", "api_code": "TSL", "booking": False, "bl": True, "container": True, "note": ""},
    "UGL": {"name_cn": "联合环球", "scac": "UGLU", "api_code": "UGL", "booking": True, "bl": True, "container": True, "note": ""},
    "UNIFEEDER": {"name_cn": "优尼菲尔德", "scac": "UNFR", "api_code": "UNIFEEDER", "booking": True, "bl": True, "container": True, "note": ""},
    "USL": {"name_cn": "美国轮船", "scac": "USLC", "api_code": "CMA", "booking": True, "bl": True, "container": True, "note": "简称USL，接口传CMA"},
    "WEC": {"name_cn": "荷兰航运", "scac": "WECL", "api_code": "WEC", "booking": True, "bl": True, "container": True, "note": ""},
    "WHL": {"name_cn": "万海", "scac": "WHLC", "api_code": "WHL", "booking": True, "bl": True, "container": True, "note": ""},
    "YML": {"name_cn": "阳明", "scac": "YMJA", "api_code": "YML", "booking": True, "bl": True, "container": True, "note": ""},
    "ZIM": {"name_cn": "以星", "scac": "ZIMU", "api_code": "ZIM", "booking": True, "bl": True, "container": True, "note": ""},
    "ZSH": {"name_cn": "中谷", "scac": "ZSHC", "api_code": "ZSH", "booking": False, "bl": True, "container": False, "note": "文档中外贸/内贸两条，接口传参均为ZSH，合并为一个"},
    "ATL": {"name_cn": "安通(内贸)", "scac": "ATLC", "api_code": "ATL", "booking": False, "bl": True, "container": False, "note": "内贸"},
    "EPANASIA": {"name_cn": "泛亚(内贸)", "scac": "COSU", "api_code": "COSCO", "booking": False, "bl": True, "container": True, "note": "内贸，简称EPANASIA，接口传COSCO"},
    "NOSCO": {"name_cn": "宁波远洋(内贸)", "scac": "NOSC", "api_code": "NOSCO", "booking": False, "bl": True, "container": False, "note": "内贸"},
    "TRAWIND": {"name_cn": "信风(内贸)", "scac": "TRAW", "api_code": "TRAWIND", "booking": False, "bl": True, "container": False, "note": "内贸，必须【提单号+箱号+POL+POD】"},
    "BEN": {"name_cn": "边航轮船", "scac": "BENU", "api_code": "BEN", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "BTL": {"name_cn": "孟虎航运", "scac": "BTLU", "api_code": "BTL", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "CCL": {"name_cn": "中通航运", "scac": "CCLU", "api_code": "CCL", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "COASTAL": {"name_cn": "宝华海运", "scac": "CSTU", "api_code": "COASTAL", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "EAS": {"name_cn": "达通", "scac": "EASC", "api_code": "EAS", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "FERRY": {"name_cn": "荣成华东", "scac": "FRYU", "api_code": "FERRY", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "FPMC": {"name_cn": "台塑航运", "scac": "FPMC", "api_code": "FPMC", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "GFS": {"name_cn": "格飞驰", "scac": "GFSU", "api_code": "GFS", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "HLD": {"name_cn": "海隆达", "scac": "HLDU", "api_code": "HLD", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "KAWA": {"name_cn": "嘉华航运", "scac": "KAWA", "api_code": "KAWA", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "KYOWA": {"name_cn": "协和海运", "scac": "KYWU", "api_code": "KYOWA", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "MHL": {"name_cn": "东方致远", "scac": "MHLU", "api_code": "MHL", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "PANDA": {"name_cn": "熊猫快线", "scac": "PADU", "api_code": "PANDA", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "PEAK": {"name_cn": "彼可航运", "scac": "PEAK", "api_code": "PEAK", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "SCO": {"name_cn": "兴联海", "scac": "SCOU", "api_code": "SCO", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "SLS": {"name_cn": "海领", "scac": "SJHH", "api_code": "SEALEAD", "booking": False, "bl": True, "container": True, "note": "简称SLS，接口传SEALEAD；必须【提单号+箱号+POL+POD】"},
    "SPS": {"name_cn": "美达船务", "scac": "SPSU", "api_code": "SPS", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "STAR": {"name_cn": "瑞洋海运", "scac": "STRU", "api_code": "STAR", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "TCL": {"name_cn": "太仓", "scac": "TCLC", "api_code": "TCLC", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "TRANSIT": {"name_cn": "特兰济特", "scac": "TSTL", "api_code": "TRANSIT", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "TYS": {"name_cn": "太荣航运", "scac": "TYSU", "api_code": "TYS", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "UWS": {"name_cn": "联丰船务", "scac": "UWSU", "api_code": "UWS", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "VOLTA": {"name_cn": "瓦尔塔", "scac": "VOLT", "api_code": "VOLTA", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "WEIDONG": {"name_cn": "威东航运", "scac": "WDGU", "api_code": "WEIDONG", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "WHDT": {"name_cn": "武汉大通", "scac": "WHDT", "api_code": "WHDT", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "XPRESS": {"name_cn": "X-Press", "scac": "XPRS", "api_code": "XPRESS", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
    "YCKY": {"name_cn": "优成凯运", "scac": "YCKY", "api_code": "YCKY", "booking": False, "bl": True, "container": True, "note": "必须【提单号+箱号+POL+POD】"},
}
# 共 113 条（文档中 ZSH 外贸/内贸两条合并为 1 条，其余 112 个简称 + 合并处理 = 113 家）

# 运单总状态（statusCategory）的中文说明（来源：节点状态码文档）
STATUS_CATEGORY_MAP = {
    "START": "订阅中（正在抓取数据）",
    "PROCESS": "跟踪进行中",
    "COMPLETE": "跟踪已结束",
    "NODATA": "船司无数据",
    "ABNORMAL": "异常（无数据或单号错误）",
}


def get_api_code(short_name):
    """根据用户填写的船司简称，返回飞驼接口要用的 carrierCode。

    参数：
        short_name: 船司简称（如 "MSC"、"APL"、"ACI"）
    返回：
        接口代码字符串；如果不认识这个简称，返回 None。
    """
    if not short_name:
        return None
    key = short_name.strip().upper()
    info = CARRIERS.get(key)
    return info["api_code"] if info else None


def get_carrier_info(short_name):
    """根据简称拿到该船司的完整信息。

    参数：
        short_name: 船司简称
    返回：
        该船司的字典；没找到返回 None。
    """
    if not short_name:
        return None
    return CARRIERS.get(short_name.strip().upper())


# SCAC 代码 → 船司简称 的反查索引（模块加载时建好，之后查找 O(1)）。
# 多维表格 Carrier 列存的可能不是简称而是 4 位 SCAC 码
# （如 MAEU=马士基、HLCU=赫伯罗特、EGLV=长荣、MSCU=MSC），
# 用这个索引可以把代码反查回简称。
_SCAC_INDEX = {}
for _short, _info in CARRIERS.items():
    _scac = (_info.get("scac") or "").strip().upper()
    if _scac and _scac not in _SCAC_INDEX:
        _SCAC_INDEX[_scac] = _short

# 标准行业 SCAC 码补充别名：多维表格 Carrier 列用的是"美国交通部标准 SCAC"，
# 而上面映射表里的 scac 个别与标准码不一致（如 MSC 记 MEDU、阳明记 YMJA），
# 这里按行业标准 SCAC 补齐确定的几条（拿不准的代码不配，走"无法获知船公司代码"）。
_SCAC_ALIASES = {
    "MSCU": "MSC",    # 地中海航运标准 SCAC（表里记的是 MEDU）
    "YMLU": "YML",    # 阳明海运标准 SCAC（表里记的是 YMJA）
    "CMAU": "CMA",    # 达飞标准 SCAC
    "APLU": "CMA",    # 达飞（原 APL）SCAC
    "COSU": "COSCO",  # 中远海运标准 SCAC
    "MSKU": "MSK",    # 马士基箱主代码
    "MRKU": "MSK",    # 马士基箱主代码
    "OOLU": "OOCL",   # 与映射表一致，双保险
}
_SCAC_INDEX.update(_SCAC_ALIASES)


def match_carrier_code(code):
    """把多维表格 Carrier 列里的代码匹配成船司简称（两级匹配）。

    匹配顺序（用户需求：Carrier 直接当船公司匹配即可）：
      ① 本来就是 113 家之一的简称（HPL/MSK/CMA/EMC...）→ 直接命中；
      ② 是 4 位 SCAC 码（MAEU/HLCU/EGLV/MSCU...）→ 用 scac 字段反查回简称；
      ③ 都不是 → 返回 None（调用方按"无法获知船公司代码"处理）。

    参数：
        code: 多维表格 Carrier 列的原始文本（可能带空格/小写）
    返回：
        船司简称（如 "MSK"）；匹配不到返回 None。
    """
    key = (code or "").strip().upper()
    if not key:
        return None
    if key in CARRIERS:                       # ① 简称直接命中
        return key
    return _SCAC_INDEX.get(key)               # ② SCAC 反查（查不到是 None）


def search_carriers(keyword):
    """按关键字模糊搜索船司（简称/中文名/SCAC/接口代码 任一命中即算）。

    参数：
        keyword: 搜索词（比如 "中远"、"COSCO"）
    返回：
        匹配到的 [简称, 中文名, 接口代码] 列表，按简称排序。
    """
    if not keyword:
        return []
    kw = keyword.strip().upper()
    results = []
    for short_name, info in CARRIERS.items():
        if (
            kw in short_name.upper()
            or kw in info.get("name_cn", "").upper()
            or kw in info.get("scac", "").upper()
            or kw in info.get("api_code", "").upper()
        ):
            results.append({"short_name": short_name, "name_cn": info["name_cn"], "api_code": info["api_code"]})
    return results


def translate_status(category):
    """把接口返回的 statusCategory 翻译成中文说明（方便业务同事看懂）。"""
    return STATUS_CATEGORY_MAP.get(str(category).upper(), str(category))
