# -*- coding: utf-8 -*-
"""
配置文件：项目参数集中管理。

【配置文件机制】
  程序不硬编码账号密码，通过 config.json 保存用户配置：
    · 启动时：优先读"注册表记忆的配置文件路径"，没有则读程序同目录 config.json
    · 保存时：如果已有配置文件 → 直接覆盖保存（不弹窗）；
              如果还没有 → 由界面弹出"保存文件"对话框，用户选位置创建 config.json，
              并把该路径记入注册表，下次启动自动读取。
  这样 exe 可以发给别人直接用：对方第一次运行填写账号密码并选择保存位置即可。

【Token 机制】
  Token 只存在内存里（每次启动第一次查询时自动用账号密码换取），
  不写入 config.json —— 用户不需要填、不需要看 Token。
"""
import json
import os
import sys
import time as _time

# ---------- 配置文件路径管理 ----------
# 源码运行时：main.py 在项目根目录，本文件在 src/ 下，所以上两级是项目根目录
# 打包成 exe 后：__file__ 指向 PyInstaller 解压的临时目录，必须改成 exe 所在目录
if getattr(sys, "frozen", False):          # 是否处于 PyInstaller 打包环境
    _ROOT_DIR = os.path.dirname(sys.executable)   # exe 所在目录
else:
    _ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_FILE = os.path.join(_ROOT_DIR, "config.json")   # 默认位置（exe 同目录）

# 注册表里记录"用户选择的配置文件路径"的键（Windows 记忆用）
_REG_KEY = r"Software\LogisticsQueryAssistant"
_REG_VALUE = "config_path"

# 默认配置（第一次运行没有 config.json 时的初始值；账号密码默认为空）
DEFAULT_CONFIG = {
    "freightower": {
        "client_id": "",        # 飞驼 API 账号（clientId，用于自动获取 token）
        "secret": "",           # 飞驼 API 密码（secret，用于自动获取 token）
    },
    "feishu": {                 # 飞书相关（多维表格读取/回写 + 群机器人通知）
        "app_id": "",           # 飞书自建应用的 App ID
        "app_secret": "",       # 飞书自建应用的 App Secret
        "table_link": "",       # 多维表格链接（程序自动解析出表格/数据表/视图 ID）
        "webhook_url": "",      # 群机器人 Webhook 地址（执行开始/完成通知）
        "webhook_secret": "",   # 群机器人签名校验密钥（机器人开了"签名校验"才需要填）
    },
}

# ============================================================
# 飞书字段映射默认值（33 项 = 32 个对接字段 + 对接状态）
# ============================================================
# 和"飞驼接口映射"同样的思路：多维表格以后改列名时不用改代码，
# 在配置页"飞书接口映射"子页里把"多维表格列名"改一下即可。
# 默认列名已按目标表格【BSQ】-在途跟踪表/数据表"飞驼对接"真实列名校对（2026-10-15）
DEFAULT_FEISHU_FIELD_MAPPING = [
    # ---------- 状态（1 项） ----------
    {"环节": "状态", "字段名称": "对接状态", "多维表格列名": "对接状态"},
    # ---------- 节点（2 项：查询页"最新节点/下一节点(预计)"同款口径） ----------
    {"环节": "节点", "字段名称": "当前节点", "多维表格列名": "当前节点"},
    {"环节": "节点", "字段名称": "下一节点", "多维表格列名": "下一节点"},
    # ---------- 起运港（16 项） ----------
    {"环节": "起运港", "字段名称": "截单时间", "多维表格列名": "截单时间"},
    {"环节": "起运港", "字段名称": "开港时间", "多维表格列名": "开港时间"},
    {"环节": "起运港", "字段名称": "截港时间", "多维表格列名": "截港时间"},
    {"环节": "起运港", "字段名称": "截关时间", "多维表格列名": "截关时间"},
    {"环节": "起运港", "字段名称": "提空时间", "多维表格列名": "提空时间"},
    {"环节": "起运港", "字段名称": "进港时间", "多维表格列名": "进港时间"},
    {"环节": "起运港", "字段名称": "海关状态", "多维表格列名": "海关状态"},
    {"环节": "起运港", "字段名称": "海关放行", "多维表格列名": "海关放行"},
    {"环节": "起运港", "字段名称": "海关滞留", "多维表格列名": "海关滞留"},
    {"环节": "起运港", "字段名称": "码头状态", "多维表格列名": "码头状态"},
    {"环节": "起运港", "字段名称": "码头放行", "多维表格列名": "码头放行"},
    {"环节": "起运港", "字段名称": "码头滞留", "多维表格列名": "码头滞留"},
    {"环节": "起运港", "字段名称": "装船时间", "多维表格列名": "装船时间"},
    {"环节": "起运港", "字段名称": "预计离港时间", "多维表格列名": "预计离港时间"},
    {"环节": "起运港", "字段名称": "实际离港时间", "多维表格列名": "实际离港时间"},
    {"环节": "起运港", "字段名称": "船名航次", "多维表格列名": "船名航次"},
    # ---------- 目的港（11 项） ----------
    {"环节": "目的港", "字段名称": "预计到港时间", "多维表格列名": "预计到港时间"},
    {"环节": "目的港", "字段名称": "实际到港时间", "多维表格列名": "实际到港时间"},
    {"环节": "目的港", "字段名称": "卸船时间", "多维表格列名": "卸船时间"},
    {"环节": "目的港", "字段名称": "可提重时间", "多维表格列名": "可提重时间"},
    {"环节": "目的港", "字段名称": "提重时间", "多维表格列名": "提重时间"},
    {"环节": "目的港", "字段名称": "还空时间", "多维表格列名": "还空时间"},
    {"环节": "目的港", "字段名称": "目的港查验", "多维表格列名": "目的港查验"},
    {"环节": "目的港", "字段名称": "目的港放行", "多维表格列名": "目的港放行"},
    {"环节": "目的港", "字段名称": "IPI实际发车时间", "多维表格列名": "IPI实际发车时间"},
    {"环节": "目的港", "字段名称": "IPI预计到达时间", "多维表格列名": "IPI预计到达时间"},
    {"环节": "目的港", "字段名称": "IPI实际到达时间", "多维表格列名": "IPI实际到达时间"},
    # ---------- 中转港（5 项，列名带"-中转"后缀） ----------
    {"环节": "中转港", "字段名称": "预计到港时间", "多维表格列名": "预计到港时间-中转"},
    {"环节": "中转港", "字段名称": "实际到港时间", "多维表格列名": "实际到港时间-中转"},
    {"环节": "中转港", "字段名称": "预计离港时间", "多维表格列名": "预计离港时间-中转"},
    {"环节": "中转港", "字段名称": "实际离港时间", "多维表格列名": "实际离港时间-中转"},
    {"环节": "中转港", "字段名称": "船名航次", "多维表格列名": "船名航次-中转"},
    # ---------- 尾程卡车（4 项：实际/预计各拆出发、到达） ----------
    {"环节": "尾程卡车", "字段名称": "卡车实际发出时间", "多维表格列名": "卡车实际发出时间"},
    {"环节": "尾程卡车", "字段名称": "卡车实际到达时间", "多维表格列名": "卡车实际到达时间"},
    {"环节": "尾程卡车", "字段名称": "卡车预计发出时间", "多维表格列名": "卡车预计发出时间"},
    {"环节": "尾程卡车", "字段名称": "卡车预计到达时间", "多维表格列名": "卡车预计到达时间"},
]

# ============================================================
# 字段映射默认值（36 个对接字段）
# ============================================================
# 每个字段固定：
#   环节      起运港/目的港/中转港/尾程卡车
#   字段名称  业务叫法（如"截单时间"）
#   英文描述  对接文档里的英文名（界面鼠标悬停显示）
#   取值来源  用"-"连接下层字段的取值路径，界面可修改，例如：
#             terminalplan-open                    港区计划里的 open 字段
#             places-type2-etd                     places 里 type=2 的 etd
#             containers-desc-进场-eventTime       status 里中文名=进场 的 eventTime
#             containers-code-PASS-eventTime       status 里事件码=PASS 的 eventTime
#             containers-exists-PASS-已放行         存在该事件码的节点就输出文案"已放行"（状态类字段用）
#             containers-code-first-GTOT-eventTime 全节点里【第一条】事件码=GTOT 的时间
#             containers-code-last-GTIN-eventTime  全节点里【最后一条】事件码=GTIN 的时间
#             containers-code-first-actual-GTOT-eventTime  尾程里第一条"实际"的 GTOT（卡车实际发出）
#             containers-code-last-actual-truck-FETA-eventTime  尾程里最后一条"实际"且运输方式=卡车的 FETA
#             containers-code-first-esti-GTOT-eventTime     尾程里第一条"预计"的 GTOT（卡车预计发出）
#             containers-code-last-esti-truck-FETA-eventTime      尾程里最后一条"预计"且运输方式=卡车的 FETA
#             containers-desc-contains-查验-eventTime  中文名"包含"查验 的 eventTime
#             places-type4-vessel/voyage           取 vessel 和 voyage 两个拼一起
DEFAULT_FIELD_MAPPING = [
    # ---------- 起运港（16 项） ----------
    {"环节": "起运港", "字段名称": "截单时间", "英文描述": "portClose", "取值来源": "terminalplan-portClose"},
    {"环节": "起运港", "字段名称": "开港时间", "英文描述": "open", "取值来源": "terminalplan-open"},
    {"环节": "起运港", "字段名称": "截港时间", "英文描述": "close", "取值来源": "terminalplan-close"},
    {"环节": "起运港", "字段名称": "截关时间", "英文描述": "customsClose", "取值来源": "terminalplan-customsClose"},
    {"环节": "起运港", "字段名称": "提空时间", "英文描述": "Pick-up Empty", "取值来源": "containers-desc-提空箱-eventTime"},
    {"环节": "起运港", "字段名称": "进港时间", "英文描述": "Received", "取值来源": "containers-desc-进场-eventTime"},
    {"环节": "起运港", "字段名称": "海关状态", "英文描述": "Customs Released", "取值来源": "containers-exists-PASS-已放行"},
    {"环节": "起运港", "字段名称": "海关放行", "英文描述": "Customs Released", "取值来源": "containers-desc-海关放行-eventTime"},
    {"环节": "起运港", "字段名称": "海关滞留", "英文描述": "Customs Released", "取值来源": "containers-code-CUIP-eventTime"},
    {"环节": "起运港", "字段名称": "码头状态", "英文描述": "Terminal Released", "取值来源": "containers-code-TMPS-eventTime"},
    {"环节": "起运港", "字段名称": "码头放行", "英文描述": "Terminal Released", "取值来源": "containers-desc-码头放行-eventTime"},
    {"环节": "起运港", "字段名称": "码头滞留", "英文描述": "Terminal Released", "取值来源": "containers-code-TMHD-eventTime"},
    {"环节": "起运港", "字段名称": "装船时间", "英文描述": "Loaded", "取值来源": "containers-desc-装船-eventTime"},
    {"环节": "起运港", "字段名称": "预计离港时间", "英文描述": "ETD", "取值来源": "places-type2-etd"},
    {"环节": "起运港", "字段名称": "实际离港时间", "英文描述": "ATD", "取值来源": "places-type2-atd"},
    {"环节": "起运港", "字段名称": "船名航次", "英文描述": "vessel/voyage", "取值来源": "places-type2-vessel/voyage"},
    # ---------- 目的港（11 项） ----------
    {"环节": "目的港", "字段名称": "预计到港时间", "英文描述": "ETA", "取值来源": "places-type4-eta"},
    {"环节": "目的港", "字段名称": "实际到港时间", "英文描述": "ATA", "取值来源": "places-type4-ata"},
    {"环节": "目的港", "字段名称": "卸船时间", "英文描述": "Vessel Discharged", "取值来源": "containers-desc-卸船-eventTime"},
    {"环节": "目的港", "字段名称": "可提重时间", "英文描述": "Available", "取值来源": "containers-code-PCAB-eventTime"},
    {"环节": "目的港", "字段名称": "提重时间", "英文描述": "Gate Out for Delivery", "取值来源": "containers-desc-提柜(货)-eventTime"},
    {"环节": "目的港", "字段名称": "还空时间", "英文描述": "Empty Returned", "取值来源": "containers-desc-还空箱-eventTime"},
    {"环节": "目的港", "字段名称": "目的港查验", "英文描述": "Inspection", "取值来源": "containers-desc-contains-查验-eventTime"},
    {"环节": "目的港", "字段名称": "目的港放行", "英文描述": "Destination Released", "取值来源": "containers-desc-contains-放行-eventTime"},
    # IPI（内陆联运）：有固定判断条件（type4与type5 code不一致 + transportMode_out=RAIL）
    {"环节": "目的港", "字段名称": "IPI实际发车时间", "英文描述": "IPI ATD", "取值来源": "places-type4-atd"},
    {"环节": "目的港", "字段名称": "IPI预计到达时间", "英文描述": "IPI ETA", "取值来源": "places-type5-eta"},
    {"环节": "目的港", "字段名称": "IPI实际到达时间", "英文描述": "IPI ATA", "取值来源": "places-type5-ata"},
    # ---------- 中转港（5 项） ----------
    {"环节": "中转港", "字段名称": "预计到港时间", "英文描述": "ETA", "取值来源": "places-type3-eta"},
    {"环节": "中转港", "字段名称": "实际到港时间", "英文描述": "ATA", "取值来源": "places-type3-ata"},
    {"环节": "中转港", "字段名称": "预计离港时间", "英文描述": "ETD", "取值来源": "places-type3-etd"},
    {"环节": "中转港", "字段名称": "实际离港时间", "英文描述": "ATD", "取值来源": "places-type3-atd"},
    {"环节": "中转港", "字段名称": "船名航次", "英文描述": "vessel/voyage", "取值来源": "places-type3-vessel/voyage"},
    # ---------- 尾程卡车（4 项：实际/预计各拆出发、到达） ----------
    # 只算尾程（装船之后的卡车节点；起运地提空箱/进场/内陆短驳会被自动排除）
    # 卡车实际发出时间：尾程里【第一条实际发生】的"卡车出场"（GTOT）
    # 卡车实际到达时间：尾程里【最后一条实际发生】且运输方式=卡车的"交货地抵达"（FETA）
    # 卡车预计发出时间：尾程里【第一条仍为预计】的"卡车出场"（GTOT），即下一次计划发车
    # 卡车预计到达时间：尾程里【最后一条仍为预计】且运输方式=卡车的"交货地抵达"（FETA）
    # 注：FETA 不专属卡车（交货地=目的港时它是船到港），用户口径 C = 只认运输方式=卡车的 FETA
    # 以上都只认"有时间"的节点，取不到即留空（该单没有卡车送达节点时到达两列留空）
    {"环节": "尾程卡车", "字段名称": "卡车实际发出时间", "英文描述": "Truck ATD", "取值来源": "containers-code-first-actual-GTOT-eventTime"},
    {"环节": "尾程卡车", "字段名称": "卡车实际到达时间", "英文描述": "Truck ATA", "取值来源": "containers-code-last-actual-truck-FETA-eventTime"},
    {"环节": "尾程卡车", "字段名称": "卡车预计发出时间", "英文描述": "Truck ETD", "取值来源": "containers-code-first-esti-GTOT-eventTime"},
    {"环节": "尾程卡车", "字段名称": "卡车预计到达时间", "英文描述": "Truck ETA", "取值来源": "containers-code-last-esti-truck-FETA-eventTime"},
]

# ============================================================
# 配置读写函数
# ============================================================

_loaded_config = None           # 内存中的配置，避免每次读文件
_loaded_config_file = None      # 当前生效的配置文件路径
_mem_token = ""                 # 内存里的 Token（不写盘）
_mem_token_fetched_at = 0.0     # 内存里 Token 的获取时间


def remember_config_path(path):
    """把用户选择的配置文件路径记到注册表（下次启动自动读这里）。"""
    if os.name != "nt":
        return
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_KEY)
        winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_SZ, str(path))
        winreg.CloseKey(key)
    except Exception:
        pass  # 记不住也不影响运行（下次用默认位置）


def _remembered_config_path():
    """读注册表里记忆的配置文件路径；没有记忆或文件没了返回空。"""
    if os.name != "nt":
        return ""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY)
        path, _ = winreg.QueryValueEx(key, _REG_VALUE)
        winreg.CloseKey(key)
        return str(path) if path and os.path.exists(path) else ""
    except Exception:
        return ""


def get_config_file():
    """当前生效的配置文件路径（优先注册表记忆，其次 exe 同目录）。"""
    global _loaded_config_file
    if _loaded_config_file:
        return _loaded_config_file
    path = _remembered_config_path()
    if not path:
        path = DEFAULT_CONFIG_FILE
    _loaded_config_file = path
    return path


def set_config_file(path):
    """设置当前配置文件路径（保存对话框选好位置后调用）。"""
    global _loaded_config_file
    _loaded_config_file = path
    remember_config_path(path)


def load_config():
    """读取配置。第一次会读配置文件；没有就返回默认配置。

    空值不再用环境变量兜底（Token 改为自动获取，账号密码都在配置文件里）。
    """
    global _loaded_config
    cfg = json.loads(deepcopy_json(DEFAULT_CONFIG))  # 复制一份默认值，避免互相影响

    path = get_config_file()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            _merge(cfg, saved)   # 把保存的配置逐层盖到默认配置上
            # 字段映射是独立数组，_merge 不处理，单独拿进来
            if isinstance(saved.get("field_mapping"), list) and saved["field_mapping"]:
                cfg["field_mapping"] = saved["field_mapping"]
            # 飞书字段映射同理（独立数组）
            if isinstance(saved.get("feishu_field_mapping"), list) and saved["feishu_field_mapping"]:
                cfg["feishu_field_mapping"] = saved["feishu_field_mapping"]
        except (json.JSONDecodeError, OSError):
            pass  # 配置文件损坏就当不存在

    _loaded_config = cfg
    return cfg


def get_field_mapping():
    """获取当前生效的字段映射（用户在配置页改过就用自己的，否则用内置默认）。"""
    cfg = get_config()
    m = cfg.get("field_mapping")
    if isinstance(m, list) and m:
        return _merge_mapping(m, DEFAULT_FIELD_MAPPING)
    return DEFAULT_FIELD_MAPPING


def get_feishu_field_mapping():
    """获取当前生效的飞书字段映射（多维表格列名映射，改过用用户的，否则用默认）。"""
    cfg = get_config()
    m = cfg.get("feishu_field_mapping")
    if isinstance(m, list) and m:
        return _merge_mapping(m, DEFAULT_FEISHU_FIELD_MAPPING)
    return DEFAULT_FEISHU_FIELD_MAPPING


# 历史废弃/改名的映射行：这些 (环节, 字段名称) 在旧版本存在，现在已改名或取消。
# 合并旧配置时要丢掉它们 —— 否则会拿着已不存在的多维表格列名去回写，
# 程序会直接报"多维表格里不存在列「xxx」"，整轮更新失败。
# 2026-10-16：多维表格把"卡车发出时间/卡车到达时间"改名为
#            "卡车实际发出时间/卡车实际到达时间"，并新增两个"预计"列，旧 2 行作废。
OBSOLETE_FIELD_ROWS = {
    ("尾程卡车", "卡车发出时间"),
    ("尾程卡车", "卡车到达时间"),
}


# 口径由程序统一维护的字段：这些字段的"取值来源"以最新默认值为准，
# 旧配置里存的旧表达式会被覆盖（其它字段仍保留用户自定义）。
# 原因：业务口径由程序定义，升级口径后不能因为配置文件里存着旧表达式而继续用旧口径。
# 2026-10-16：尾程卡车"到达"从 GTIN 卡车进场 改为 FETA 交货地抵达；
# 2026-10-17：起运港"海关状态"从"放行时间"改为"状态文案（已放行）"。
CODE_OWNED_FIELDS = {
    # 尾程卡车 4 项（口径由程序统一维护）
    ("尾程卡车", "卡车实际发出时间"),
    ("尾程卡车", "卡车实际到达时间"),
    ("尾程卡车", "卡车预计发出时间"),
    ("尾程卡车", "卡车预计到达时间"),
    # 海关状态：显示形式变更（时间 → 状态文案）
    ("起运港", "海关状态"),
}


def _merge_mapping(saved, default):
    """把用户保存的映射和最新默认映射合并（版本升级兼容）。

    场景：用户在旧版本保存过映射（写进了 config.json），后来程序升级
    在默认映射里新增了字段行 —— 如果直接用保存值，新行永远不会出现。
    合并规则（按 环节+字段名称 匹配）：
      · 用户配置里已有的行：原样保留（用户改过的"列名"等不丢）；
      · 默认映射里有、用户配置里没有的行：自动追加到末尾（新版本新增的字段）；
      · 属于 CODE_OWNED_FIELDS 的字段：其"取值来源"强制用最新默认值
        （旧配置里存的旧表达式会被覆盖，避免升级口径后旧口径继续生效）。
    """
    merged = [dict(x) for x in saved
              if (x.get("环节"), x.get("字段名称")) not in OBSOLETE_FIELD_ROWS]
    index = {(x.get("环节"), x.get("字段名称")): i for i, x in enumerate(merged)}
    for item in default:
        key = (item.get("环节"), item.get("字段名称"))
        if key not in index:
            merged.append(dict(item))
        elif key in CODE_OWNED_FIELDS and "取值来源" in item:
            # 口径由程序统一维护：覆盖旧配置里的旧表达式（如卡车到达由 GTIN 改成 FETA、
            # 海关状态由"放行时间"改成"已放行"文案）
            merged[index[key]]["取值来源"] = item["取值来源"]
    return merged


def save_config(new_cfg, path=None):
    """把新配置保存到配置文件（同时更新内存）。

    参数：
        new_cfg: 要保存的配置字典
        path:    保存到的路径；不传就用当前生效的配置文件路径
    """
    global _loaded_config
    if path:
        set_config_file(path)
    target = path or get_config_file()
    with open(target, "w", encoding="utf-8") as f:
        json.dump(new_cfg, f, ensure_ascii=False, indent=2)
    _loaded_config = new_cfg


def get_config():
    """拿到当前配置（内存优先）。"""
    return _loaded_config if _loaded_config is not None else load_config()


def get_freightower_credentials():
    """获取飞驼 API 账号和密码（用于自动换取 token）。

    返回：
        (client_id, secret) 两个字符串；没配置时都是空串。
    """
    cfg = get_config()["freightower"]
    return cfg.get("client_id", ""), cfg.get("secret", "")


# ============================================================
# Token 内存缓存（不写盘，程序运行期间有效）
# ============================================================

def get_freightower_token():
    """获取内存里的飞驼 Token（没有返回空串，查询前会自动换取）。"""
    return _mem_token


def save_freightower_token(token):
    """把新获取的 token 存进内存（并记录获取时间）。"""
    global _mem_token, _mem_token_fetched_at
    _mem_token = token
    _mem_token_fetched_at = _time.time()


def freightower_token_age():
    """内存里 token 是多久前获取的（秒）；没有获取记录返回 -1。"""
    if not _mem_token_fetched_at:
        return -1
    return int(_time.time() - _mem_token_fetched_at)


# ============================================================
# 工具函数
# ============================================================

def _merge(base, extra):
    """把 extra 里的值盖到 base 上（只处理两边都是 dict 的情况）。"""
    for k, v in (extra or {}).items():
        if k in base:
            if isinstance(base[k], dict) and isinstance(v, dict):
                _merge(base[k], v)
            else:
                base[k] = v


def deepcopy_json(obj):
    """简单深拷贝（配置里只有字符串，用 json 转一圈最省事）。"""
    return json.dumps(obj, ensure_ascii=False)


# ============================================================
# 固定参数（不随配置变化的常量）
# ============================================================

# 飞驼查询接口地址（见官方文档：集装箱综合跟踪）
FREIGHTOWER_API_URL = "http://openapi.freightower.com/application/v1/query"

# 飞驼获取 Token 接口地址（见官方文档：获取Token）
FREIGHTOWER_TOKEN_URL = "http://openapi.freightower.com/auth/api/token"

# Token 有效期：接口说明默认 24 小时，建议 12 小时获取一次。
# 这里取 12 小时，提前换新，避免刚好在查询时过期。
TOKEN_REFRESH_SECONDS = 12 * 3600

# 相邻两次查询之间的间隔秒数（飞驼接口限流，加个小停顿更安全）
REQUEST_INTERVAL = 0.8

# 单次请求超时时间（秒）：防止网络卡住一直等待
REQUEST_TIMEOUT = 30
