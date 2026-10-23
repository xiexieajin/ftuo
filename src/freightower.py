# -*- coding: utf-8 -*-
"""
飞驼查询模块：负责调用飞驼"集装箱综合跟踪"接口，并把返回结果整理成好用的数据。

对外提供两个函数：
  query_bill(...)     给一个单号查询，返回整理好的结果（概要 + 节点明细）
  format_result(...)  把结果格式化成人能读的文本（命令行测试用）

返回的结果结构（供 GUI 和"导入多维表格"复用）：
  {
    "success":   True/False             这次查询是否成功
    "message":   "成功/失败原因"         给人看的一句话
    "raw":       {...}                  飞驼返回的原始 JSON
    "summary":   {...}                  运单概要（总状态、最新节点、船名航次等）
    "nodes":     [ {...}, ... ]         每个节点一行（含箱号），用于表格展示
    "fields":    [ {...}, ... ]         对接字段（按飞驼对接规范抽取的业务字段，
                                        起运港/目的港/中转港 分组，见 parse_mapped_fields）
  }
"""
import json
import threading
import time

import requests

from . import config
from .carriers import translate_status

# ================================================================
# 全局限流（所有并发线程共享一把锁）
# ================================================================
# 飞驼限流：42900 = 60次/10秒 = 全局限速 6 次/秒。
# 程序批量查询用多线程并发（见 main.py BatchQueryWorker），
# 但所有对飞驼的 HTTP 请求都要过这一个闸门：保证任意两次请求
# 间隔不小于 REQUEST_MIN_INTERVAL，整体速率不超过 5 次/秒
# （留 20% 余量，避免边缘触发 42900）。
_throttle_lock = threading.Lock()          # 全局请求闸门
_last_request_at = 0.0                     # 上次请求发出时间（epoch 秒）
REQUEST_MIN_INTERVAL = 0.2                 # 任意两次请求最小间隔（5 次/秒）


def _throttle_wait():
    """所有对飞驼的 HTTP 请求发出前调用：保证全局限速（线程安全）。

    多线程并发时会排队：前面的请求刚发出，后面的就等够间隔再发，
    从而把"并发"转化成"稳定的高速串行"，既不触发 42900，又比
    原来每条 0.8 秒的串行快得多。
    """
    global _last_request_at
    with _throttle_lock:
        now = time.time()
        wait = REQUEST_MIN_INTERVAL - (now - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        _last_request_at = time.time()

# 飞驼接口状态码 → 说明（来自《飞驼对接数据》文档的状态码表，图2）
# 批量查询结果里的"状态"列就是用这张表映射（20000=有数据、20001=无数据 等）
STATUS_CODE_MAP = {
    20000: "有数据",
    20001: "无数据",
    40300: "无权限",
    40100: "token无效",
    40400: "错误链接",
    40500: "方法不允许",
    40101: "账号或密码错误",
    40102: "账号被停用",
    40103: "账号不存在",
    40000: "参数错误",
    40001: "参数列表过长",
    40010: "不支持坐标系",
    40011: "坐标系转换错误",
    40020: "无法获知船公司代码",
    50000: "内部错误",
    42900: "调用次数超限，不能超过60次/10秒",
}


def translate_status_code(code):
    """把飞驼状态码翻译成中文说明（批量查询"状态"列用）。

    参数：
        code: 接口返回的 statusCode（可能是数字，也可能是字符串）
    返回：
        中文说明；不认识的状态码返回"未知状态码(N)"
    """
    try:
        code = int(code)
    except (TypeError, ValueError):
        return f"未知状态码({code})"
    return STATUS_CODE_MAP.get(code, f"未知状态码({code})")


def query_bill(
    bill_no,
    carrier_short,
    bill_category="BL",
    container_no="",
    port_code="",
    is_export="",
    pol_code="",
    pod_code="",
    business_no="",
    subscribe_retry=True,
):
    """查询一个单号/箱号的物流跟踪信息。

    【重要】提单号、订舱号、箱号三者**填一个就行**，有数据即可查询。
    如果只填了箱号，就按箱号查；只填单号就按单号查。

    参数说明（都是平时业务上常用的叫法）：
        bill_no:        提单号或订舱号（选填，和箱号至少填一个）
        carrier_short:  船司简称（如 "MSC"、"APL"，程序会自动翻译成接口代码）
        bill_category:  单号类型："BL"提单号 或 "BK"订舱号（没填单号时不起作用）
        container_no:   箱号（选填，和单号至少填一个）
        port_code:      港区代码（选填，走港区数据时用）
        is_export:      "E"出口 / "I"进口（与 port_code 配套）
        pol_code:       起运港代码（部分船司强制要求，如内贸船司）
pod_code:      目的港代码
        business_no:   客户订单号（跟单联调用）
        subscribe_retry: 订阅成功但暂无数据时，是否在本函数内自动重试几次
                       （默认 True 保持原行为；批量/多维表格场景传 False：
                        首轮快速返回，由外层统一等待后重查，避免等待叠加）

    返回：
        整理好的结果字典（结构见模块顶部说明）。

    【Token 自动处理】
      配置了账号密码（client_id/secret）时，程序会自动：
        · 启动后第一次查询前，若没有有效 token，自动换取一次
        · 查询中遇到 40100（token 无效/过期），自动换取新 token 并重查一次
     这样用户不用关心 token 24 小时过期的问题。
    """
    from .carriers import get_carrier_info

    # ---- 0. 校验：单号/箱号/港区 至少填一个 ----
    bill_no = (bill_no or "").strip()
    container_no = (container_no or "").strip()
    port_code = (port_code or "").strip()
    if not (bill_no or container_no or port_code):
        return _error_result("请至少填写一个：提单号/订舱号/箱号。")

    # ---- 1. 把船司简称翻译成接口代码 ----
    carrier_info = get_carrier_info(carrier_short)
    if carrier_info is None:
        return {
            "success": False,
            "message": f"没找到叫「{carrier_short}」的船司，请从 113 家列表里选择正确的简称。",
            "raw": None,
            "summary": {},
            "nodes": [],
            "fields": [],
        }
    carrier_code = carrier_info["api_code"]

    # ---- 2. 检查该船司的特殊要求（比如必须提单号+箱号） ----
    note = carrier_info.get("note", "")
    if "必须" in note and (not container_no or not pol_code or not pod_code):
        return {
            "success": False,
            "message": f"船司 {carrier_short} 有特殊要求：{note}。请补全箱号/起运港/目的港后再试。",
            "raw": None,
            "summary": {},
            "nodes": [],
            "fields": [],
        }

    # ---- 3. 组装请求体 ----
    payload = {
        "billNo": bill_no,
        "containerNo": container_no,
        "carrierCode": carrier_code,
        "portCode": port_code.strip(),
        "isExport": is_export.strip(),
        # 只有传了单号才带单号类型；只查箱号时留空，避免接口误解
        "billCategory": (bill_category or "").strip() if bill_no else "",
        "polCode": pol_code.strip(),
        "podCode": pod_code.strip(),
        "businessNo": business_no.strip(),
    }

    # ---- 4. 确保 token 有效（配置了账号密码时自动换取/刷新） ----
    ok, msg = ensure_token()
    if not ok:
        return _error_result(msg)

    # ---- 5. 发起请求（订阅成功但暂无数据时，自动多试几次；token失效自动重取） ----
    # 飞驼是"订阅+查询"模式：第一次查一个单号，可能返回"订阅成功"但数据还在生成中。
    # 这里用循环自动重试，最多 3 次，避免用户手动点了又点。
    max_attempts = 3 if subscribe_retry else 1
    last_body = None
    token_refreshed = False   # 本轮是否已经重取过一次 token（防止死循环）
    for attempt in range(1, max_attempts + 1):
        headers = {
            "Authorization": f"Bearer {config.get_freightower_token()}",
            "Content-Type": "application/json",
        }
        body, status_code = _post_once(payload, headers)

        # 考虑网络类失败（没拿到接口返回）就不重试了，直接报错
        if body is None:
            return _error_result(status_code)
        last_body = body

        message = body.get("message", "")

        # 40100 = token 无效/过期：若配置了账号密码，自动重取一次再查
        if status_code == 40100 and not token_refreshed:
            ok, msg2 = ensure_token(force=True)
            if ok:
                token_refreshed = True
                continue   # 换到新 token，重新发这次请求
            return {
                "success": False,
                "message": f"Token 失效（40100）且自动换取失败：{msg2}",
                "raw": body,
                "summary": {},
                "nodes": [],
                "fields": [],
            }

        # 只有 20000(查询成功)/20001(订阅成功) 算成功；其他都是失败
        if status_code not in (20000, 20001):
            return {
                "success": False,
                "message": f"查询失败（{status_code}）：{message}",
                "raw": body,
                "summary": {},
                "nodes": [],
            }

        # 解析这次的结果；只要解析出节点数据，就算查到了
        data = body.get("data") or {}
        result = data.get("result") or {}
        summary, nodes = _parse_result(result)
        fields = parse_mapped_fields(result)   # 按对接规范抽取业务字段
        if nodes or attempt == max_attempts:
            break
        # 还没数据：给飞驼几秒生成时间，再试一次（新单号一般 5~10 秒内出数据）
        time.sleep(5)

    if not nodes:
        message = last_body.get("message", "")
        if "订阅成功" in message:
            return {
                "success": True,
                "message": "订阅成功，但暂时还没有节点数据（飞驼正在抓取，可稍后重查）。",
                "raw": last_body,
                "summary": summary,
                "nodes": [],
                "fields": fields,
            }
        return {
            "success": True,
            "message": "查询成功，该单暂无节点数据（可能船司接口还没更新）。",
            "raw": last_body,
            "summary": summary,
            "nodes": [],
            "fields": fields,
        }

    return {
        "success": True,
        "message": "查询成功",
        "raw": last_body,
        "summary": summary,
        "nodes": nodes,
        "fields": fields,
    }


def query_batch_row(carrier_short, bill_no="", container_no="", subscribe_retry=True):
    """批量查询单条数据：按优先级降级查询，并返回"状态"列内容。

    优先级规则（用户需求）：
      1. 船公司不存在（不在 113 家列表）→ 直接返回状态"船公司不存在"
      2. 提单号、箱号都有：
         ① 三者一起查（船司+提单号+箱号）
         ② 没结果 → 降级 船司+提单号
         ③ 还没结果 → 降级 船司+箱号
         ④ 全都没结果 → 状态"参数错误"
      3. 只有提单号或箱号 → 船司 + 存在的字段查询即可

    参数：
        carrier_short: 船司简称
        bill_no:       提单号（可空）
        container_no:  箱号（可空）
        subscribe_retry: 透传给 query_bill（False=不内部等待重试，快速返回）
    返回：
        一个结果字典（结构和 query_bill 一样，额外带"状态"）：
          {
            "success": True/False,
            "status":  "有数据/无数据/船公司不存在/参数错误/..."（图2状态码说明）
            "raw"/"summary"/"nodes"/"fields": 同 query_bill
          }
    """
    from .carriers import get_carrier_info

    # ---- 1. 船公司不存在 ----
    carrier_info = get_carrier_info(carrier_short)
    if carrier_info is None:
        return {
            "success": False,
            "status": "船公司不存在",
            "message": f"船司「{carrier_short}」不在 113 家列表里",
            "raw": None, "summary": {}, "nodes": [], "fields": [],
        }

    # 收集需要尝试的查询组合（按优先级从高到低）
    attempts = []
    if bill_no and container_no:
        # 三者都有：①三者一起 → ②船司+提单号 → ③船司+箱号
        attempts.append((bill_no, container_no))
        attempts.append((bill_no, ""))
        attempts.append(("", container_no))
    elif bill_no:
        attempts.append((bill_no, ""))
    elif container_no:
        attempts.append(("", container_no))
    else:
        # 船司之外啥都没填 → 参数错误
        return {
            "success": False,
            "status": "参数错误",
            "message": "提单号/箱号至少填一个",
            "raw": None, "summary": {}, "nodes": [], "fields": [],
        }

    # ---- 2. 逐个组合尝试，查到节点数据就返回 ----
    last_body = None
    for b, c in attempts:
        result = query_bill(
            bill_no=b,
            carrier_short=carrier_short,
            bill_category="BL" if b else "",
            container_no=c,
            subscribe_retry=subscribe_retry,
        )
        last_body = result["raw"]
        # 该组合查到了节点数据 → 成功，状态按状态码映射
        if result["success"] and result["nodes"]:
            code = _raw_status_code(result["raw"])
            result["status"] = translate_status_code(code)
            return result

    # ---- 3. 所有组合都没查到节点 ----
    # 状态取最后一次返回的状态码；如果是 20001 无数据也算"无数据"，
    # 但按用户需求：三者都有时全没结果 → "参数错误"
    code = _raw_status_code(last_body)
    status = translate_status_code(code) if code else "参数错误"
    return {
        "success": False,
        "status": status,
        "message": f"多组查询均无节点数据（最后状态码 {code}）",
        "raw": last_body,
        "summary": {},
        "nodes": [],
        "fields": [],
    }


def _raw_status_code(raw):
    """从查询返回的原始 JSON 里取出 statusCode（没有返回 None）。"""
    if not raw or not isinstance(raw, dict):
        return None
    return raw.get("statusCode")


# ================================================================
# Token 自动获取（用账号密码换取 access_token，免去手动更新）
# ================================================================


def ensure_token(force=False):
    """确保有一个可用的飞驼 token；没有或过期时，用账号密码自动换取。

    什么时候会"自动换"：
      · 当前没有 token（还没配过）
      · token 超过 12 小时（接口说 24 小时有效，提前换避免刚好过期）
      · 查询中被 40100 拒了，会带 force=True 强制换
    什么时候不换：
      · 没配置账号密码（client_id/secret 为空）→ 直接用手动填的 token
      · 换 token 的接口请求失败 → 返回失败原因，让用户去配置页看

    参数：
        force: True=不管现在 token 是否过期，都强制换取新的
    返回：
        (True, "")    有可用的 token（可能刚换的）
        (False, 原因)  没换成功，原因给人看的文字
    """
    # 没配置账号密码：就用现有的 token（可能是用户手动填的）
    client_id, secret = config.get_freightower_credentials()
    if not (client_id and secret):
        if config.get_freightower_token():
            return True, ""
        return False, "未配置飞驼账号密码，也没有手动填 Token，请到【配置】页填写。"

    # token 还比较新，且不要求强制换 → 直接用现有的
    if not force:
        token = config.get_freightower_token()
        if token:
            age = config.freightower_token_age()
            if age < 0 or age < config.TOKEN_REFRESH_SECONDS:
                return True, ""

    # 需要换新：调用获取 Token 接口
    new_token, err = fetch_access_token(client_id, secret)
    if not new_token:
        return False, f"自动获取 Token 失败：{err}"
    config.save_freightower_token(new_token)
    return True, ""


def fetch_access_token(client_id, secret):
    """调用飞驼"获取 Token"接口，用账号密码换取 access_token。

    参数：
        client_id: 飞驼 API 账号
        secret:    飞驼 API 密码
    返回：
        (token, "")        成功，token 是 access_token 字符串
        ("", 失败原因)     失败，失败原因是人能看懂的提示
    """
    payload = {"clientId": client_id, "secret": secret}
    headers = {"Content-Type": "application/json"}
    _throttle_wait()   # 全局限流：换取 token 也算一次请求
    try:
        resp = requests.post(
            config.FREIGHTOWER_TOKEN_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return "", "请求超时，请检查网络。"
    except requests.exceptions.ConnectionError:
        return "", "网络连接失败，请检查网络。"
    except Exception as exc:
        return "", f"请求出错：{exc}"

    try:
        body = resp.json()
    except Exception:
        return "", f"接口返回的不是 JSON：{resp.text[:200]}"

    status_code = body.get("statusCode")
    data = body.get("data") or {}
    access_token = (data.get("access_token") or "").strip() if isinstance(data, dict) else ""
    if status_code == 20000 and access_token:
        return access_token, ""
    return "", f"换取失败（{status_code}）：{body.get('message', '')}"


def _post_once(payload, headers):
    """发送一次 HTTP 请求并解析 JSON。

    参数：
        payload: 请求体的字典
        headers: 请求头
    返回：
        (body, status_code)
          body      接口返回的 JSON 字典；请求失败时为 None
          status_code  接口返回的 statusCode；请求失败时为一个以"错误:"开头的说明文字
    """
    _throttle_wait()   # 全局限流：并发线程共享闸门，保证整体 ≤5 次/秒
    try:
        resp = requests.post(
            config.FREIGHTOWER_API_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            timeout=config.REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return None, "请求超时了，请检查网络后重试。"
    except requests.exceptions.ConnectionError:
        return None, "网络连接失败，请检查网络。"
    except Exception as exc:
        return None, f"请求出错：{exc}"

    try:
        body = resp.json()
    except Exception:
        return None, f"接口返回的不是 JSON：{resp.text[:200]}"

    return body, body.get("statusCode")


def _parse_result(result):
    """把接口返回的 result 对象解析成【概要】和【节点明细】两面。

    参数：
        result: 飞驼返回的 data.result 字典
    返回：
        (summary, nodes) 两个东西，含义见模块顶部。
    """
    # ---------- 概要部分 ----------
    carrier = result.get("carrier") or {}
    first_vessel = result.get("firstVessel") or {}
    current = result.get("currentStatus") or {}
    booking = result.get("booking") or {}

    # 起运港/目的港取 routes 第一段的 pol / 最后一段的 pod
    routes = result.get("routes") or []
    pol_name = routes[0].get("polName") if routes else None
    pod_name = routes[-1].get("podName") if routes else None

    summary = {
        "billNo": result.get("billNo", ""),                          # 单号
        "statusCategory": result.get("statusCategory", ""),          # 总状态代码
        "statusCn": translate_status(result.get("statusCategory")),  # 总状态中文
        "statusDescription": result.get("statusDescription", ""),    # 总状态英文描述
        "updateTime": result.get("updateTime", ""),                  # 数据更新时间
        "carrierCn": carrier.get("nameCn", ""),                      # 船司中文名
        "vessel": (first_vessel.get("vessel") or ""),                # 船名
        "voyage": (first_vessel.get("voyage") or ""),                # 航次
        "polName": pol_name or "",                                   # 起运港
        "podName": pod_name or "",                                   # 目的港
        "bookingStatusCn": booking.get("bookingStatusCn", ""),       # 订舱状态中文
        # 最新节点信息
        "currentEventCode": current.get("eventCode", ""),
        "currentEventCn": current.get("descriptionCn", ""),
        "currentEventTime": current.get("eventTime", ""),
        "currentEventPlace": current.get("eventPlace", ""),
        "currentContainerNo": current.get("containerNo", ""),
    }

    # ---------- 节点明细部分 ----------
    nodes = []
    containers = result.get("containers") or []
    for cont in containers:
        cont_no = cont.get("containerNo", "")
        status_list = cont.get("status") or []
        for st in status_list:
            # 每个节点一行，带上箱号、时间和中文描述，方便业务同事直接看
            nodes.append({
                "containerNo": cont_no,                              # 箱号
                "eventTime": st.get("eventTime", ""),                # 节点时间
                "eventCode": st.get("eventCode", ""),                # 节点码
                "descriptionCn": st.get("descriptionCn", ""),        # 节点中文名
                "descriptionEn": st.get("descriptionEn", ""),        # 节点英文名
                "eventPlace": st.get("eventPlace", ""),              # 地点
                "transportMode": st.get("transportMode", ""),        # 运输方式
                "vslName": st.get("vslName") or "",                  # 船名
                "voy": st.get("voy") or "",                          # 航次
                "isEsti": st.get("isEsti", ""),                      # 是否预计时间(预测值)
            })
    # 按时间倒序排（最新在前）
    nodes.sort(key=lambda x: x.get("eventTime") or "", reverse=True)

    # ---------- 最新节点：优先用"实际发生"的节点（isEsti != Y） ----------
    # 说明：接口的 currentStatus 只反映实际发生的最新节点；而节点明细里
    # 还混着"预计节点"（isEsti=Y，未来时间）。为了界面口径一致，这里
    # 自己从明细里算：实际最新节点 + 下一预计节点。
    actual_nodes = [n for n in nodes if n["isEsti"] != "Y"]      # 实际发生的
    esti_nodes = [n for n in nodes if n["isEsti"] == "Y"]        # 预计的
    latest_actual = actual_nodes[0] if actual_nodes else None    # 时间倒序后第一条
    next_esti = esti_nodes[-1] if esti_nodes else None           # 预计节点里时间最早 = 下一预计

    if latest_actual:
        # 有实际节点：概要用实际最新（和明细口径一致）
        summary["currentEventCode"] = latest_actual["eventCode"]
        summary["currentEventCn"] = latest_actual["descriptionCn"]
        summary["currentEventTime"] = latest_actual["eventTime"]
        summary["currentEventPlace"] = latest_actual["eventPlace"]
        summary["currentContainerNo"] = latest_actual["containerNo"]
        summary["currentIsEsti"] = "N"
    else:
        # 没有实际节点（刚订阅）：退回用接口的 currentStatus
        summary["currentIsEsti"] = current.get("isEsti", "")

    # 下一预计节点（有就带上，界面会显示"下一节点(预计)"）
    if next_esti:
        summary["nextEventCode"] = next_esti["eventCode"]
        summary["nextEventCn"] = next_esti["descriptionCn"]
        summary["nextEventTime"] = next_esti["eventTime"]
        summary["nextEventPlace"] = next_esti["eventPlace"]
    else:
        summary["nextEventCode"] = ""
        summary["nextEventCn"] = ""
        summary["nextEventTime"] = ""
        summary["nextEventPlace"] = ""

    return summary, nodes


# ================================================================
# 对接字段解析（按《飞驼对接数据 2026-10-12》规范抽取业务字段）
# ================================================================
# 说明：这份文档定义了"起运港/目的港/中转港"三组业务字段，每个字段都有固定的
# 取值来源：
#   terminalPlan  港区船舶计划（开港/截港/截单/截关时间）
#   containers    集装箱节点（提空/进场/海关放行/码头放行/装船/卸船/提柜/还空...）
#   places        发生地信息（type 1起始地/2起运港/3中转港/4目的港/5目的地，
#                 含 etd/atd/eta/ata/vessel/voyage）
# 部分字段还受"港口/船司"限制（比如只有 CNNGB、CNXMN 能拿截单时间），
# 程序照常取值，取不到就显示"—"，并在"说明"里注明限制，方便业务判断。


# 每个字段在界面"说明"列显示的固定说明（港口/船司限制、取值规则）
# 键用 (环节, 字段名称) 定位，和 DEFAULT_FIELD_MAPPING 一一对应
_FIELD_NOTES = {
    ("起运港", "截单时间"): "只有CNNGB和CNXMN能获取",
    ("起运港", "开港时间"): "倍思奇出货的中国6大港口都能获取",
    ("起运港", "截港时间"): "倍思奇出货的中国6大港口都能获取",
    ("起运港", "截关时间"): "只有CNNGB、CNTXG和CNXMN能获取",
    ("起运港", "提空时间"): "isEsti：N实际 / Y预计",
    ("起运港", "进港时间"): "isEsti：N实际 / Y预计",
    ("起运港", "海关状态"): "存在 eventCode=PASS（且有发生时间）即显示「已放行」，否则留空",
    ("起运港", "海关放行"): "只有CNSHA不能获取具体时间；eventCode=PASS",
    ("起运港", "海关滞留"): "只有CNSHA、CNNGB、CNYTN能获取",
    ("起运港", "码头状态"): "存在 eventCode=TMPS 即已放行",
    ("起运港", "码头放行"): "只有CNNGB和CNXMN能获取具体时间；eventCode=TMPS",
    ("起运港", "码头滞留"): "存在 eventCode=TMHD 即滞留",
    ("起运港", "装船时间"): "isEsti：N实际 / Y预计",
    ("起运港", "预计离港时间"): "取 type1/type2 的 etd",
    ("起运港", "实际离港时间"): "取 type1/type2 的 atd",
    ("起运港", "船名航次"): "取 type2 下面的 vessel 和 voyage",
    ("目的港", "预计到港时间"): "取 type4 下面的 eta",
    ("目的港", "实际到港时间"): "取 type4 下面的 ata",
    ("目的港", "卸船时间"): "取 status 的 descriptionCn：卸船 eventTime",
    ("目的港", "可提重时间"): "只有MSC、OOCL、ZIM、MATS能获取可提时间",
    ("目的港", "提重时间"): "取 status 的 descriptionCn：提柜(货) eventTime",
    ("目的港", "还空时间"): "取 status 的 descriptionCn：还空箱 eventTime",
    ("目的港", "目的港查验"): "只有OOCL、ZIM、MATS能获取",
    ("目的港", "目的港放行"): "只有OOCL、ZIM、MATS能获取",
    ("目的港", "IPI实际发车时间"): "type4与type5 code不一致且transportMode_out=RAIL时，取type4的atd",
    ("目的港", "IPI预计到达时间"): "同上条件，取type5的eta",
    ("目的港", "IPI实际到达时间"): "同上条件，取type5的ata",
    ("中转港", "预计到港时间"): "取 type3 下面的 eta",
    ("中转港", "实际到港时间"): "取 type3 下面的 ata",
    ("中转港", "预计离港时间"): "取 type3 下面的 etd",
    ("中转港", "实际离港时间"): "取 type3 下面的 atd",
    ("中转港", "船名航次"): "取 type3 下面的 vessel 和 voyage",
}


def _clean_value(value):
    """把接口返回的值清洗成"展示用"的干净字符串。

    接口有时会返回字符串 "None"、"null" 或空串，业务上都是"没数据"，
    统一转成空串（界面/导出显示空，不出现 None/—）。

    参数：
        value: 接口取到的原始值
    返回：
        干净字符串；空值返回 ""（界面和导出直接留空）
    """
    if value is None:
        return ""
    s = str(value).strip()
    if s in ("", "None", "null", "none", "NULL", "N/A", "nan"):
        return ""
    return s


def parse_mapped_fields(result):
    """按《飞驼对接数据》规范，从接口返回的 result 里抽取 32 个对接字段。

    这个函数是"映射驱动"的：每个字段取什么，完全由
    当前生效的字段映射（config.get_field_mapping()，用户可在配置页修改）
    里的"取值来源"表达式决定。

    参数：
        result: 飞驼返回的 data.result 字典
    返回：
        一个列表，每一项是一个字段字典：
          {
            "环节":   "起运港" / "目的港" / "中转港"
            "字段名称": "截单时间"                 业务叫法
            "英文描述": "portClose"               对接文档里的英文名（可作Excel列名）
            "值":      "2026/08/15 18:00:00"      接口取到的值；取不到是 ""
            "说明":    "只有CNNGB和CNXMN能获取"    港口/船司限制或取值规则说明
          }
        界面可直接按"环节"分组展示，Excel 导出一行一个字段。
    """
    result = result or {}

    fields = []
    for item in config.get_field_mapping():
        section = item["环节"]
        cn = item["字段名称"]
        en = item["英文描述"]
        source = item["取值来源"]

        # IPI 字段有固定判断条件（type4/type5 code不一致 + transportMode_out=RAIL），
        # 条件不满足时即使配置了来源也不取值；满足时按配置的来源取。
        if cn.startswith("IPI"):
            value = _resolve_ipi_value(result, source)
        else:
            value = _resolve_source(result, source)

        fields.append({
            "环节": section,
            "字段名称": cn,
            "英文描述": en,
            "值": _clean_value(value),   # 清洗空值（None/null/— → 空）
            "说明": _FIELD_NOTES.get((section, cn), ""),
        })

    return fields


def _resolve_source(result, source):
    """按"取值来源"表达式从 result 里取一个字段的值（映射配置驱动）。

    表达式规则（用"-"连接层级）：
      terminalplan-portClose                    港区计划对象里的字段
      places-type2-etd                          places 里 type=2 的地点取 etd
      containers-desc-进场-eventTime            status 里中文名=进场 的节点取 eventTime
      containers-code-PASS-eventTime            status 里事件码=PASS 的节点取 eventTime
      containers-exists-PASS-已放行              存在事件码=PASS（且有时间）的节点就输出文案"已放行"
      containers-code-first-GTOT-eventTime      全节点里【第一条】事件码=GTOT 的节点取 eventTime
      containers-code-last-GTIN-eventTime       全节点里【最后一条】事件码=GTIN 的节点取 eventTime
      containers-desc-contains-查验-eventTime   status 里中文名"包含"查验 的节点取 eventTime
      places-type4-vessel/voyage                取 vessel 和 voyage 拼成"船名 / 航次"

    参数：
        result: 飞驼返回的 data.result 字典
        source: 取值来源表达式字符串
    返回：
        取到的值字符串；表达式不认识或取不到返回 ""（界面显示"—"）
    """
    if not source:
        return ""
    parts = [p for p in str(source).split("-") if p]
    if not parts:
        return ""

    head = parts[0]

    # ---- 港区计划对象：terminalplan-open ----
    if head == "terminalplan":
        return str((result.get("terminalPlan") or {}).get(parts[1], ""))

    # ---- places 按类型定位：places-type2-etd ----
    if head == "places":
        type_str = parts[1]                       # "type2"
        field = parts[2]                          # "etd" 或 "vessel/voyage"
        ptype = int(type_str.replace("type", ""))
        place = _place_by_type(result.get("places") or [], (ptype,))
        if "/" in field:                          # 组合字段：vessel/voyage
            f1, f2 = field.split("/", 1)
            v1, v2 = _clean_value(place.get(f1)), _clean_value(place.get(f2))
            return f"{v1} / {v2}".strip(" /") if (v1 or v2) else ""
        return _clean_value(place.get(field, ""))

    # ---- 集装箱节点：containers-desc-进场-eventTime ----
    if head == "containers":
        nodes = _collect_status_nodes(result.get("containers") or [])
        mode = parts[1]
        if mode == "desc":
            if len(parts) > 2 and parts[2] == "contains":
                return _time_by_desc_contains(nodes, parts[3])
            return _time_by_desc(nodes, parts[2])
        if mode == "exists":
            # containers-exists-PASS-已放行
            # → 存在该事件码【且有发生时间】的节点时，输出最后的文案；否则留空
            #   （用于"状态"类字段：有值=已发生，值就是状态文案，如"已放行"）
            code = parts[2]
            text = "-".join(parts[3:])
            for n in nodes:
                if n["eventCode"] == code and _clean_value(n["eventTime"]):
                    return text
            return ""
        if mode == "code":
            # containers-code-first-GTOT-eventTime            → 全节点第一条该事件码
            # containers-code-first-actual-GTOT-eventTime     → 尾程第一条"实际发生"的该事件码
            # containers-code-last-esti-GTIN-eventTime        → 尾程最后一条"预计"的该事件码
            # containers-code-last-esti-truck-FETA-eventTime  → 尾程最后一条"预计"且运输方式=卡车的该事件码
            # 中间可选修饰词顺序不限：actual/esti（实际/预计）、truck（只认运输方式=卡车）
            if len(parts) > 2 and parts[2] in ("first", "last"):
                kind, only_mode, idx = "any", "", 3
                while idx < len(parts) - 2:          # 最后两个元素固定是 事件码 + 字段名
                    if parts[idx] in ("actual", "esti"):
                        kind = parts[idx]
                    elif parts[idx] == "truck":
                        only_mode = "TRUCK"
                    idx += 1
                return _time_by_code_edge(nodes, parts[idx], parts[2], kind, only_mode)
            return _time_by_code(nodes, parts[2])

    return ""


def _resolve_ipi_value(result, source):
    """IPI 字段的特殊取值：先判断"是否内陆联运"，满足才按配置的来源取。

    判断条件（文档规定）：
      places 里 type4 和 type5 的 code 不一致，且 type4 的 transportMode_out=RAIL
    """
    places = result.get("places") or []
    p4 = _place_by_type(places, (4,))
    p5 = _place_by_type(places, (5,))
    ok = (
        bool(p4) and bool(p5)
        and p4.get("code") != p5.get("code")
        and str(p4.get("transportMode_out") or "").upper() == "RAIL"
    )
    if not ok:
        return ""
    return _resolve_source(result, source)


def _collect_status_nodes(containers):
    """把每个箱子的 status 节点拍平成一个列表（每个节点带箱号、时间、事件码等）。

    参数：
        containers: 接口返回的 containers 数组
    返回：
        [{eventTime, eventCode, descriptionCn, isEsti, ...}, ...]
    """
    out = []
    for cont in containers or []:
        for st in (cont.get("status") or []):
            out.append({
                "containerNo": cont.get("containerNo", ""),
                "eventTime": st.get("eventTime", ""),
                "eventCode": st.get("eventCode", ""),
                "descriptionCn": st.get("descriptionCn", ""),
                "isEsti": st.get("isEsti", ""),
                "eventPlace": st.get("eventPlace", ""),
                "transportMode": st.get("transportMode", ""),   # 运输方式（TRUCK/VESSEL/FEEDER/RAIL）
                "sort": st.get("sort", 0),      # 接口给的节点顺序号（取"第一/最后一条"要用）
            })
    return out


def _time_by_desc(nodes, desc):
    """按节点中文名找时间：优先"实际发生"的节点（isEsti != Y），找不到再看预计的。

    参数：
        nodes: _collect_status_nodes 拍平的节点列表
        desc:  中文节点名，比如"提空箱"
    返回：
        该节点的时间字符串；没找到返回 ""（界面显示"—"）
    """
    for n in nodes:
        if n["descriptionCn"] == desc and n["isEsti"] != "Y":
            return n["eventTime"]
    for n in nodes:
        if n["descriptionCn"] == desc:
            return n["eventTime"]
    return ""


def _time_by_code(nodes, code):
    """按事件码找时间：优先"实际发生"的节点（isEsti != Y），找不到再看预计的。

    参数：
        nodes: _collect_status_nodes 拍平的节点列表
        code:  事件码，比如 "PASS"、"TMPS"
    返回：
        该节点的时间字符串；没找到返回 ""（界面显示"—"）
    """
    for n in nodes:
        if n["eventCode"] == code and n["isEsti"] != "Y":
            return n["eventTime"]
    for n in nodes:
        if n["eventCode"] == code:
            return n["eventTime"]
    return ""


def _time_by_code_edge(nodes, code, which, kind="any", only_mode=""):
    """按事件码取【尾程】"全节点里第一条 / 最后一条"的时间（卡车发出/到达专用）。

    什么是"尾程"：
      只认"装船之后"的卡车节点。货物装船之前出现的卡车节点（提空箱、进场、
      起运地内陆短驳、上支线船前的卡车进场等）都不算尾程。
      实测：起运地卡车节点一定排在"首个装船/船运节点"之前，用节点顺序号(sort)就能切开。

    和 _time_by_code 的区别（很重要）：
      · _time_by_code 会优先挑"实际发生"的节点，取不到再退到预计的；
      · 本函数严格按接口给的节点顺序(sort)取第一条或最后一条，
        绝不往前退到别的节点 —— 取不到就返回空。

    业务场景（4 个卡车字段）：
      · 卡车实际发出时间 = 尾程里第一条"实际发生"的"卡车出场"(GTOT) 的时间
      · 卡车实际到达时间 = 尾程里最后一条"实际发生"的"卡车进场"(GTIN) 的时间
      · 卡车预计发出时间 = 尾程里第一条"仍为预计"的 GTOT 的时间（下一次计划发车）
      · 卡车预计到达时间 = 尾程里最后一条"仍为预计"的 GTIN 的时间（最终计划到达）

    参数：
        nodes: _collect_status_nodes 拍平的节点列表
        code:  事件码，如 "GTOT"、"GTIN"
        which: "first" 取第一条 / "last" 取最后一条
        kind:  "any" 不筛实际/预计 / "actual" 只算实际发生 / "esti" 只算预计
        only_mode: 只认某种运输方式的节点（如 "TRUCK"），空字符串表示不筛
    返回：
        该节点的时间字符串；没有符合条件的节点 → ""
    """
    ordered = sorted(nodes, key=lambda n: n["sort"] if isinstance(n["sort"], int) else 9999)

    # 找"装船/船运"分界点：第一条 装船(LOBD) 或 船运(VESSEL) 节点的顺序号
    # （支线 FEEDER 不算分界：支线离港时货其实还在起运地，刚上支线船前的卡车进场属起运地）
    boundary = None
    for n in ordered:
        if n["eventCode"] == "LOBD" or str(n.get("transportMode", "")).upper() == "VESSEL":
            boundary = n["sort"] if isinstance(n["sort"], int) else 9999
            break

    # 分界点之前的一律不算尾程；找不到分界点（数据不全）时保持原逻辑：全部节点都参与
    last_mile = [
        n for n in ordered
        if boundary is None or not isinstance(n["sort"], int) or n["sort"] >= boundary
    ]

    matched = []
    for n in last_mile:
        if n["eventCode"] != code:
            continue
        if only_mode and str(n.get("transportMode", "")).upper() != only_mode:
            continue                                    # 运输方式不符（如到达只认卡车）
        value = _clean_value(n["eventTime"])
        if kind == "actual":
            # 只算"实际发生"的（isEsti 不是 Y），且必须真的有时间
            if str(n.get("isEsti", "")).upper() == "Y" or not value:
                continue
        elif kind == "esti":
            # 只算"预计"的（isEsti=Y），且必须真的有时间
            if str(n.get("isEsti", "")).upper() != "Y" or not value:
                continue
        matched.append(value)

    if not matched:
        return ""
    return matched[0] if which == "first" else matched[-1]


def _time_by_desc_contains(nodes, keyword):
    """按"中文名里包含某个词"找时间（用于目的港查验/放行这类没固定码的节点）。

    参数：
        nodes: _collect_status_nodes 拍平的节点列表
        keyword: 关键词，比如"查验"、"放行"
    返回：
        第一个命中的节点时间字符串；没找到返回 ""（界面显示"—"）
    """
    for n in nodes:
        if keyword in (n["descriptionCn"] or "") and n["isEsti"] != "Y":
            return n["eventTime"]
    for n in nodes:
        if keyword in (n["descriptionCn"] or ""):
            return n["eventTime"]
    return ""


def _place_by_type(places, types):
    """按地点类型取 places 里的第一个匹配项（type 数字，越小越优先）。

    参数：
        places: 接口返回的 places 数组
        types:  要匹配的类型元组，比如 (2, 1) 表示"优先起运港type2，没有用type1兜底"
    返回：
        匹配到的地点字典；一个都没匹配返回 {}（界面显示"—"）
    """
    for t in types:
        for p in places or []:
            if str(p.get("type")) == str(t):
                return p
    return {}


def _error_result(message):
    """生成一个统一的"失败结果"字典，省得每处都写一遍。"""
    return {"success": False, "message": message, "raw": None, "summary": {}, "nodes": [], "fields": []}


def format_result(result):
    """把查询结果格式化成人能读懂的文本（主要是命令行测试阶段用）。

    参数：
        result: query_bill() 返回的结果字典
    返回：
        一段给打印/显示的中文文本。
    """
    if not result.get("success"):
        return f"✗ {result['message']}"

    s = result["summary"]
    lines = []
    lines.append("=" * 60)
    lines.append(f"单号：{s['billNo']}")
    lines.append(f"总状态：{s['statusCn']}（{s['statusDescription']}）")
    if s["carrierCn"]:
        lines.append(f"船司：{s['carrierCn']}")
    if s["vessel"]:
        lines.append(f"船名航次：{s['vessel']} / {s['voyage']}")
    if s["polName"]:
        lines.append(f"航线：{s['polName']} → {s['podName']}")
    if s["currentEventCn"]:
        lines.append(
            f"最新节点：{s['currentEventCn']}（{s['currentEventCode']}）"
            f" {s['currentEventTime']} @ {s['currentEventPlace']}"
        )
    lines.append(f"数据更新时间：{s['updateTime']}")
    lines.append("-" * 60)

    nodes = result["nodes"]
    if nodes:
        lines.append(f"节点明细（共 {len(nodes)} 条，最新在前）：")
        for n in nodes[:20]:
            lines.append(
                f"  {n['eventTime']}  {n['descriptionCn'] or n['eventCode']}"
                f"  {n['eventPlace']}  箱{n['containerNo']}（{n['transportMode']}）"
            )
        if len(nodes) > 20:
            lines.append(f"  ... 还有 {len(nodes) - 20} 条未显示")
    else:
        lines.append("（暂无节点数据，飞驼正在抓取中）")
    lines.append("=" * 60)
    return "\n".join(lines)
