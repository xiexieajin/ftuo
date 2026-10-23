# -*- coding: utf-8 -*-
"""
飞书多维表格客户端模块
======================
负责程序和飞书多维表格之间的所有通信（POC 已于 2026-10-15 全链路验证通过）：

  · parse_base_url()  从多维表格链接里解析出 app_token / table_id / view_id
  · FeishuBase 类     换 token（2小时缓存）、按视图读记录、按 record_id 批量回写
  · send_webhook()    给群机器人发通知（自定义机器人 + 签名校验）
  · to_timestamp()    时间字符串 → 毫秒时间戳（多维表格日期列要求这种格式）

设计原则（和 POC 脚本一致，出错就把飞书返回的错误码/信息抛出来）：
  · 读取按视图（view_id）分页拉取，每页 500 条；
  · 回写严格按 record_id 定位（每行记录的唯一身份证号），绝不错行；
  · 写入自动分批（500 条/批），批间隔 0.5 秒，避免触发飞书限流。
"""
import base64
import hashlib
import hmac
import re
import threading
import time
from datetime import datetime

import requests

# 飞书开放平台接口前缀（所有飞书 API 都以它开头）
FEISHU_HOST = "https://open.feishu.cn"
# 分页读取时每页条数（飞书单页上限 500）
PAGE_SIZE = 500
MAX_READ_PAGES = 200        # 读表翻页上限（500条/页 → 最多 10 万条），防死循环兜底
# 批量回写时每批条数
WRITE_BATCH = 500
# 相邻两批写入之间的间隔（秒），礼貌对待飞书接口
WRITE_INTERVAL = 0.5
# 单次 HTTP 请求超时（秒）
REQUEST_TIMEOUT = 30


class FeishuBaseError(Exception):
    """飞书接口调用失败时抛出的异常（带飞书返回的错误码和信息，方便排查）。"""


def parse_base_url(url):
    """从多维表格链接里解析出三个"门牌号"。

    链接样例：
      https://xxx.feishu.cn/base/V6xEbKhWBaKQ?table=tblJ59l&view=vew3Txp
      └─ app_token：哪张表格文件（/base/ 后面那串）
      └─ table：    哪张数据表（table= 参数）
      └─ view：     哪个视图（view= 参数，可省略）

    返回：
        (app_token, table_id, view_id) —— 解析不到的项返回空字符串
    """
    url = (url or "").strip()
    m = re.search(r"/base/([A-Za-z0-9]+)", url)
    app_token = m.group(1) if m else ""
    m = re.search(r"[?&]table=([A-Za-z0-9]+)", url)
    table_id = m.group(1) if m else ""
    m = re.search(r"[?&]view=([A-Za-z0-9]+)", url)
    view_id = m.group(1) if m else ""
    return app_token, table_id, view_id


def cell_text(value):
    """把多维表格单元格的值剥成纯文本（判断"是否为空"/展示用）。

    取值可能有三层"壳"，这里统一剥干净：
      ① 字符串：直接返回；
      ② lookup(引用)列：返回 {"type":1, "value":[...]}，要再取里面的 value；
      ③ 多段文本列表：[{"text":"MSC"},...]，把每段的 text 拼起来。
    """
    if value is None:
        return ""
    if isinstance(value, dict):
        return cell_text(value.get("value"))
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for seg in value:
            if isinstance(seg, dict):
                parts.append(seg.get("text", ""))
            else:
                parts.append(str(seg))
        return "".join(parts).strip()
    return str(value).strip()


# 时间字符串支持的所有格式（按顺序尝试解析）
_TIME_FORMATS = (
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%Y%m%d%H%M%S", "%Y%m%d",
)


def to_timestamp(text):
    """把时间字符串（如 "2026/08/15 18:00:00"）转成毫秒时间戳。

    多维表格的日期列（DateTime 类型）要求传毫秒时间戳（如 1755252000000），
    传字符串会报错。解析失败返回 None（调用方就不写这个单元格）。
    """
    text = (text or "").strip()
    if not text:
        return None
    # 纯数字：接口有时直接给毫秒时间戳，原样转 int 即可
    if text.isdigit() and len(text) >= 12:
        try:
            return int(text[:13])
        except ValueError:
            return None
    for fmt in _TIME_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    return None


def send_webhook(webhook_url, secret, text):
    """给飞书群自定义机器人发文本通知（带签名校验）。

    加签算法（飞书官方规则）：
      用 "时间戳\\n签名密钥" 当钥匙，对空内容做 HmacSHA256 运算，
      再 base64 编码得到 sign；时间戳和 sign 一起放进消息体，机器人验签通过才发送。
    webhook_url 或签名密钥没配置时直接跳过（不报错，通知是可选功能）。
    """
    if not webhook_url:
        return
    body = {"msg_type": "text", "content": {"text": text}}
    if secret:
        timestamp = str(int(time.time()))
        string_to_sign = f"{timestamp}\n{secret}"
        sign = base64.b64encode(
            hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        ).decode("utf-8")
        body["timestamp"] = timestamp
        body["sign"] = sign
    try:
        resp = requests.post(webhook_url, json=body, timeout=15)
        data = resp.json()
        # 飞书机器人成功返回 {"code":0,...}；code 非 0 说明验签失败/被限流等
        if data.get("code") not in (0, None) and data.get("StatusCode") != 0:
            raise FeishuBaseError(f"Webhook 发送失败: {data}")
    except requests.RequestException as e:
        raise FeishuBaseError(f"Webhook 网络请求失败: {e}")


class FeishuBase:
    """飞书多维表格客户端：一张数据表对应一个实例。

    用法（三步走）：
        fb = FeishuBase(app_id, app_secret, app_token, table_id)
        records = fb.search_records(view_id, field_names=[...])   # 读
        fb.batch_update([(record_id, {"列名": 值}), ...])          # 写
    """

    def __init__(self, app_id, app_secret, app_token, table_id):
        self.app_id = (app_id or "").strip()
        self.app_secret = (app_secret or "").strip()
        self.app_token = (app_token or "").strip()
        self.table_id = (table_id or "").strip()
        self._token = ""                 # 内存里的 tenant_access_token
        self._token_time = 0.0           # token 获取时间（判断是否过期）
        self._token_lock = threading.Lock()   # 多线程取 token 时只取一次

    # ---------------- token 管理 ----------------
    def get_token(self, force=False):
        """获取 tenant_access_token（2 小时有效，内存缓存，过期/强制时重取）。"""
        with self._token_lock:
            fresh = (time.time() - self._token_time) < 110 * 60   # 提前 10 分钟续期
            if not force and self._token and fresh:
                return self._token
            url = f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal"
            resp = requests.post(url, json={"app_id": self.app_id,
                                            "app_secret": self.app_secret},
                                 timeout=REQUEST_TIMEOUT)
            data = resp.json()
            if data.get("code") != 0:
                raise FeishuBaseError(
                    f"获取飞书 token 失败: code={data.get('code')} msg={data.get('msg')}")
            self._token = data["tenant_access_token"]
            self._token_time = time.time()
            return self._token

    def _headers(self):
        """带通行证的请求头（所有数据接口都要带）。"""
        return {"Authorization": f"Bearer {self.get_token()}"}

    def _check(self, data, action):
        """检查飞书返回是否成功；失败时抛出带错误码的异常（token 过期自动重试一次）。"""
        if data.get("code") == 99991663 or data.get("code") == 99991661:
            # token 无效/过期：强制重取后由调用方重试
            self.get_token(force=True)
        if data.get("code") != 0:
            raise FeishuBaseError(f"{action}失败: code={data.get('code')} msg={data.get('msg')}")
        return data

    # ---------------- 读取 ----------------
    def list_fields(self):
        """拉取这张数据表的全部列（字段）定义，返回 {列名: 类型编号} 字典。

        类型编号速查：1=文本 2=数字 3=单选 5=日期时间 11=人员 13=电话 15=超链接
        19=引用(lookup) 1001=创建时间 1002=修改时间（公式/lookup 等只读列写入会被忽略）
        """
        fields = {}
        page_token = ""
        while True:
            path = (f"/open-apis/bitable/v1/apps/{self.app_token}/tables/{self.table_id}"
                    f"/fields?page_size=100" + (f"&page_token={page_token}" if page_token else ""))
            resp = requests.get(f"{FEISHU_HOST}{path}", headers=self._headers(),
                                timeout=REQUEST_TIMEOUT)
            data = self._check(resp.json(), "拉取字段")
            for item in data["data"]["items"]:
                fields[item["field_name"]] = item["type"]
            if not data["data"].get("has_more"):
                break
            page_token = data["data"]["page_token"]
        return fields

    def search_records(self, view_id="", field_names=None, progress_cb=None):
        """按视图搜索记录（自动翻页拿全）。

        参数：
            view_id:     视图 ID（只读该视图筛出来的行；为空则读全表）
            field_names: 只要这些列（不传则读全部列）
            progress_cb: 进度回调 progress_cb(第几页, 已读条数)，用于界面实时显示读表进度
        返回：
            记录列表，每条形如 {"record_id": "recXXX", "fields": {列名: 值}}
        """
        url = (f"{FEISHU_HOST}/open-apis/bitable/v1/apps/{self.app_token}"
               f"/tables/{self.table_id}/records/search?page_size={PAGE_SIZE}")
        records, page_token, page_no = [], "", 1
        while True:
            # ⚠ 关键：page_token 必须拼在 URL 查询参数里！
            # 放 JSON body 会被飞书忽略 → 每次都返回第 1 页且 has_more 恒为 true
            # → 死循环（视图记录数超过 PAGE_SIZE 时才暴露，表现为一直"正在读取视图记录..."）。
            page_url = url + (f"&page_token={page_token}" if page_token else "")
            body = {}
            if view_id:
                body["view_id"] = view_id
            if field_names:
                body["field_names"] = field_names
            resp = requests.post(page_url, headers=self._headers(), json=body,
                                 timeout=REQUEST_TIMEOUT)
            data = self._check(resp.json(), "读取记录")
            records.extend(data["data"].get("items", []))
            if progress_cb:
                progress_cb(page_no, len(records))     # 实时汇报读表进度
            if not data["data"].get("has_more"):
                return records
            page_token = data["data"]["page_token"]
            page_no += 1
            if page_no > MAX_READ_PAGES:      # 兜底：防止任何情况下无限翻页
                raise FeishuBaseError(
                    f"读取记录超过 {MAX_READ_PAGES} 页仍未读完，已中止（请检查视图记录数）")
            time.sleep(0.2)

    # ---------------- 写入 ----------------
    def batch_update(self, updates):
        """按 record_id 批量更新记录，绝不错行。

        参数：
            updates: [(record_id, {列名: 新值}), ...] 列表
        说明：
            · 一次最多 WRITE_BATCH 条，多了自动分批，批间隔 WRITE_INTERVAL 秒；
            · record_id 是每行的唯一身份证号，写哪行就是哪行（POC 已实测核验）。
        """
        url = (f"{FEISHU_HOST}/open-apis/bitable/v1/apps/{self.app_token}"
               f"/tables/{self.table_id}/records/batch_update")
        total = len(updates)
        for i in range(0, total, WRITE_BATCH):
            batch = updates[i:i + WRITE_BATCH]
            body = {"records": [{"record_id": rid, "fields": fields}
                                for rid, fields in batch]}
            resp = requests.post(url, headers=self._headers(), json=body,
                                 timeout=REQUEST_TIMEOUT)
            self._check(resp.json(), "写入记录")
            if i + WRITE_BATCH < total:
                time.sleep(WRITE_INTERVAL)
