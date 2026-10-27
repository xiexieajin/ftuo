# -*- coding: utf-8 -*-
"""
物流查询助手（GUI 版）—— 主程序入口

界面按 Figma 设计稿重构（v7）：
  · 左侧深石墨侧边栏（品牌区 + 查询/配置导航 + 版本号）
  · 右侧内容区：顶部栏（页面标题 + 窗口按钮）+ 页面堆叠
  · 查询页：条件卡片（船司 + 单号类型三选一 + 单号 + 箱号可选）、运单概要卡片、节点历史表格
  · 配置页：飞驼 Token + 预留飞书配置

窗口特性：
  · 无边框窗口（自绘顶部栏，颜色与窗口一致，看不出边框）
  · 顶部栏：左边当前页标题/副标题（可拖动移动窗口/双击最大化），右边最小化/最大化/关闭按钮
  · 界面文本支持鼠标选中复制

运行方式：
  python main.py
"""
import os
import re
import sys
import time

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QKeySequence, QPainterPath, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLineEdit, QRadioButton, QCheckBox,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFrame, QMessageBox,
    QCompleter, QScrollArea, QStackedWidget, QGridLayout,
    QPlainTextEdit, QFileDialog, QTabWidget, QSizeGrip, QSplitter,
    QAbstractScrollArea,
)

from src import config
from src import freightower
from src.carriers import CARRIERS, get_carrier_info
from src.carriers import match_carrier_code
from src.feishu_base import (
    FeishuBase, FeishuBaseError, cell_text, parse_base_url, send_webhook, to_timestamp,
)


def resource_path(rel):
    """取资源文件（图标等）的真实路径。

    源码运行：直接取项目目录下的文件；
    打包成 exe 后：PyInstaller 会把 --add-data 的文件解压到临时目录 _MEIPASS，
    必须去那里找，否则 exe 里没有这些文件。
    """
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def load_app_icon():
    """加载应用图标（吉祥物）；找不到就返回空图标（不影响运行）。"""
    path = resource_path(os.path.join("assets", "logo.ico"))
    return QIcon(path) if os.path.exists(path) else QIcon()

# ---------- 整体配色（按 Figma 设计稿：深石墨侧边栏 + 浅灰内容区 + 品牌蓝） ----------
# 设计稿令牌（来源：Figma 设计稿 colors_and_type.css）：
#   主色   #2f6fed（克制专业蓝）   侧边栏 #1a1d24 / 高亮 #2a2f3a
#   背景   #f4f6f9                卡片    #ffffff / 边框 #e4e7ee
#   正文   #0f172a                次要文字 #64748b
#   状态   成功#16a34a 警告#d97706 错误#dc2626 信息#0ea5e9
APP_STYLE = """
/* 全局不写 QWidget 背景色！！否则会污染所有容器（品牌区/输入框包裹层出现白块）。
   需要背景的地方全部用具体选择器显式指定。字体与颜色仍需全局设置。 */
* {
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    font-size: 13px;
    color: #0f172a;
}
/* ---- 窗口外框：圆角 + 细边框（无边框窗口的视觉外壳） ---- */
QWidget#WindowFrame {
    background: #f4f6f9;
    border: 1px solid #dfe3ea;
    border-radius: 14px;
}

/* ---- 页面内容区背景（滚动页的底色） ---- */
QWidget#PageBg { background: #f4f6f9; }

/* ---- 左侧深石墨侧边栏 ---- */
/* 注意：QWidget 上用 QSS border-radius 做圆角背景在 Qt 里不渲染（坑），
   所以侧边栏背景改由 Sidebar 类 paintEvent 自绘（深色 + 左下圆角）。 */
QLabel#BrandName { background: transparent; color: #e8ebf0; font-size: 15px; font-weight: 600; }
QLabel#BrandSub  { background: transparent; color: #6b7280; font-size: 11px; }
QLabel#SidebarFoot { background: transparent; color: #6b7280; font-size: 11px; }
QPushButton#NavItem {
    background: transparent; color: #b4bcc9; border: none;
    border-radius: 6px; padding: 10px 16px; font-size: 14px;
    text-align: left;
}
QPushButton#NavItem:hover { background: #2a2f3a; color: #e8ebf0; }
QPushButton#NavItem:checked {
    background: #2a2f3a; color: #e8ebf0;
    border-left: 3px solid #2f6fed;   /* 选中项左侧蓝色竖条（设计稿 active） */
    padding-left: 13px;
}

/* ---- 顶部标题栏（横贯整宽，高 40px，更像系统标题栏） ---- */
QWidget#TitleBar { background: #f4f6f9; border-top-left-radius: 14px; border-top-right-radius: 14px; }
QLabel#TitleApp  { background: transparent; font-size: 13px; color: #475569; }

/* ---- 通用文字 ---- */
QLabel#FieldLabel { color: #64748b; background: transparent; }
QLabel#CardTitle  { color: #0f172a; background: transparent; font-size: 14px; font-weight: 600; }
QLabel#CardLabel  { color: #64748b; background: transparent; font-size: 12px; font-weight: 600; }
QLabel#SummaryKey   { color: #64748b; background: transparent; font-size: 12px; }
QLabel#SummaryValue { color: #0f172a; background: transparent; font-weight: 600; }
QLabel#MonoValue    { color: #0f172a; background: transparent; font-weight: 600; font-family: "Consolas", "Microsoft YaHei", monospace; }

/* 页面大标题（内容区顶部） */
QLabel#PageTitle { font-size: 20px; font-weight: 700; color: #0f172a; background: transparent; }
QLabel#PageSub   { font-size: 12px; color: #64748b; background: transparent; margin-top: 2px; }

/* 总状态徽章：平时蓝色浅底；查询中显示中性深灰；失败红色 */
QLabel#StatusBig {
    background: rgba(47, 111, 237, 0.12); color: #2f6fed;
    border-radius: 4px; padding: 3px 12px;
    font-size: 15px; font-weight: 700;
}

/* ---- 白色卡片 ---- */
QFrame#Card {
    background: #ffffff;
    border: 1px solid #dce1ea;
    border-radius: 8px;
}

/* ---- 表单控件 ---- */
QComboBox, QLineEdit {
    background: #ffffff;
    border: 1px solid #e4e7ee;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #e8f1ff;
    selection-color: #0f172a;
}
QComboBox:focus, QLineEdit:focus { border: 1px solid #2f6fed; }
QComboBox:hover, QLineEdit:hover { border: 1px solid #c9cfd9; }
QRadioButton, QCheckBox { background: transparent; spacing: 6px; color: #64748b; }
QRadioButton:checked, QCheckBox:checked { color: #0f172a; font-weight: 500; }

/* ---- 按钮 ---- */
QPushButton#PrimaryBtn {
    background: #2f6fed; color: #ffffff; border: none;
    border-radius: 6px; padding: 8px 28px;
    font-size: 14px; font-weight: 600;
}
QPushButton#PrimaryBtn:hover { background: #2a60e0; }
QPushButton#PrimaryBtn:disabled { background: #a8c6f7; color: #f0f4ff; }
QPushButton#GhostBtn {
    background: #ffffff; color: #0f172a; border: 1px solid #e4e7ee;
    border-radius: 6px; padding: 8px 28px; font-size: 14px;
}
QPushButton#GhostBtn:hover { background: #f8f9fb; }

/* ---- 表格（节点历史） ---- */
QTableWidget {
    background: #ffffff; border: none;
    gridline-color: #f0f1f3; selection-background-color: #e8f1ff; selection-color: #0f172a;
}
QHeaderView::section {
    background: #f8f9fb; border: none; border-bottom: 1px solid #e4e7ee;
    padding: 9px 12px; font-weight: 600; color: #64748b;
}
QTableWidget::item { padding: 2px 3px; }

/* ---- 状态栏（与背景融为一体，仅作提示用） ---- */
QStatusBar { background: #f4f6f9; color: #64748b; border: none; }
QStatusBar::item { border: none; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #d1d5db; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; }
QScrollBar::handle:horizontal { background: #d1d5db; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""

# 节点表格的列标题
NODE_HEADERS = ["时间", "节点", "实际/预计", "地点", "箱号", "运输方式", "船名/航次"]

# 运输方式：接口返回的英文代码 → 中文
TRANSPORT_MODE_MAP = {
    "VESSEL": "海运", "TRUCK": "卡车", "RAIL": "铁路",
    "SHIPMENT": "单证", "BARGE": "驳船", "FEEDER": "支线",
}

# 运输方式小标签的配色（浅底 + 同色系文字），对应设计稿 tag-sea / tag-truck / tag-doc
TRANSPORT_TAG_COLORS = {
    "VESSEL": ("#e6ecf7", "#3b6fd4"),   # 海运：蓝
    "FEEDER": ("#e6ecf7", "#3b6fd4"),   # 支线：蓝
    "BARGE": ("#e6ecf7", "#3b6fd4"),    # 驳船：蓝
    "TRUCK": ("#eef1f6", "#64748b"),    # 卡车：灰
    "RAIL": ("#fdf4e9", "#d97706"),     # 铁路：橙
    "SHIPMENT": ("#f4f5f7", "#6b7280"), # 单证：浅灰
}


# 主按钮 QSS：直接在按钮上 setStyleSheet，绕开 Windows 原生按钮样式对背景色的干扰
BUTTON_PRIMARY_QSS = """
QPushButton {
    background: #2f6fed; color: #ffffff; border: none;
    border-radius: 6px; padding: 0 28px;
    font-size: 14px; font-weight: 600;
}
QPushButton:hover { background: #2a60e0; }
QPushButton:disabled { background: #a8c6f7; color: #f0f4ff; }
"""


def mk_label(text, obj_name=None, selectable=True):
    """统一创建标签的工厂函数。

    参数：
        text: 标签文字
        obj_name: 样式表用的对象名（比如 SummaryKey/SummaryValue）
        selectable: True 时文字可用鼠标选中复制（用户要求界面文本可复制）
    """
    lab = QLabel(text)
    if obj_name:
        lab.setObjectName(obj_name)
    if selectable:
        # TextSelectableByMouse = 鼠标按住可拖选文字，选中后 Ctrl+C 复制
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lab


class CaptionButton(QWidget):
    """标题栏小按钮：用画笔自己画图标（不用文字符号），保证三个按钮风格、大小完全统一。

    背景：之前用 "— □ ✕" 文字当图标，三种字符在字体里渲染出来大小粗细都不一样，
    看着不像一套。改成自绘后：最小化=横线、最大化=方框（最大化时变双框=还原）、关闭=X。
    """

    # 点击信号（和 QPushButton 的 clicked 一样用法）
    clicked = Signal()

    def __init__(self, kind, parent=None):
        """kind: "min"最小化 / "max"最大化(还原) / "close"关闭"""
        super().__init__(parent)
        self.kind = kind
        self.restore = False      # 窗口最大化时，图标切成"还原"（两个叠着的方框）
        self._hover = False       # 鼠标是否悬停（悬停时换底色）
        self.setFixedSize(36, 28) # 三个按钮完全同尺寸（对齐设计稿窗口按钮）
        self.setCursor(Qt.PointingHandCursor)

    def set_restore(self, on):
        """切换"最大化/还原"图标形态。"""
        self.restore = on
        self.update()   # 触发重画

    def enterEvent(self, event):
        """鼠标进入：记录悬停状态并重画（换底色）。"""
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        """鼠标离开：取消悬停并重画。"""
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        """松开鼠标且指针还在按钮范围内，才算一次有效点击。"""
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, event):
        """画按钮：悬停底色 + 图标线条（所有图标统一用 1.3px 灰色线条画）。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)   # 抗锯齿，线条更圆润

        # 悬停底色：关闭按钮悬停红色，其他按钮浅灰
        if self._hover:
            bg = QColor("#f53f3f") if self.kind == "close" else QColor("#e5e6eb")
            painter.fillRect(self.rect(), bg)

        # 线条颜色：关闭按钮悬停时白色（红底白线），平时统一深灰
        line = QColor("#ffffff") if (self._hover and self.kind == "close") else QColor("#4e5969")
        painter.setPen(QPen(line, 1.3))
        cx, cy = self.width() / 2, self.height() / 2

        if self.kind == "min":
            # 最小化：一条居中短线
            painter.drawLine(QPointF(cx - 5, cy + 3.5), QPointF(cx + 5, cy + 3.5))
        elif self.kind == "max":
            if self.restore:
                # 还原：两个叠着的方框（前后遮挡）
                painter.drawRect(QRectF(cx - 5.5, cy - 2.5, 8, 8))
                painter.drawRect(QRectF(cx - 2.5, cy - 5.5, 8, 8))
            else:
                # 最大化：一个方框
                painter.drawRect(QRectF(cx - 4.5, cy - 4.5, 9, 9))
        else:
            # 关闭：X（两条对角线）
            painter.drawLine(QPointF(cx - 4.5, cy - 4.5), QPointF(cx + 4.5, cy + 4.5))
            painter.drawLine(QPointF(cx + 4.5, cy - 4.5), QPointF(cx - 4.5, cy + 4.5))


class CopyableTable(QTableWidget):
    """支持多选单元格 + Ctrl+C 复制的表格。

    用法：鼠标拖框选 / Ctrl+点选 多个单元格 → 按 Ctrl+C →
    粘贴到 Excel/记事本（列与列之间是制表符，行与行之间是换行）。
    """

    def keyPressEvent(self, event):
        """拦截键盘事件：Ctrl+C 走自定义复制，其他按键交给表格原本处理。"""
        if event.matches(QKeySequence.Copy):
            self.copy_selection()
        else:
            super().keyPressEvent(event)

    def copy_selection(self):
        """把选中的单元格内容拼成文本，放进系统剪贴板。"""
        ranges = self.selectedRanges()
        if not ranges:
            return
        lines = []
        for r in ranges:
            # 一个 range 是一块连续选区：逐行逐列取出文字，拼成"单元格1\t单元格2..."
            for row in range(r.topRow(), r.bottomRow() + 1):
                cells = []
                for col in range(r.leftColumn(), r.rightColumn() + 1):
                    item = self.item(row, col)
                    cells.append(item.text() if item else "")
                lines.append("\t".join(cells))
        QApplication.clipboard().setText("\n".join(lines))


class TitleBar(QWidget):
    """顶部标题栏（横贯整宽 40px）：无边框窗口靠它拖动和放系统按钮。

    对齐图片外框：
      · 高 40px，左侧一行应用名（灰色小字），右侧最小化/最大化/关闭自绘按钮
      · 圆角只出现在标题栏上沿（窗口外壳的顶部两角）
      · 按住标题区可拖动窗口，双击最大化/还原
    """

    def __init__(self, parent_window):
        super().__init__()
        self.win = parent_window          # 主窗口引用（移动/最大化都要操作它）
        self._drag_pos = None             # 拖动时记录鼠标相对窗口的位置

        self.setObjectName("TitleBar")
        self.setFixedHeight(40)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 6, 10, 6)
        lay.setSpacing(0)

        # 左侧不写文字，只留间距（要求去掉「物流查询助手·飞驼集装箱跟踪」）
        lay.addStretch(1)

        # 三个窗口控制按钮（自绘图标，大小风格完全统一）
        self.btn_min = CaptionButton("min")      # —
        self.btn_max = CaptionButton("max")      # □（最大化时变双框）
        self.btn_close = CaptionButton("close")  # X
        lay.addWidget(self.btn_min)
        lay.addWidget(self.btn_max)
        lay.addWidget(self.btn_close)

        # 按钮功能绑定
        self.btn_min.clicked.connect(self.win.showMinimized)   # 最小化到任务栏
        self.btn_max.clicked.connect(self.toggle_max)          # 最大化/还原切换
        self.btn_close.clicked.connect(self.win.close)         # 关闭程序

    def toggle_max(self):
        """切换最大化/还原（同步切换按钮图标形态）。"""
        if self.win.isMaximized():
            self.win.showNormal()
        else:
            self.win.showMaximized()
        # 最大化状态下按钮显示"还原"双框图标
        self.btn_max.set_restore(self.win.isMaximized())

    # ---- 拖动窗口的实现：鼠标按下记录起点 → 移动时窗口跟手 ----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # 记录"鼠标位置 - 窗口左上角"的偏移，之后移动窗口时保持这个偏移
            self._drag_pos = event.globalPosition().toPoint() - self.win.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._drag_pos is not None:
            # 惯例：最大化状态下拖标题栏，先还原成普通窗口
            if self.win.isMaximized():
                self.win.showNormal()
            self.win.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None   # 松手，结束拖动

    def mouseDoubleClickEvent(self, event):
        self.toggle_max()       # 双击标题栏：最大化/还原


class QueryWorker(QThread):
    """后台查询线程：在界面点"查询"后，用它去调飞驼接口，不卡住界面。"""
    finished_signal = Signal(dict)

    def __init__(self, payload, parent=None):
        super().__init__(parent)
        self.payload = payload

    def run(self):
        """线程真正执行的内容：调用查询模块，然后把结果通过信号发回主界面。"""
        p = self.payload
        result = freightower.query_bill(
            bill_no=p["bill_no"],
            carrier_short=p["carrier_short"],
            bill_category=p["bill_category"],
            container_no=p.get("container_no", ""),
        )
        self.finished_signal.emit(result)


class BatchQueryWorker(QThread):
    """批量查询线程：多线程并发逐条查询，边查边汇报进度。

    用法：把待查的 payload 列表丢给它，它会：
      · 进度每变化 progress_step 条，发 progress_signal(完成数, 总数)
      · 全部查完，发 finished_signal(所有结果列表, 成功条数) 一次性交给界面
    为什么结果一次性返回：几千条时逐行发信号会让界面刷新卡顿，
    改为收集完统一填表（表格一次性 setRowCount 比逐行快得多）。

    并发说明：线程数 BATCH_CONCURRENCY=20，配合 freightower 全局限流
    （任意两次请求 ≥0.2 秒 ≈ 5 次/秒），既提速又不触发飞驼 42900。
    """
    BATCH_CONCURRENCY = 20         # 并发线程数（全局限流 5 次/秒是硬上限，线程多只是排队不空闲）
    progress_step = 1              # 每完成 1 条就发一次进度（实时进度；全量上千条也扛得住）
    progress_signal = Signal(int, int)     # (完成数, 总数)
    finished_signal = Signal(list, int)    # (结果列表[{"result","payload"}], 成功条数)
    stage_signal = Signal(str)              # 阶段提示（如"3 条订阅中等待数据..."）

    def __init__(self, payloads, parent=None):
        super().__init__(parent)
        self.payloads = payloads            # 待查的 payload 列表

    def run(self):
        """并发查询所有行；结果按输入顺序收集，查询完成统一汇报。"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        total = len(self.payloads)
        results = [None] * total      # 按输入顺序占位（多线程完成顺序不定，用索引落位）
        ok_count = 0
        done = 0

        def work(idx_p):
            """单条查询任务：idx_p = (序号, payload)。"""
            idx, p = idx_p
            result = freightower.query_batch_row(
                carrier_short=p.get("carrier_short", ""),
                bill_no=p.get("bill_no", ""),
                container_no=p.get("container_no", ""),
            )
            return idx, result

        # 并发执行（限流在 freightower 内部统一控制，线程再多也不会超速）
        with ThreadPoolExecutor(max_workers=self.BATCH_CONCURRENCY) as pool:
            futures = {pool.submit(work, (i, p)): i for i, p in enumerate(self.payloads)}
            for fut in as_completed(futures):
                idx, result = fut.result()
                results[idx] = {
                    "result": result,
                    "payload": self.payloads[idx],
                }
                if result.get("success"):
                    ok_count += 1
                done += 1
                if done % self.progress_step == 0 or done == total:
                    self.progress_signal.emit(done, total)

        # 首轮后：对"无数据"（订阅中）的行按单查同款节奏等待重查
        # （20秒/轮 × 最多10轮 ≈ 3分半；与多维表格更新共用同一逻辑）
        results = _wait_and_retry(
            self.payloads, results, concurrency=self.BATCH_CONCURRENCY,
            is_stopped=self.isInterruptionRequested,
            stage_cb=lambda s: self.stage_signal.emit(s))
        ok_count = sum(1 for r in results
                       if _unwrap_result(r) and _unwrap_result(r).get("success"))

        # 全部完成：一次性把结果交给界面
        self.finished_signal.emit(results, ok_count)


class FeishuUpdateWorker(QThread):
    """【多维表格更新】后台线程：一键完成"读表 → 清洗 → 查询 → 回写 → 通知"全流程。

    整个流程（对应业务需求，2026-10-15 确认）：
      1. Webhook 通知群里"开始执行"；
      2. 按配置的链接读多维表格目标视图的全部记录；
      3. 数据清洗：
         · 船公司 Carrier 必填：先按 113 家简称匹配，匹配不上再按 SCAC 码反查
           （如 MAEU→MSK、HLCU→HPL），还匹配不上 → 回写"对接状态=无法获知船公司代码"；
         · 提单号和箱号至少要有一个，两个都空 → 回写"对接状态=参数错误"；
      4. 有效数据并发调飞驼查询（复用现有 4 线程 + 全局限流 + 降级逻辑）；
      5. 查询结果（对接状态 + 36 个对接字段）按 record_id 精确回写多维表格，
         日期列自动转毫秒时间戳，文本列原样写入；
      6. Webhook 通知群里"执行完成"（带统计汇总）。

    线程安全说明：查询阶段用线程池并发，回写阶段在收集完所有结果后统一分批执行，
    任意时刻同一张表只有一个写入流，不会触发飞书并发冲突（1254291）。
    """
    BATCH_CONCURRENCY = 20     # 飞驼查询并发数（与批量查询页一致；全局限流 5 次/秒是硬上限）
    progress_step = 1          # 每完成 1 条发一次进度（实时进度）

    stage_signal = Signal(str)             # 阶段变化（"正在读取表格..."等提示文本）
    progress_signal = Signal(int, int)     # 查询进度（完成数, 总数）
    finished_signal = Signal(object)       # 全部完成（统计字典）或出错（{"error": 消息}）

    def __init__(self, fs_cfg, parent=None):
        """fs_cfg: 配置页里的飞书配置字典（app_id/app_secret/table_link/webhook...）。"""
        super().__init__(parent)
        self.fs_cfg = fs_cfg

    def run(self):
        """线程主体：按 6 步流程执行，任何一步出错都发 error 并停止。"""
        try:
            stats = self._run_flow()
            self.finished_signal.emit(stats)
        except FeishuBaseError as e:
            self.finished_signal.emit({"error": str(e)})
        except Exception as e:                                  # 兜底：不让线程无声死掉
            self.finished_signal.emit({"error": f"未预期的错误：{e}"})

    # ---------------- 内部步骤 ----------------
    def _run_flow(self):
        """完整流程，返回统计字典（同时负责开始/完成两次 Webhook 通知）。"""
        import time as _time
        t0 = _time.time()
        cfg = self.fs_cfg

        # 0. 解析配置（链接 → 表格/数据表/视图 三个标识）
        app_token, table_id, view_id = parse_base_url(cfg.get("table_link", ""))
        if not (cfg.get("app_id") and cfg.get("app_secret") and app_token and table_id):
            raise FeishuBaseError("飞书配置不完整：请到【配置】页填写 App ID、"
                                  "App Secret 和多维表格链接（链接需包含 table 参数）")
        webhook_url = cfg.get("webhook_url", "")
        webhook_secret = cfg.get("webhook_secret", "")
        fb = FeishuBase(cfg["app_id"], cfg["app_secret"], app_token, table_id)

        # 飞书字段映射：字段名称 → 多维表格列名（用户可在配置页改）
        mapping = config.get_feishu_field_mapping()
        # 映射键必须用（环节, 字段名称）二元组：字段名称有重名
        # （如"预计离港时间"在起运港和中转港各出现一次），
        # 只用字段名做键会让中转港覆盖起运港，导致前者列永远写不进数据。
        col_of = {(m["环节"], m["字段名称"]): m["多维表格列名"].strip() for m in mapping}
        status_col = col_of.get(("状态", "对接状态"), "对接状态")

        # 1. 通知开始
        self.stage_signal.emit("已发送开始通知，正在读取多维表格...")
        send_webhook(webhook_url, webhook_secret,
                     "【多维表格更新】开始执行：正在读取待更新运单...")

        # 2. 拉取列类型（判断哪列是日期列，回写时要把时间字符串转毫秒时间戳）
        self.stage_signal.emit("正在读取表格结构...")
        field_types = fb.list_fields()
        # 映射里有、但表格里还没有的列：跳过不写（提示用户），不再直接报错中断
        # —— 场景：映射配置扩展了新字段（如"尾程卡车"），表格还没建对应列时，
        #    其他字段的更新照常进行，缺的列下次建好后再写。
        missing_cols = sorted({name for name in col_of.values()
                               if name and name not in field_types
                               and name != status_col})
        if missing_cols:
            for key in [k for k, v in col_of.items() if v in missing_cols]:
                col_of.pop(key)
            self.stage_signal.emit(
                f"提示：多维表格缺少列 {'、'.join(missing_cols)}，本次跳过这些列"
                f"（在表格建好同名列后自动恢复写入）")

        # 3. 读视图记录（只取需要的列：输入三列 + 对接状态）
        self.stage_signal.emit("正在读取视图记录...")
        records = fb.search_records(
            view_id,
            progress_cb=lambda page, n: self.stage_signal.emit(
                f"正在读取视图记录... 第 {page} 页，已读 {n} 条"))
        total = len(records)
        if total == 0:
            send_webhook(webhook_url, webhook_secret,
                         "【多维表格更新】执行完成：视图内没有记录，无需处理。")
            return {"total": 0}

        # 4. 数据清洗：分出"直接回写状态"和"要查询"的两批
        self.stage_signal.emit(f"读取到 {total} 条，正在清洗数据...")
        direct_updates = []     # [(record_id, {对接状态: xx})] 不用查询、直接回写状态
        query_rows = []         # 要调飞驼查询的行
        for rec in records:
            fields = rec.get("fields", {})
            carrier_raw = cell_text(fields.get("Carrier"))
            bl = cell_text(fields.get("B|L NO."))
            cntr = cell_text(fields.get("Container"))
            if not carrier_raw or (not bl and not cntr):
                # 船公司空 或 提单号/箱号都空 → 参数错误（业务清洗规则）
                direct_updates.append((rec["record_id"], {status_col: "参数错误"}))
                continue
            short = match_carrier_code(carrier_raw)   # 简称 → SCAC 两级匹配
            if not short:
                direct_updates.append(
                    (rec["record_id"], {status_col: "无法获知船公司代码"}))
                continue
            query_rows.append({
                "record_id": rec["record_id"],
                "carrier_short": short,
                "bill_no": bl,
                "container_no": cntr,
                "carrier_raw": carrier_raw,
            })

        # 5. 并发查询（复用 freightower 内部限流与降级逻辑）
        self.stage_signal.emit(
            f"清洗完成：有效 {len(query_rows)} 条待查询，"
            f"{len(direct_updates)} 条直接标记状态。正在查询飞驼...")
        results = [None] * len(query_rows)
        done = 0
        if query_rows:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def work(idx_row):
                """单条查询任务（idx_row = (序号, 行)），查完返回 (序号, 结果)。"""
                idx, row = idx_row
                result = freightower.query_batch_row(
                    carrier_short=row["carrier_short"],
                    bill_no=row["bill_no"],
                    container_no=row["container_no"],
                )
                return idx, result

            with ThreadPoolExecutor(max_workers=self.BATCH_CONCURRENCY) as pool:
                futures = {pool.submit(work, (i, r)): i
                           for i, r in enumerate(query_rows)}
                for fut in as_completed(futures):
                    if self.isInterruptionRequested():
                        break                     # 用户点了停止：不再提交新查询
                    idx, result = fut.result()
                    results[idx] = result
                    done += 1
                    if done % self.progress_step == 0 or done == len(query_rows):
                        self.progress_signal.emit(done, len(query_rows))

        # 5.5 等待重查阶段：与查询页单查同款节奏（20秒/轮 × 最多10轮 ≈ 3分半），
        #     超时仍无数据才最终回写"无数据"。
        results = self._retry_pending(query_rows, results)

        # 6. 汇总回写（查询结果 + 直接状态，一起分批写回）
        self.stage_signal.emit("查询完成，正在回写多维表格...")
        updates = list(direct_updates)
        ok_count = 0
        for row, result in zip(query_rows, results):
            if result is None:
                continue                          # 停止时没查到的行：本次不回写
            fields_out = {status_col: result.get("status", "")}
            if result.get("success"):
                ok_count += 1
                # 当前节点/下一节点（与查询页"最新节点/下一节点(预计)"同款口径）
                for field_name, kind in (("当前节点", "current"), ("下一节点", "next")):
                    col = col_of.get(("节点", field_name))
                    text = _node_summary_text(result.get("summary") or {}, kind)
                    if col and text:
                        fields_out[col] = text
                # 36 个对接字段 → 按映射列名回写（日期列转时间戳，文本列原样）
                for f in result.get("fields", []):
                    col = col_of.get((f.get("环节", ""), f.get("字段名称", "")))
                    if not col:
                        continue
                    value = f.get("值", "")
                    if field_types.get(col) == 5:            # DateTime 列
                        # 空值也要回写（None 表示清空）：否则表格里会残留上一轮/旧口径的值，
                        # 例：口径改成"交货地抵达"后，原来按"卡车进场"写进去的到达时间会一直留在表里。
                        fields_out[col] = to_timestamp(value)
                    else:                                   # 文本/单选等列
                        if value:
                            fields_out[col] = value
            updates.append((row["record_id"], fields_out))
        if updates:
            fb.batch_update(updates)

        # 7. 通知完成 + 返回统计
        elapsed = int(_time.time() - t0)
        stats = {
            "total": total,
            "queried": len(query_rows),
            "ok": ok_count,
            "direct": len(direct_updates),
            "written": len(updates),
            "elapsed": elapsed,
        }
        summary = (f"【多维表格更新】执行完成：共 {total} 条；"
                   f"查询 {len(query_rows)} 条（有数据 {ok_count}）；"
                   f"直接标记 {len(direct_updates)} 条；"
                   f"回写 {len(updates)} 条；耗时 {elapsed // 60}分{elapsed % 60}秒。")
        send_webhook(webhook_url, webhook_secret, summary)
        return stats

    def _retry_pending(self, query_rows, results):
        """对"无数据"（订阅中）的行按单查同款节奏等待并自动重查（见 _wait_and_retry）。"""
        return _wait_and_retry(query_rows, results,
                               concurrency=self.BATCH_CONCURRENCY,
                               is_stopped=self.isInterruptionRequested,
                               stage_cb=lambda s: self.stage_signal.emit(s))


# 等待重查的节奏（用户要求：每 5 秒重查一轮，最多 40 轮 → 总等待上限 200 秒）
RETRY_ROUNDS = 40     # 最多重查轮数
RETRY_INTERVAL = 5    # 每轮等待秒数（总等待上限 = 40 × 5 = 200 秒 ≈ 3分半）


def _unwrap_result(r):
    """剥掉批量查询结果的包装：裸结果直接返回；{"result":..., "payload":...} 包装取里面的 result。"""
    if isinstance(r, dict) and isinstance(r.get("result"), dict):
        return r["result"]
    return r


def _wait_and_retry(rows, results, concurrency=4, is_stopped=None, stage_cb=None):
    """【通用】对"无数据"（订阅中）的行按单查同款节奏等待并自动重查。

    批量查询和多维表格更新共用这个函数：
      · 首轮查询后，收集状态="无数据"的行（飞驼订阅中，正在向船司抓数据）；
      · 每 RETRY_INTERVAL 秒一轮并发重查，最多 RETRY_ROUNDS 轮；
      · 某行拿到数据就更新 results；全部拿到 / 超轮数上限 / 用户点停止 就结束；
      · 等待按 1 秒切片，点"停止"最多 1 秒内响应。
    参数：
        rows:       每行的查询参数（需要含 carrier_short/bill_no/container_no 键）
        results:    首轮结果列表（本函数原地更新后返回）
        is_stopped: 返回 True 表示用户请求停止（QThread 的 isInterruptionRequested）
        stage_cb:   阶段提示回调（如"3 条订阅中等待数据，已等 40/200 秒..."）
    """
    pending = [i for i, r in enumerate(results)
               if _unwrap_result(r) is not None
               and _unwrap_result(r).get("status") == "无数据"]
    if not pending:
        return results

    from concurrent.futures import ThreadPoolExecutor, as_completed
    import time as _time
    timeout = RETRY_ROUNDS * RETRY_INTERVAL
    t0 = _time.time()

    def requery(idx):
        """重查一行（一轮一次请求，不内部重试——节奏由本函数统一控制）。"""
        row = rows[idx]
        return idx, freightower.query_batch_row(
            carrier_short=row["carrier_short"],
            bill_no=row.get("bill_no", ""),
            container_no=row.get("container_no", ""),
            subscribe_retry=False,
        )

    rounds = 0
    # 退出条件用"实际总耗时"而不是"固定轮数"：
    # 每轮真实耗时 = 5 秒等待 + 本轮并发重查的耗时（8 条受全局限流至少要 1.6 秒，
    # 遇到降级重试/网络慢会更久），所以按轮数算会让总时长超过 200 秒（曾出现已等 237/200 秒）。
    while pending and rounds < RETRY_ROUNDS and _time.time() - t0 < timeout:
        # 等一个重查间隔：按 1 秒切片 —— 既能随时被"停止"打断，也每秒刷新一次界面计数
        for _ in range(RETRY_INTERVAL):
            if is_stopped and is_stopped():
                return results           # 用户停止：不再重查，已查到的照常使用
            _time.sleep(1)
            if stage_cb:                 # 每秒汇报一次，秒数 1 秒 1 秒地走
                stage_cb(f"{len(pending)} 条订阅中等待数据，"
                         f"已等 {int(_time.time() - t0)}/{timeout} 秒，自动重查...")
        if _time.time() - t0 >= timeout:
            break                        # 到点即停（200 秒是含每轮查询耗时的总上限）
        # 并发重查当前所有"无数据"的行
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(requery, i): i for i in pending}
            still = []
            for fut in as_completed(futures):
                idx, result = fut.result()
                if result.get("status") == "无数据":
                    still.append(idx)    # 这轮还没出数据，下一轮继续等
                else:
                    # 拿到数据（或最终失败状态）→ 更新（兼容包装/裸两种结构）
                    r = results[idx]
                    if isinstance(r, dict) and isinstance(r.get("result"), dict):
                        r["result"] = result
                    else:
                        results[idx] = result
        pending = still
        rounds += 1
        if not pending:
            if stage_cb:
                stage_cb("订阅数据已全部生成。")
            break
    if pending and stage_cb:
        stage_cb(f"{len(pending)} 条订阅中等待数据，已等 {timeout}/{timeout} 秒，"
                 f"超过等待上限，按当前结果继续执行。")
    return results


def _node_summary_text(summary, kind):
    """从查询结果的 summary 里组装"当前节点/下一节点"的回写文案。

    kind="current"：最新实际节点（与查询页概要卡"最新节点"同款口径）；
    kind="next"：下一预计节点（与"下一节点(预计)"同款口径）。
    文案格式：描述（事件码） 时间 地点 —— 某项没有就省略，全没有返回空。
    """
    cn = summary.get(f"{kind}EventCn", "")
    if not cn:
        return ""
    code = summary.get(f"{kind}EventCode", "")
    t = summary.get(f"{kind}EventTime", "")
    place = summary.get(f"{kind}EventPlace", "")
    parts = [f"{cn}（{code}）" if code else cn]
    if t:
        parts.append(t)
    if place:
        parts.append(place)
    return " ".join(parts)


class Sidebar(QWidget):
    """左侧深色侧边栏：用画笔自绘黑蓝背景（比 QSS 圆角背景可靠）。

    为什么不用 QSS 画背景？
      QWidget 上写 `background + border-radius` 时，Qt 的样式引擎对普通
      QWidget 的圆角背景填充不可靠（会整个不渲染/显示透明）。
      这里自己用 QPainter 画：深色 #1a1d24 铺满 + 四角 14px 圆角（与窗口外壳一致）。
    内部控件（品牌文字/导航按钮）保持透明，自然露出这块深色底。
    """

    SIDEBAR_BG = QColor("#1a1d24")   # 深石墨黑蓝

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        # 不参与 QSS 背景绘制（我们自己画），避免被样式表污染
        self.setAttribute(Qt.WA_StyledBackground, False)

    def paintEvent(self, event):
        """把整个侧边栏填成深色，四角圆角化，让内部控件透明浮现其上。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 14, 14)   # 半径与窗口外壳一致
        p.fillPath(path, self.SIDEBAR_BG)


class MainWindow(QMainWindow):
    """主窗口：无边框 + 左侧深色侧边栏 + 右侧（顶部栏 + 查询/配置页面堆叠）。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("物流查询助手 - 飞驼集装箱跟踪")
        # 窗口图标（任务栏也用吉祥物，和 exe 图标一致）
        self.setWindowIcon(load_app_icon())
        # 无边框 + 背景透明：画一个圆角细边框的窗口外壳（对齐图片外框）
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(1440, 900)
        self.setMinimumSize(1100, 700)     # 拖动缩放的保底：别被拖到看不清
        self.worker = None        # 当前正在跑的后台查询线程
        self.last_result = None   # 最近一次查询结果

        # ---- 订阅中自动轮询（新箱号/单号首次订阅，飞驼要几分钟抓数据） ----
        self.poll_timer = QTimer(self)              # 定时器：每隔一阵自动重查
        self.poll_timer.setInterval(20 * 1000)      # 20 秒一查
        self.poll_timer.timeout.connect(self._poll_once)
        self.poll_count = 0                         # 已经轮询了几次
        self.poll_max = 10                          # 最多轮询 10 次（约 3 分半）
        self.polling = False                        # 当前是否处于轮询状态

        # ---- 整体布局：窗口外壳（圆角）内 = 标题栏 + （左侧侧边栏 | 右侧页面堆叠） ----
        central = QWidget()
        central.setObjectName("WindowFrame")   # 圆角 + 细边框背景
        root = QVBoxLayout(central)
        root.setContentsMargins(1, 1, 1, 1)    # 留出边框细线
        root.setSpacing(0)

        # 顶部标题栏（横贯整宽 40px，可拖动窗口）
        self.title_bar = TitleBar(self)
        root.addWidget(self.title_bar)

        # 中间一行：左侧深色导航栏 + 右侧页面切换区
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        body.addWidget(self._build_sidebar())   # 左侧导航（查询/配置）

        self.stacked = QStackedWidget()          # 右侧页面堆叠
        self.stacked.addWidget(self._build_query_page())   # 索引 0：查询页
        self.stacked.addWidget(self._build_batch_page())  # 索引 1：批量查询页
        self.stacked.addWidget(self._build_config_page())  # 索引 2：配置页
        body.addWidget(self.stacked, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪：选船公司 + 单号类型，输入单号/箱号查询")
        # 右下角尺寸手柄：无边框窗口没法从边缘拖动缩放，放一个手柄让用户能自由拖大窗口
        # （拖动它即可放大/缩小整个窗口，放大后节点历史能看到更多行）
        self.statusBar().addPermanentWidget(QSizeGrip(self))

        # 启动时把已保存的配置回显到配置页
        self.refresh_config_form()

    def _build_sidebar(self):
        """左侧深石墨侧边栏：品牌区 + 导航（查询/配置）+ 底部版本号。"""
        sidebar = Sidebar()   # 背景由 Sidebar.paintEvent 自绘（深色+圆角）

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(12, 0, 12, 16)
        lay.setSpacing(4)

        # 品牌区：软件名 + 副标题（普通容器，无背景绘制 → 露出侧边栏深色）
        brand = QWidget()
        blay = QVBoxLayout(brand)
        blay.setContentsMargins(8, 20, 8, 14)
        blay.setSpacing(1)
        name = mk_label("物流查询助手", "BrandName", selectable=False)
        sub = mk_label("飞驼集装箱跟踪", "BrandSub", selectable=False)
        blay.addWidget(name)
        blay.addWidget(sub)
        lay.addWidget(brand)

        # 导航按钮：查询 / 批量查询 / 配置（互斥高亮，选中项左侧由样式强调）
        self.nav_btns = []
        for key, text in (("query", "查  询"), ("batch", "批量查询"), ("config", "配  置")):
            btn = QPushButton(text)
            btn.setObjectName("NavItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, k=key: self._switch_page(k))
            self.nav_btns.append(btn)
            lay.addWidget(btn)
        self.nav_btns[0].setChecked(True)

        lay.addStretch(1)

        # 底部版本号
        foot = mk_label("v2.0 · 简洁版", "SidebarFoot", selectable=False)
        foot.setAlignment(Qt.AlignCenter)
        lay.addWidget(foot)
        return sidebar

    def _switch_page(self, key):
        """点击侧边栏导航：切换右侧页面 + 更新导航高亮。

        参数：
            key: "query" 查询页 / "batch" 批量查询页 / "config" 配置页
        """
        idx = {"query": 0, "batch": 1, "config": 2}[key]
        self.stacked.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_btns):   # 只高亮当前页的导航按钮
            btn.setChecked(i == idx)

    # ================================================================
    # 第一页：查询页
    # ================================================================

    def _build_query_page(self):
        """【查询页】：放进滚动区：页面大标题 + 三张卡片（条件/概要/历史）。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        page.setObjectName("PageBg")   # 明确的浅灰背景（不再依赖全局 QWidget 规则）
        root = QVBoxLayout(page)
        root.setContentsMargins(24, 14, 24, 12)
        root.setSpacing(12)

        # 页面大标题 + 副标题合成一行（省下一行高度，让给下面的节点历史表格）
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(mk_label("物流查询", "PageTitle", selectable=False))
        head.addWidget(mk_label("提单号 / 箱号 填其一即可查询 · 数据来自飞驼",
                                "PageSub", selectable=False))
        head.addStretch(1)
        root.addLayout(head)

        root.addWidget(self._build_condition_card())
        self.summary_card = self._build_summary_card()
        root.addWidget(self.summary_card)

        # 「对接字段」和「节点历史」放进上下两栏的可拖动分隔条（QSplitter）：
        # 之前给两张表各自设 min/max 高度，结果整页最小高度超过窗口可视高度，
        # Qt 会把"可压缩"的对接字段表压到只剩表头（内容全看不见）。
        # 用分隔条后：两张表各有保底高度、总高由窗口决定，用户还能拖动分割线分配空间。
        self.fields_card = self._build_fields_card()
        self.nodes_card = self._build_table_card()
        self.table_split = QSplitter(Qt.Vertical)
        self.table_split.setObjectName("TableSplit")
        self.table_split.setHandleWidth(8)
        self.table_split.setChildrenCollapsible(False)      # 不允许被拖到完全消失
        self.table_split.addWidget(self.fields_card)
        self.table_split.addWidget(self.nodes_card)
        self.table_split.setSizes([170, 380])              # 初始：对接字段约3行 + 节点历史约8行
        root.addWidget(self.table_split, 1)

        scroll.setWidget(page)
        return scroll

    def _build_condition_card(self):
        """【查询条件】卡片：船司 + 单号类型二选一 + 单号输入 + 查询按钮。

        布局对齐图片：
          头部：左"查询条件"标题，右"单号类型"二选一（提单号BL/箱号）
          一行两列：船公司（下拉）| 单号输入 + 查询按钮（同行右侧）
        """
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 16, 24, 20)
        lay.setSpacing(14)

        # ---- 头部：左标题 + 右单号类型三选一 ----
        head = QHBoxLayout()
        t = mk_label("查询条件", "CardLabel")   # 字段名可选中复制
        head.addWidget(t)
        head.addStretch(1)
        head.addWidget(mk_label("单号类型", "FieldLabel"))
        self.rb_bl = QRadioButton("提单号 BL")
        self.rb_cn = QRadioButton("箱号")
        self.rb_bl.setChecked(True)   # 默认按提单号查
        # 切换类型时，联动更新输入框的提示文字
        for rb in (self.rb_bl, self.rb_cn):
            rb.toggled.connect(self._on_category_changed)
        head.addWidget(self.rb_bl)
        head.addWidget(self.rb_cn)
        lay.addLayout(head)

        # ---- 一行两列：船公司 | 单号(+查询按钮) ----
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(6)

        grid.addWidget(mk_label("船公司", "FieldLabel"), 0, 0)
        grid.addWidget(mk_label("单号", "FieldLabel"), 0, 1)

        self.combo_carrier = self._make_carrier_combo()
        self.input_no = QLineEdit()
        self.input_no.setClearButtonEnabled(True)
        self._on_category_changed()   # 初始化提示文字

        # 单号输入框 + 查询按钮放同一行，按钮靠右
        no_box = QWidget()
        no_lay = QHBoxLayout(no_box)
        no_lay.setContentsMargins(0, 0, 0, 0)
        no_lay.setSpacing(10)
        no_lay.addWidget(self.input_no, 1)
        self.btn_query = QPushButton("查询")
        self.btn_query.setObjectName("PrimaryBtn")
        self.btn_query.setFixedHeight(38)   # 与输入框同高
        self.btn_query.setStyleSheet(BUTTON_PRIMARY_QSS)   # 局部样式确保蓝色生效
        self.btn_query.setCursor(Qt.PointingHandCursor)
        self.btn_query.clicked.connect(self.on_query_clicked)
        no_lay.addWidget(self.btn_query)

        grid.addWidget(self.combo_carrier, 1, 0)
        grid.addWidget(no_box, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)

        lay.addLayout(grid)

        # 回车键也可以触发查询
        self.input_no.returnPressed.connect(self.on_query_clicked)
        return card

    def _on_category_changed(self):
        """单号类型切换时，更新输入框提示文字（告诉用户该输什么）。"""
        if self.rb_cn.isChecked():
            self.input_no.setPlaceholderText("请输入箱号，如 FFAU3658493")
        else:
            self.input_no.setPlaceholderText("请输入提单号")

    def _make_carrier_combo(self):
        """船公司下拉框：带"输入即搜索" + 失焦自动补全全称。"""
        combo = QComboBox()
        combo.setEditable(True)
        combo.setMinimumWidth(180)

        self._display_to_short = {}
        for short in sorted(CARRIERS.keys()):
            name_cn = CARRIERS[short]["name_cn"]
            display = f"{short} - {name_cn}"
            self._display_to_short[display] = short
            combo.addItem(display, short)

        completer = QCompleter(combo.model(), combo)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        combo.setCompleter(completer)

        # 补全时机：鼠标点到输入框以外的区域（失焦）时，把简称/中文名补成全称。
        # 注意不用"静止时间"方案——否则用户还没停手就一直补，体验不好。
        combo.lineEdit().editingFinished.connect(self._try_fill_carrier_fullname)

        idx = combo.findData("MSC")
        if idx >= 0:
            combo.setCurrentIndex(idx)
        return combo

    def _try_fill_carrier_fullname(self):
        """船公司自动补全全称：把"简称/中文名"替换成"简称 - 中文全称"。

        触发时机（不是按静止时间）：
          · 鼠标点击输入框以外的区域（下拉框失焦时 editingFinished 信号）
          · 点"查询"前兜底调用（先补全再组装查询参数）
          即：只要用户收了手要去点别的地方/查询，就先补全；正打字时不会被打断。

        规则（由易到难）：
          1. 已经是"简称 - 全称"格式 → 不动；
          2. 输入恰好是某船司简称（大小写不敏感）→ 补成"简称 - 中文全称"；
          3. 输入与某船司中文名完全一致 → 补成全称；
          4. 都匹配不到 → 保持原样不动（查询时会提示"没找到该船司"）。
        """
        text = self.combo_carrier.currentText().strip()
        if not text:
            return  # 空的不用管
        if self._display_to_short.get(text):
            return  # 已经是标准格式，不用动

        up = text.upper()
        if up in CARRIERS:   # 情况2：输入的是简称
            self.combo_carrier.setCurrentText(f"{up} - {CARRIERS[up]['name_cn']}")
            return
        for short, info in CARRIERS.items():   # 情况3：输入的是中文全名
            if info["name_cn"] == text:
                self.combo_carrier.setCurrentText(f"{short} - {info['name_cn']}")
                return
        # 情况4：没匹配到，什么都不做（返回空补全）

    def _build_summary_card(self):
        """【运单概要】卡片：查询结果的关键信息（文本可选中复制）。

        结构对齐设计稿：
          头部：左"运单概要"，右单号（等宽灰字）
          总状态徽章行 → 分隔线
          最新节点 3 列（节点/时间/地点）+ 下一节点(预计) 橙色行
          分隔线 → 其他信息 4 列（船司/船名航次/航线/更新时间）
        """
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        # 紧凑布局：缩小内边距和行距，把垂直空间让给下方的节点历史表格
        lay.setContentsMargins(20, 10, 20, 12)
        lay.setSpacing(8)

        # ---- 头部：标题 + 单号 ----
        head = QHBoxLayout()
        head.addWidget(mk_label("运单概要", "CardTitle"))   # 字段名可选中复制
        head.addStretch(1)
        self.lbl_bill_no = mk_label("—", "MonoValue")
        self.lbl_bill_no.setStyleSheet("color:#64748b; background:transparent; font-size:13px;")
        head.addWidget(self.lbl_bill_no)
        lay.addLayout(head)

        # ---- 行1：总状态徽章 ----
        row_status = QHBoxLayout()
        row_status.setSpacing(10)
        row_status.addWidget(mk_label("总状态", "SummaryKey"))
        self.lbl_status = mk_label("—", "StatusBig")
        self.lbl_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row_status.addWidget(self.lbl_status)
        self.lbl_status_detail = mk_label("", "FieldLabel")
        row_status.addWidget(self.lbl_status_detail)
        row_status.addStretch(1)
        lay.addLayout(row_status)

        # ---- 分隔线 ----
        lay.addWidget(self._make_h_sep())

        # ---- 行2：最新节点 3 列（节点/时间/地点） ----
        grid3 = QGridLayout()
        grid3.setHorizontalSpacing(24)
        grid3.setVerticalSpacing(2)
        grid3.addWidget(mk_label("最新节点", "SummaryKey"), 0, 0)
        grid3.addWidget(mk_label("时间", "SummaryKey"), 0, 1)
        grid3.addWidget(mk_label("地点", "SummaryKey"), 0, 2)
        self.lbl_current = mk_label("—", "SummaryValue")
        self.lbl_current_time = mk_label("—", "MonoValue")
        self.lbl_current_place = mk_label("—", "SummaryValue")
        grid3.addWidget(self.lbl_current, 1, 0)
        grid3.addWidget(self.lbl_current_time, 1, 1)
        grid3.addWidget(self.lbl_current_place, 1, 2)
        grid3.setColumnStretch(1, 1)
        grid3.setColumnStretch(0, 2)
        grid3.setColumnStretch(2, 2)
        lay.addLayout(grid3)

        # ---- 行3：下一节点（预计）—— 橙色区分"还没发生" ----
        grid_next = QGridLayout()
        grid_next.setHorizontalSpacing(24)
        grid_next.setVerticalSpacing(2)
        lbl_next = mk_label("下一节点(预计)", "SummaryKey")
        grid_next.addWidget(lbl_next, 0, 0)
        grid_next.addWidget(mk_label("时间", "SummaryKey"), 0, 1)
        grid_next.addWidget(mk_label("地点", "SummaryKey"), 0, 2)
        self.lbl_next = mk_label("—", "SummaryValue")
        self.lbl_next_time = mk_label("—", "MonoValue")
        self.lbl_next_place = mk_label("—", "SummaryValue")
        # 预计节点统统橙色显示，一眼看出"还没发生"
        for x in (self.lbl_next, self.lbl_next_time, self.lbl_next_place):
            x.setStyleSheet(f"color:#d97706; background:transparent; {('font-weight:600;' if x is not self.lbl_next_time else 'font-weight:600;')}")
        grid_next.addWidget(self.lbl_next, 1, 0)
        grid_next.addWidget(self.lbl_next_time, 1, 1)
        grid_next.addWidget(self.lbl_next_place, 1, 2)
        grid_next.setColumnStretch(0, 2)
        grid_next.setColumnStretch(1, 1)
        grid_next.setColumnStretch(2, 2)
        lay.addLayout(grid_next)

        # ---- 分隔线 ----
        lay.addWidget(self._make_h_sep())

        # ---- 行4：其他信息 4 列（船司/船名航次/航线/更新时间） ----
        grid4 = QGridLayout()
        grid4.setHorizontalSpacing(24)
        grid4.setVerticalSpacing(2)
        for i, label in enumerate(["船司", "船名/航次", "航线", "更新时间"]):
            grid4.addWidget(mk_label(label, "SummaryKey"), 0, i)
        self.lbl_carrier = mk_label("—", "SummaryValue")
        self.lbl_vessel = mk_label("—", "MonoValue")
        self.lbl_route = mk_label("—", "SummaryValue")
        self.lbl_update = mk_label("—", "MonoValue")
        for i, w in enumerate([self.lbl_carrier, self.lbl_vessel, self.lbl_route, self.lbl_update]):
            grid4.addWidget(w, 1, i)
        for i in range(4):
            grid4.setColumnStretch(i, 1)
        lay.addLayout(grid4)

        return card

    def _build_fields_card(self):
        """【对接字段】卡片：按《飞驼对接数据》规范展示 32 个业务字段。

        结构：
          头部：左"对接字段"标题，右提示文字
          表格：4 列（环节 / 字段名称 / 取值 / 说明），按 起运港→目的港→中转港 分组，
                环节列用底色区分，字段名和取值都可选中复制。
        """
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 16, 24, 20)
        lay.setSpacing(10)

        # 头部：标题 + 计数提示 + 收起/展开（收起后把高度让给下方"节点历史"）
        head = QHBoxLayout()
        head.addWidget(mk_label("对接字段", "CardTitle"))
        head.addSpacing(12)
        self.lbl_fields_count = mk_label("", "FieldLabel")
        head.addWidget(self.lbl_fields_count)
        head.addStretch(1)
        self.btn_toggle_fields = QPushButton("收起字段")
        self.btn_toggle_fields.setFixedHeight(26)
        self.btn_toggle_fields.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_fields.clicked.connect(self._toggle_fields_table)
        head.addWidget(self.btn_toggle_fields)
        lay.addLayout(head)
        self._fields_collapsed = False

        # 4 列表格（环节 / 字段名称 / 取值 / 说明）
        self.table_fields = CopyableTable(0, 4)
        self.table_fields.setHorizontalHeaderLabels(["环节", "字段名称", "取值", "说明"])
        self.table_fields.setEditTriggers(QAbstractItemView.NoEditTriggers)          # 只读
        self.table_fields.setSelectionBehavior(QAbstractItemView.SelectItems)        # 单元格级选择
        self.table_fields.setSelectionMode(QAbstractItemView.ExtendedSelection)      # 支持多选复制
        self.table_fields.verticalHeader().setVisible(False)
        self.table_fields.horizontalHeader().setStretchLastSection(True)
        self.table_fields.setShowGrid(False)
        self.table_fields.setWordWrap(False)
        # 列宽：环节 80 / 字段名称 140 / 取值 210 / 说明(拉伸)
        for i, w in enumerate([80, 140, 210, 260]):
            self.table_fields.setColumnWidth(i, w)
        # 保底高度：这张表本身可滚动，保底约 3 行，避免被其它块挤到看不见内容
        self.table_fields.setMinimumHeight(100)
        lay.addWidget(self.table_fields, 1)
        return card

    def _toggle_fields_table(self):
        """收起/展开"对接字段"表：收起后腾出的高度直接让给下方"节点历史"表格。"""
        self._fields_collapsed = not getattr(self, "_fields_collapsed", False)
        self.table_fields.setVisible(not self._fields_collapsed)
        self.btn_toggle_fields.setText("展开字段" if self._fields_collapsed else "收起字段")
        # 同步调整分隔条：收起时只给"对接字段"卡留标题栏高度，其余全给节点历史
        part = getattr(self, "table_split", None)
        if part is not None:
            total = sum(part.sizes()) or 530
            keep = 70 if self._fields_collapsed else 190
            part.setSizes([keep, max(200, total - keep)])

    def _fill_fields_table(self, fields):
        """把对接字段列表填进表格（按环节分组，空值显示"—"，环节列加底色）。"""
        # 环节 → 底色（浅色区分三大环节，不干扰正文阅读）
        section_colors = {
            "起运港": ("#eef4ff", "#2f6fed"),   # 起运港：浅蓝
            "目的港": ("#e9f7ef", "#16a34a"),   # 目的港：浅绿
            "中转港": ("#fdf4e9", "#d97706"),   # 中转港：浅橙
            "尾程卡车": ("#fdf2f8", "#db2777"),  # 尾程卡车：浅粉
        }
        fields = fields or []
        self.lbl_fields_count.setText(f"共 {len(fields)} 个对接字段")
        self.table_fields.setRowCount(len(fields))
        for row, f in enumerate(fields):
            bg, fg = section_colors.get(f.get("环节", ""), ("#f8f9fb", "#6b7280"))

            # 环节列：底色区分
            it_section = QTableWidgetItem(f.get("环节", ""))
            it_section.setBackground(QColor(bg))
            it_section.setForeground(QColor(fg))
            it_section.setTextAlignment(Qt.AlignCenter)
            self.table_fields.setItem(row, 0, it_section)

            # 字段名称列
            it_cn = QTableWidgetItem(f.get("字段名称", ""))
            it_cn.setTextAlignment(Qt.AlignCenter)
            self.table_fields.setItem(row, 1, it_cn)

            # 取值列：空值显示"—"
            it_val = QTableWidgetItem(f.get("值") or "—")
            it_val.setTextAlignment(Qt.AlignCenter)
            self.table_fields.setItem(row, 2, it_val)

            # 说明列
            it_note = QTableWidgetItem(f.get("说明", ""))
            self.table_fields.setItem(row, 3, it_note)

    def _make_h_sep(self):
        """一条浅浅的分隔线（QFrame 画横线），用于卡片内分区。"""
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color:#eef1f6; background:#eef1f6; border:none; max-height:1px;")
        return sep

    def _build_table_card(self):
        """【节点历史】卡片：一个表格，展示每个箱子每一步的物流节点。"""
        card = QFrame()
        card.setObjectName("Card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 16, 24, 20)
        lay.setSpacing(10)

        # 头部：标题 + 计数（左对齐，与运单概要卡片一致；只有表格内容居中）
        head = QHBoxLayout()
        t = mk_label("节点历史", "CardTitle")
        self.lbl_node_count = mk_label("", "FieldLabel")
        head.addWidget(t)
        head.addSpacing(12)
        head.addWidget(self.lbl_node_count)
        head.addStretch(1)
        lay.addLayout(head)

        # 支持多选单元格 + Ctrl+C 复制的表格
        self.table = CopyableTable(0, len(NODE_HEADERS))
        self.table.setHorizontalHeaderLabels(NODE_HEADERS)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)          # 只读，不许改单元格
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)        # 单元格级选择（可框选）
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)      # 支持拖框选/Ctrl 多选
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignCenter)     # 表头居中
        self.table.setShowGrid(False)                          # 对齐设计稿：无竖线，只有行分隔
        self.table.setAlternatingRowColors(False)
        self.table.setWordWrap(False)                          # 单元格不换行，保持行高整齐
        # 各列宽度（时间/节点/实际预计/地点/箱号/运输方式/船名航次）
        # 运输方式列特意加宽到 110：太窄时彩色标签文字会被截断、显示不全
        for i, w in enumerate([150, 110, 80, 130, 130, 110, 150]):
            self.table.setColumnWidth(i, w)
        # 保底高度：至少能显示约 6 行节点；实际能显示多少由分隔条/窗口高度决定
        self.table.setMinimumHeight(200)

        lay.addWidget(self.table, 1)
        return card

    # ================================================================
    # 第二页：批量查询页
    # ================================================================

    def _build_batch_page(self):
        """【批量查询】页：导入 Excel 或人工填写待查列表，逐条查询，结果可导出 Excel。

        布局：
          输入卡：导入 Excel 按钮 + 多行文本框（每行"船司 提单号 箱号"）+ 开始/停止按钮
          进度行：当前进度提示（第几条/共几条）
          结果表格：每行一条运单（单号、船司、状态 + 36 个对接字段，可横向滚动）
          导出按钮：把结果表格导成 Excel（.xlsx）
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        page.setObjectName("PageBg")
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        # 页面大标题
        root.addWidget(mk_label("批量查询", "PageTitle", selectable=False))
        root.addWidget(mk_label("支持导入 Excel 模板（船公司/提单号/箱号）或人工填写，点【开始批量查询】执行",
                                "PageSub", selectable=False))

        # ---------- 输入卡 ----------
        input_card = QFrame()
        input_card.setObjectName("Card")
        in_lay = QVBoxLayout(input_card)
        in_lay.setContentsMargins(24, 16, 24, 20)
        in_lay.setSpacing(10)

        head = QHBoxLayout()
        head.addWidget(mk_label("待查列表", "CardTitle"))
        head.addStretch(1)
        head.addWidget(mk_label("每行一条：船司简称 + 提单号 + 箱号（箱号可空）", "FieldLabel", selectable=False))
        in_lay.addLayout(head)

        # 顶部按钮行：下载模板 / 导入 Excel
        import_row = QHBoxLayout()
        import_row.setSpacing(10)
        self.btn_download_tpl = QPushButton("下载模板")
        self.btn_download_tpl.setObjectName("GhostBtn")
        self.btn_download_tpl.setFixedHeight(34)
        self.btn_download_tpl.setCursor(Qt.PointingHandCursor)
        self.btn_download_tpl.clicked.connect(self.on_download_template)
        import_row.addWidget(self.btn_download_tpl)

        self.btn_import_excel = QPushButton("导入 Excel")
        self.btn_import_excel.setObjectName("GhostBtn")
        self.btn_import_excel.setFixedHeight(34)
        self.btn_import_excel.setCursor(Qt.PointingHandCursor)
        self.btn_import_excel.clicked.connect(self.on_import_excel)
        import_row.addWidget(self.btn_import_excel)

        # 多维表格更新：一键完成"读飞书多维表格 → 清洗 → 查询 → 回写 → 群通知"
        self.btn_feishu_update = QPushButton("多维表格更新")
        self.btn_feishu_update.setObjectName("GhostBtn")
        self.btn_feishu_update.setFixedHeight(34)
        self.btn_feishu_update.setCursor(Qt.PointingHandCursor)
        self.btn_feishu_update.clicked.connect(self.on_feishu_update)
        import_row.addWidget(self.btn_feishu_update)
        import_row.addWidget(mk_label(
            "模板列：船公司 / 提单号 / 箱号（也可人工在下方粘贴）", "FieldLabel", selectable=False))
        import_row.addStretch(1)
        in_lay.addLayout(import_row)

        self.txt_batch = QPlainTextEdit()
        self.txt_batch.setPlaceholderText(
            "示例（每行一条）：\nMSC 177MASASS106510A TCKU1559530\nONE FFAU3658493\nHPL HLCUSZX2608CGDQ6"
        )
        self.txt_batch.setMinimumHeight(130)
        in_lay.addWidget(self.txt_batch)

        # 操作按钮行：开始 / 停止 / 导出 Excel
        op_row = QHBoxLayout()
        op_row.setSpacing(10)
        self.btn_batch_start = QPushButton("开始批量查询")
        self.btn_batch_start.setObjectName("PrimaryBtn")
        self.btn_batch_start.setFixedHeight(38)
        self.btn_batch_start.setStyleSheet(BUTTON_PRIMARY_QSS)
        self.btn_batch_start.setCursor(Qt.PointingHandCursor)
        self.btn_batch_start.clicked.connect(self.on_batch_start)
        op_row.addWidget(self.btn_batch_start)

        self.btn_batch_export = QPushButton("导出 Excel")
        self.btn_batch_export.setObjectName("GhostBtn")
        self.btn_batch_export.setFixedHeight(38)
        self.btn_batch_export.setCursor(Qt.PointingHandCursor)
        self.btn_batch_export.setEnabled(False)     # 没结果前不可导出
        self.btn_batch_export.clicked.connect(self.on_batch_export)
        op_row.addWidget(self.btn_batch_export)

        self.lbl_batch_progress = mk_label("", "FieldLabel")
        op_row.addWidget(self.lbl_batch_progress)
        op_row.addStretch(1)
        in_lay.addLayout(op_row)
        root.addWidget(input_card)

        # ---------- 结果表格 ----------
        res_card = QFrame()
        res_card.setObjectName("Card")
        res_lay = QVBoxLayout(res_card)
        res_lay.setContentsMargins(24, 16, 24, 20)
        res_lay.setSpacing(10)

        res_head = QHBoxLayout()
        res_head.addWidget(mk_label("批量结果", "CardTitle"))
        self.lbl_batch_count = mk_label("", "FieldLabel")
        res_head.addWidget(self.lbl_batch_count)
        res_head.addStretch(1)
        res_lay.addLayout(res_head)

        # 结果表：船公司 / 提单号 / 箱号 / 状态 / 总状态 + 36 个对接字段（可横向滚动查看）
        self.table_batch = CopyableTable(0, 5)
        self.table_batch.setHorizontalHeaderLabels(["船公司", "提单号", "箱号", "状态", "总状态"])
        self.table_batch.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_batch.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_batch.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_batch.verticalHeader().setVisible(False)
        self.table_batch.horizontalHeader().setStretchLastSection(False)
        self.table_batch.setShowGrid(False)
        self.table_batch.setWordWrap(False)
        # 前五列固定宽度，对接字段列窄一点（显示值，导出 Excel 才是完整用法）
        for i, w in enumerate([120, 150, 130, 100, 110]):
            self.table_batch.setColumnWidth(i, w)
        res_lay.addWidget(self.table_batch, 1)
        root.addWidget(res_card, 1)

        # 保存批量结果（内存里，导出时用）
        self.batch_results = []      # [{"船公司","提单号","箱号","状态","总状态","fields":[...]}, ...]
        self.batch_worker = None     # 批量查询线程引用
        self.feishu_worker = None    # 多维表格更新线程引用

        scroll.setWidget(page)
        return scroll

    def on_batch_start(self):
        """点"开始批量查询"：解析多行文本 → 后台线程逐个查询。"""
        if self.batch_worker and self.batch_worker.isRunning():
            # 正在跑：点按钮 = 停止（线程下次循环会因标志位退出）
            self.batch_worker.requestInterruption()
            self.btn_batch_start.setEnabled(False)
            self.lbl_batch_progress.setText("正在停止...")
            return

        # ---- 解析多行输入（每行：船司 提单号 箱号，箱号可空） ----
        lines = self.txt_batch.toPlainText().strip().splitlines()
        payloads = []
        errors = []
        for i, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue
            parts = line.replace(",", " ").replace("\t", " ").split()
            if len(parts) < 2:
                errors.append(f"第 {i} 行格式不对：{line}（应为：船司简称 提单号 箱号）")
                continue
            carrier_short = parts[0].upper()
            if not get_carrier_info(carrier_short):
                errors.append(f"第 {i} 行船司「{parts[0]}」不在 113 家列表里")
                continue
            # 三字段：提单号 + 箱号 都有；两字段：只有一个号（可能是提单号或箱号）
            if len(parts) >= 3:
                bill_no = parts[1]
                container_no = parts[2]
            else:
                no = parts[1]
                # 长得像箱号（4字母+7数字）就当箱号，否则当提单号
                is_container = _looks_like_container(no)
                bill_no = "" if is_container else no
                container_no = no if is_container else ""
            payloads.append({
                "carrier_short": carrier_short,
                "bill_no": bill_no,
                "container_no": container_no,
            })

        if errors:
            QMessageBox.warning(self, "格式有误", "\n".join(errors[:8]))
        if not payloads:
            return

        # ---- 清空旧结果，开始逐条查询 ----
        self.batch_results = []
        self.table_batch.setRowCount(0)
        self.table_batch.setColumnCount(5)   # 固定前五列（船公司/提单号/箱号/状态/总状态）
        self.table_batch.setHorizontalHeaderLabels(["船公司", "提单号", "箱号", "状态", "总状态"])
        self.lbl_batch_count.setText("")
        self.btn_batch_export.setEnabled(False)
        self.btn_batch_start.setText("停止查询")
        self.lbl_batch_progress.setText(f"开始查询，共 {len(payloads)} 条...")

        self.batch_worker = BatchQueryWorker(payloads)
        self.batch_worker.progress_signal.connect(self.on_batch_progress)
        self.batch_worker.finished_signal.connect(self.on_batch_finished)
        self.batch_worker.stage_signal.connect(
            lambda s: self.lbl_batch_progress.setText(s))
        self.batch_worker.start()

    def on_download_template(self):
        """点"下载模板"：生成批量查询模板 Excel（列：船公司/提单号/箱号），让用户选位置保存。"""
        default_name = "批量查询模板.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "下载批量查询模板", default_name, "Excel 文件 (*.xlsx)"
        )
        if not path:
            return
        try:
            write_batch_template(path)
        except Exception as exc:
            QMessageBox.warning(self, "下载失败", f"生成模板出错：{exc}")
            return
        QMessageBox.information(self, "下载成功", f"模板已保存到：\n{path}")
        self.statusBar().showMessage(f"模板已保存：{path}")

    def on_import_excel(self):
        """点"导入 Excel"：读取模板文件（列：船公司/提单号/箱号），填入待查文本框。

        模板第一行是表头；按表头找列，找不到就用前 3 列顺序对应。
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "选择批量查询模板 Excel", "", "Excel 文件 (*.xlsx *.xls)"
        )
        if not path:
            return
        try:
            rows = read_batch_template(path)
        except Exception as exc:
            QMessageBox.warning(self, "导入失败", f"读取 Excel 出错：{exc}")
            return

        if not rows:
            QMessageBox.warning(self, "导入失败", "Excel 里没有数据（从第二行起每行一条）。")
            return

        # 拼成"船司 提单号 箱号"文本填进文本框（保留已有的手动内容在前？直接覆盖，因为导入是替换）
        lines = []
        for carrier, bill, container in rows:
            carrier = str(carrier or "").strip().upper()
            bill = str(bill or "").strip()
            container = str(container or "").strip()
            if not carrier:
                continue
            parts = [carrier]
            if bill:
                parts.append(bill)
            if container:
                parts.append(container)
            lines.append(" ".join(parts))
        if not lines:
            QMessageBox.warning(self, "导入失败", "Excel 里没有可用的船公司数据。")
            return

        self.txt_batch.setPlainText("\n".join(lines))
        self.statusBar().showMessage(f"已从 Excel 导入 {len(lines)} 条待查记录，可点击【开始批量查询】")
        QMessageBox.information(self, "导入成功", f"已导入 {len(lines)} 条记录到待查列表，请核对后点击【开始批量查询】。")

    def on_batch_progress(self, done, total):
        """批量查询进度更新（Worker 每完成 progress_step 条发一次）。"""
        self.lbl_batch_progress.setText(f"查询进度：{done}/{total}")
        self.statusBar().showMessage(f"批量查询 {done}/{total}，请稍候...")

    def on_batch_finished(self, results, ok_count):
        """批量查询全部结束：把结果一次性填进表格，恢复按钮、开放导出。

        参数：
            results: 按输入顺序排列的结果列表，每项 {"result":..., "payload":...}
            ok_count: 查询成功（有数据）的条数
        """
        self.batch_worker = None
        self.btn_batch_start.setText("开始批量查询")
        self.btn_batch_start.setEnabled(True)

        # 把结果整理成导出用的行（保留模板原字段，空值留空）
        self.batch_results = []
        for item in results:
            result = item["result"]
            payload = item["payload"]
            s = result.get("summary") or {}
            fields = result.get("fields") or []
            self.batch_results.append({
                "船公司": str(payload.get("carrier_short") or "").strip(),
                "提单号": str(payload.get("bill_no") or "").strip(),
                "箱号": str(payload.get("container_no") or "").strip(),
                "状态": result.get("status", ""),
                "总状态": s.get("statusCn") or "",
                "fields": fields,
            })

        # 一次性填表（几千条也一次性 setRowCount，比逐行刷新快得多）
        total = len(self.batch_results)
        self.table_batch.setRowCount(total)
        self.table_batch.setColumnCount(5)
        self.table_batch.setHorizontalHeaderLabels(["船公司", "提单号", "箱号", "状态", "总状态"])
        for r, row in enumerate(self.batch_results):
            for c, key in enumerate(["船公司", "提单号", "箱号", "状态", "总状态"]):
                it = QTableWidgetItem(str(row[key]))
                it.setTextAlignment(Qt.AlignCenter)
                self.table_batch.setItem(r, c, it)
            # 对接字段动态加列（表头用"环节-字段名"，如"起运港-截单时间"）
            for fi, f in enumerate(row["fields"]):
                col = 5 + fi
                if self.table_batch.columnCount() < col + 1:
                    self.table_batch.setColumnCount(col + 1)
                    self.table_batch.setHorizontalHeaderItem(
                        col, QTableWidgetItem(f"{f.get('环节','')}-{f.get('字段名称','')}")
                    )
                    self.table_batch.setColumnWidth(col, 160)
                it = QTableWidgetItem(f.get("值") or "")
                it.setTextAlignment(Qt.AlignCenter)
                self.table_batch.setItem(r, col, it)

        self.lbl_batch_count.setText(f"共 {total} 条（成功 {ok_count} 条）")
        self.lbl_batch_progress.setText(f"全部完成：{total} 条")
        self.btn_batch_export.setEnabled(total > 0)
        self.statusBar().showMessage(f"批量查询完成：{total} 条，可导出 Excel")

    def on_batch_export(self):
        """点"导出 Excel"：把批量结果（含全部对接字段）导出成 .xlsx 文件。"""
        if not self.batch_results:
            QMessageBox.information(self, "提示", "还没有查询结果，先做批量查询再导出。")
            return

        # 选择保存位置
        default_name = f"批量查询结果_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Excel", default_name, "Excel 文件 (*.xlsx)"
        )
        if not path:
            return

        try:
            export_batch_to_excel(self.batch_results, path)
        except ImportError:
            QMessageBox.warning(
                self, "缺少依赖",
                "导出 Excel 需要 openpyxl 库。请在命令行执行：pip install openpyxl"
            )
            return
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", f"导出时出错：{exc}")
            return

        QMessageBox.information(self, "导出成功", f"已导出到：\n{path}")
        self.statusBar().showMessage(f"已导出 Excel：{path}")

    # ================================================================
    # 多维表格更新（飞书多维表格一键读取→清洗→查询→回写）
    # ================================================================

    def on_feishu_update(self):
        """点"多维表格更新"：校验配置 → 启动后台线程执行全流程。

        运行中再点一次 = 请求停止（正在跑的查询查完这批就停，已查完的照常回写）。
        """
        if self.feishu_worker and self.feishu_worker.isRunning():
            self.feishu_worker.requestInterruption()
            self.btn_feishu_update.setEnabled(False)
            self.lbl_batch_progress.setText("正在停止多维表格更新...")
            return

        # ---- 校验飞书配置（没填就引导去配置页，不瞎跑） ----
        fs = config.get_config().get("feishu", {})
        missing = []
        if not fs.get("app_id"):
            missing.append("App ID")
        if not fs.get("app_secret"):
            missing.append("App Secret")
        if not fs.get("table_link"):
            missing.append("多维表格链接")
        if missing:
            QMessageBox.warning(
                self, "飞书配置未填写",
                "请先到【配置】页 → 系统配置 → 飞书配置，填写：\n"
                + "、".join(missing) + "\n\n保存后再点【多维表格更新】。")
            self._switch_page("config")
            return

        # ---- 启动后台线程（全流程在 FeishuUpdateWorker 里跑，不卡界面） ----
        self.btn_feishu_update.setText("停止更新")
        self.lbl_batch_progress.setText("正在启动...")
        self.statusBar().showMessage("多维表格更新执行中...")
        self.feishu_worker = FeishuUpdateWorker(fs)
        self.feishu_worker.stage_signal.connect(self.on_feishu_stage)
        self.feishu_worker.progress_signal.connect(self.on_batch_progress)
        self.feishu_worker.finished_signal.connect(self.on_feishu_finished)
        self.feishu_worker.start()

    def on_feishu_stage(self, text):
        """后台线程汇报阶段变化：显示到进度标签和状态栏。"""
        self.lbl_batch_progress.setText(text)
        self.statusBar().showMessage(text)

    def on_feishu_finished(self, payload):
        """后台线程结束：恢复按钮，弹窗展示统计（或错误原因）。"""
        self.btn_feishu_update.setEnabled(True)
        self.btn_feishu_update.setText("多维表格更新")
        if payload.get("error"):
            self.lbl_batch_progress.setText(f"多维表格更新失败：{payload['error']}")
            QMessageBox.warning(self, "多维表格更新失败", str(payload["error"]))
            self.statusBar().showMessage("多维表格更新失败")
            return
        if payload.get("total", 0) == 0:
            self.lbl_batch_progress.setText("视图内没有记录，无需处理")
            QMessageBox.information(self, "多维表格更新", "视图内没有记录，无需处理。")
            return
        # 正常完成：展示统计
        m, s = divmod(payload.get("elapsed", 0), 60)
        summary = (
            f"视图共 {payload['total']} 条\n"
            f"查询 {payload['queried']} 条（有数据 {payload['ok']} 条）\n"
            f"直接标记 {payload['direct']} 条（参数错误/无法获知船公司代码）\n"
            f"回写 {payload['written']} 条，耗时 {m} 分 {s} 秒"
        )
        self.lbl_batch_progress.setText(
            f"完成：{payload['total']} 条（查询 {payload['queried']}/"
            f"有数据 {payload['ok']}/标记 {payload['direct']}）")
        QMessageBox.information(self, "多维表格更新完成", summary)
        self.statusBar().showMessage("多维表格更新完成")

    # ================================================================
    # 第三页：配置页
    # ================================================================

    def _build_config_page(self):
        """【配置】页：改飞驼 Token + 预留飞书配置（布局对齐图片）。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        page = QWidget()
        page.setObjectName("PageBg")   # 明确的浅灰背景（不再依赖全局 QWidget 规则）
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        # 页面大标题
        root.addWidget(mk_label("配置", "PageTitle", selectable=False))
        root.addWidget(mk_label("修改后保存即生效（写入 config.json，无需改代码）",
                                "PageSub", selectable=False))

        # 页内两个子页签：系统配置 / 飞驼接口映射
        # 拉伸系数 1：窗口变大时 Tab 跟着长高（否则被下方 stretch 吸收，子页不变）
        self.tabs_config = QTabWidget()
        self.tabs_config.addTab(self._build_system_config_tab(), "系统配置")
        self.tabs_config.addTab(self._build_mapping_tab(), "飞驼接口映射")
        self.tabs_config.addTab(self._build_feishu_mapping_tab(), "飞书接口映射")
        root.addWidget(self.tabs_config, 1)

        # ---------- 保存按钮 ----------
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_save_config = QPushButton("保存配置")
        self.btn_save_config.setObjectName("PrimaryBtn")
        self.btn_save_config.setFixedHeight(38)
        self.btn_save_config.setStyleSheet(BUTTON_PRIMARY_QSS)
        self.btn_save_config.setCursor(Qt.PointingHandCursor)
        self.btn_save_config.clicked.connect(self.on_save_config)
        btn_row.addWidget(self.btn_save_config)
        root.addLayout(btn_row)

        # 不放 addStretch(1)：tabs 已拉伸填满，多余空间都给子页内容
        scroll.setWidget(page)
        return scroll

    def _build_system_config_tab(self):
        """【系统配置】子页：飞驼账号密码（自动换取 Token 用）+ 飞书预留配置。"""
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 16, 0, 8)
        root.setSpacing(16)

        # ---------- 飞驼配置 ----------
        fw_card = QFrame()
        fw_card.setObjectName("Card")
        fw_lay = QVBoxLayout(fw_card)
        fw_lay.setContentsMargins(24, 16, 24, 20)
        fw_lay.setSpacing(10)
        fw_lay.addWidget(mk_label("飞驼配置", "CardTitle"))

        # API 账号一行
        row_cred = QHBoxLayout()
        row_cred.setSpacing(10)
        row_cred.addWidget(mk_label("API 账号", "FieldLabel"))
        self.input_client_id = QLineEdit()
        self.input_client_id.setPlaceholderText("飞驼 API 账号（clientId）")
        row_cred.addWidget(self.input_client_id, 1)
        fw_lay.addLayout(row_cred)

        # API 密码一行
        row_secret = QHBoxLayout()
        row_secret.setSpacing(10)
        row_secret.addWidget(mk_label("API 密码", "FieldLabel"))
        self.input_secret = QLineEdit()
        self.input_secret.setEchoMode(QLineEdit.Password)   # 密码默认密文
        self.input_secret.setPlaceholderText("飞驼 API 密码（secret）")
        self.chk_show_secret = QCheckBox("显示")
        self.chk_show_secret.toggled.connect(
            lambda c: self.input_secret.setEchoMode(QLineEdit.Normal if c else QLineEdit.Password)
        )
        row_secret.addWidget(self.input_secret, 1)
        row_secret.addWidget(self.chk_show_secret)
        fw_lay.addLayout(row_secret)

        # 温馨提示（灰字）
        fw_lay.addWidget(mk_label(
            "填写 API 账号+密码后，程序自动获取 Token（每 12 小时自动刷新，失效自动重取），无需手动填 Token。",
            "FieldLabel", selectable=False))
        root.addWidget(fw_card)

        # ---------- 飞书配置（预留） ----------
        fs_card = QFrame()
        fs_card.setObjectName("Card")
        fs_lay = QVBoxLayout(fs_card)
        fs_lay.setContentsMargins(24, 16, 24, 20)
        fs_lay.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(mk_label("飞书配置", "CardTitle"))
        head.addSpacing(10)
        head.addWidget(mk_label("用于【批量查询】页的\"多维表格更新\"：读运单、回写结果、群通知",
                                "FieldLabel", selectable=False))
        head.addStretch(1)
        fs_lay.addLayout(head)

        # 四行"标签右对齐 + 输入框"的网格（对齐设计稿 110px 标签列）
        form = QGridLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)

        rows = [
            ("飞书 App ID", self._mk_secret_line(None, "飞书开放平台自建应用的 App ID", False)),
            ("App Secret", self._mk_secret_line(None, "飞书开放平台自建应用的 App Secret", True)),
            ("多维表格链接", self._mk_secret_line(None, "https://xxx.feishu.cn/base/xxx?table=tblxxx&view=vewxxx", False)),
            ("机器人 Webhook", self._mk_secret_line(None, "https://open.feishu.cn/open-apis/bot/v2/hook/xxx（不填则不通知）", False)),
            ("签名校验密钥", self._mk_secret_line(None, "群机器人开启\"签名校验\"时填，未开启留空", True)),
        ]
        for i, (label, line) in enumerate(rows):
            lab = mk_label(label, "FieldLabel")
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            form.addWidget(lab, i, 0)
            form.addWidget(line, i, 1)
        self.input_app_id, self.input_app_secret, self.input_table_link, self.input_webhook_url, \
            self.input_webhook_secret = \
            [r[1] for r in rows]

        fs_lay.addLayout(form)
        root.addWidget(fs_card)

        root.addStretch(1)
        return page

    def _build_mapping_tab(self):
        """【飞驼接口映射】子页：36 个对接字段的取值来源映射（可修改）。

        表格说明：
          · 环节 / 字段名称：固定，不许改（英文描述鼠标悬停字段名可见）
          · 取值来源：可编辑，用"-"连接下层字段，如 places-type2-etd
        """
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 16, 0, 8)
        root.setSpacing(12)

        # 提示说明（灰字，教用户怎么改；允许换行，避免长文本把页面最小宽度撑大）
        tip = mk_label(
            "取值来源格式（用 - 连接）：terminalplan-open | places-type2-etd | "
            "containers-desc-进场-eventTime | containers-code-PASS-eventTime | "
            "containers-desc-actual-提柜(货)-eventTime | "
            "containers-desc-contains-查验-eventTime | places-type4-vessel/voyage",
            "FieldLabel", selectable=False)
        tip.setWordWrap(True)
        root.addWidget(tip)

        # 映射表格：4 列（环节/字段名称/取值来源/英文描述）
        mapping = config.get_field_mapping()
        self.table_mapping = CopyableTable(0, 4)
        self.table_mapping.setHorizontalHeaderLabels(["环节", "字段名称", "取值来源", "英文描述"])
        self.table_mapping.setEditTriggers(QAbstractItemView.DoubleClicked)   # 双击才能编辑取值来源
        self.table_mapping.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_mapping.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_mapping.verticalHeader().setVisible(False)
        self.table_mapping.horizontalHeader().setStretchLastSection(False)
        self.table_mapping.setShowGrid(False)
        self.table_mapping.setWordWrap(False)
        # 取消表格最小宽度：否则窗口缩小时表格最小尺寸(列宽总和)会把内容顶出视口，
        # 表现为"子页面不自适应"。固定前两列 + 后两列弹性拉伸填满剩余宽度。
        self.table_mapping.setMinimumWidth(0)
        self.table_mapping.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        self.table_mapping.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table_mapping.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table_mapping.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_mapping.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table_mapping.setColumnWidth(0, 100)
        self.table_mapping.setColumnWidth(1, 150)
        self.table_mapping.setColumnWidth(3, 180)

        # 环节列底色（与查询页对接字段卡一致）
        section_colors = {
            "起运港": ("#eef4ff", "#2f6fed"),
            "目的港": ("#e9f7ef", "#16a34a"),
            "中转港": ("#fdf4e9", "#d97706"),
            "尾程卡车": ("#fdf2f8", "#db2777"),   # 尾程卡车：浅粉
        }
        self.table_mapping.setRowCount(len(mapping))
        for r, item in enumerate(mapping):
            bg, fg = section_colors.get(item["环节"], ("#f8f9fb", "#6b7280"))

            it_sec = QTableWidgetItem(item["环节"])
            it_sec.setBackground(QColor(bg))
            it_sec.setForeground(QColor(fg))
            it_sec.setTextAlignment(Qt.AlignCenter)
            it_sec.setFlags(it_sec.flags() & ~Qt.ItemIsEditable)   # 环节固定
            self.table_mapping.setItem(r, 0, it_sec)

            it_cn = QTableWidgetItem(item["字段名称"])
            it_cn.setTextAlignment(Qt.AlignCenter)
            it_cn.setToolTip(item["英文描述"])                     # 英文描述悬停显示
            it_cn.setFlags(it_cn.flags() & ~Qt.ItemIsEditable)     # 字段名固定
            self.table_mapping.setItem(r, 1, it_cn)

            it_src = QTableWidgetItem(item["取值来源"])
            it_src.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table_mapping.setItem(r, 2, it_src)

            it_en = QTableWidgetItem(item["英文描述"])
            it_en.setTextAlignment(Qt.AlignCenter)
            it_en.setFlags(it_en.flags() & ~Qt.ItemIsEditable)     # 英文描述固定
            self.table_mapping.setItem(r, 3, it_en)

        root.addWidget(self.table_mapping, 1)

        # 说明 + 重置按钮
        bottom = QHBoxLayout()
        bottom.addWidget(mk_label(
            "改错想还原？点【恢复默认】回到内置映射", "FieldLabel", selectable=False))
        bottom.addStretch(1)
        btn_reset = QPushButton("恢复默认")
        btn_reset.setObjectName("GhostBtn")
        btn_reset.setFixedHeight(34)
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self.on_mapping_reset)
        bottom.addWidget(btn_reset)
        root.addLayout(bottom)

        return page

    def on_mapping_reset(self):
        """点【恢复默认】：把映射表格恢复成内置默认值（不自动保存，需再点保存）。"""
        default = config.DEFAULT_FIELD_MAPPING
        self.table_mapping.setRowCount(len(default))
        section_colors = {
            "起运港": ("#eef4ff", "#2f6fed"),
            "目的港": ("#e9f7ef", "#16a34a"),
            "中转港": ("#fdf4e9", "#d97706"),
            "尾程卡车": ("#fdf2f8", "#db2777"),   # 尾程卡车：浅粉
        }
        for r, item in enumerate(default):
            bg, fg = section_colors.get(item["环节"], ("#f8f9fb", "#6b7280"))
            it_sec = QTableWidgetItem(item["环节"])
            it_sec.setBackground(QColor(bg))
            it_sec.setForeground(QColor(fg))
            it_sec.setTextAlignment(Qt.AlignCenter)
            it_sec.setFlags(it_sec.flags() & ~Qt.ItemIsEditable)
            self.table_mapping.setItem(r, 0, it_sec)
            it_cn = QTableWidgetItem(item["字段名称"])
            it_cn.setTextAlignment(Qt.AlignCenter)
            it_cn.setToolTip(item["英文描述"])
            it_cn.setFlags(it_cn.flags() & ~Qt.ItemIsEditable)
            self.table_mapping.setItem(r, 1, it_cn)
            it_src = QTableWidgetItem(item["取值来源"])
            it_src.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table_mapping.setItem(r, 2, it_src)
            it_en = QTableWidgetItem(item["英文描述"])
            it_en.setTextAlignment(Qt.AlignCenter)
            it_en.setFlags(it_en.flags() & ~Qt.ItemIsEditable)
            self.table_mapping.setItem(r, 3, it_en)
        self.statusBar().showMessage("已恢复默认映射，记得点【保存配置】生效")

    def _build_feishu_mapping_tab(self):
        """【飞书接口映射】子页：36 个对接字段 + 对接状态 → 多维表格列名的映射。

        表格说明（参考"飞驼接口映射"，但不需要英文描述）：
          · 环节 / 字段名称：固定，不许改（与飞驼查询结果的字段对应）
          · 多维表格列名：可编辑 —— 多维表格以后改列名，在这里改一下即可正常回写
        """
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 16, 0, 8)
        root.setSpacing(12)

        tip = mk_label(
            "多维表格列名 = 查询结果回写到表格的哪一列。多维表格改了列名后，"
            "在这里同步修改即可（双击单元格编辑），保存后生效。",
            "FieldLabel", selectable=False)
        tip.setWordWrap(True)
        root.addWidget(tip)

        mapping = config.get_feishu_field_mapping()
        self.table_feishu_mapping = CopyableTable(0, 3)
        self.table_feishu_mapping.setHorizontalHeaderLabels(["环节", "字段名称", "多维表格列名"])
        self.table_feishu_mapping.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.table_feishu_mapping.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table_feishu_mapping.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_feishu_mapping.verticalHeader().setVisible(False)
        self.table_feishu_mapping.horizontalHeader().setStretchLastSection(False)
        self.table_feishu_mapping.setShowGrid(False)
        self.table_feishu_mapping.setWordWrap(False)
        self.table_feishu_mapping.setMinimumWidth(0)
        self.table_feishu_mapping.setSizeAdjustPolicy(QAbstractScrollArea.AdjustIgnored)
        # 前两列固定宽度，列名列弹性拉伸（与飞驼映射页同款布局）
        self.table_feishu_mapping.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table_feishu_mapping.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table_feishu_mapping.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table_feishu_mapping.setColumnWidth(0, 100)
        self.table_feishu_mapping.setColumnWidth(1, 160)

        self._fill_feishu_mapping(mapping)
        root.addWidget(self.table_feishu_mapping, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(mk_label(
            "改错想还原？点【恢复默认】回到内置列名", "FieldLabel", selectable=False))
        bottom.addStretch(1)
        btn_reset = QPushButton("恢复默认")
        btn_reset.setObjectName("GhostBtn")
        btn_reset.setFixedHeight(34)
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self.on_feishu_mapping_reset)
        bottom.addWidget(btn_reset)
        root.addLayout(bottom)

        return page

    def _fill_feishu_mapping(self, mapping):
        """把飞书映射列表填进表格（构建和恢复默认共用，避免两处重复代码）。"""
        section_colors = {
            "状态": ("#f4f0ff", "#7c3aed"),
            "起运港": ("#eef4ff", "#2f6fed"),
            "目的港": ("#e9f7ef", "#16a34a"),
            "中转港": ("#fdf4e9", "#d97706"),
            "尾程卡车": ("#fdf2f8", "#db2777"),
        }
        self.table_feishu_mapping.setRowCount(len(mapping))
        for r, item in enumerate(mapping):
            bg, fg = section_colors.get(item["环节"], ("#f8f9fb", "#6b7280"))

            it_sec = QTableWidgetItem(item["环节"])
            it_sec.setBackground(QColor(bg))
            it_sec.setForeground(QColor(fg))
            it_sec.setTextAlignment(Qt.AlignCenter)
            it_sec.setFlags(it_sec.flags() & ~Qt.ItemIsEditable)   # 环节固定
            self.table_feishu_mapping.setItem(r, 0, it_sec)

            it_cn = QTableWidgetItem(item["字段名称"])
            it_cn.setTextAlignment(Qt.AlignCenter)
            it_cn.setFlags(it_cn.flags() & ~Qt.ItemIsEditable)     # 字段名固定
            self.table_feishu_mapping.setItem(r, 1, it_cn)

            it_col = QTableWidgetItem(item["多维表格列名"])
            it_col.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table_feishu_mapping.setItem(r, 2, it_col)        # 列名可编辑

    def on_feishu_mapping_reset(self):
        """点【恢复默认】：飞书映射表格恢复内置默认列名（仍需点保存配置生效）。"""
        self._fill_feishu_mapping(config.DEFAULT_FEISHU_FIELD_MAPPING)
        self.statusBar().showMessage("已恢复默认飞书映射，记得点【保存配置】生效")

    def _mk_secret_line(self, text, placeholder, password):
        """创建一个配置输入框（返回 QLineEdit，密码框可选）。"""
        line = QLineEdit()
        line.setPlaceholderText(placeholder)
        if password:
            line.setEchoMode(QLineEdit.Password)
        return line

    def on_save_config(self):
        """点"保存配置"：把页面上的内容写进配置文件。

        保存逻辑：
          · 收集系统配置页（账号密码/飞书）+ 映射页（取值来源）
          · 如果已有配置文件 → 直接保存覆盖（不弹窗）
          · 如果还没有配置文件 → 弹出"另存为"让用户选位置，创建 config.json，
            并把路径记入注册表（下次启动自动读这里，不用再填账号密码）
        """
        cfg = config.get_config()
        cfg["freightower"]["client_id"] = self.input_client_id.text().strip()
        cfg["freightower"]["secret"] = self.input_secret.text().strip()
        cfg["feishu"]["app_id"] = self.input_app_id.text().strip()
        cfg["feishu"]["app_secret"] = self.input_app_secret.text().strip()
        cfg["feishu"]["table_link"] = self.input_table_link.text().strip()
        cfg["feishu"]["webhook_url"] = self.input_webhook_url.text().strip()
        cfg["feishu"]["webhook_secret"] = self.input_webhook_secret.text().strip()

        # 校验：必须填了账号密码（自动获取 Token 用）
        if not (cfg["freightower"]["client_id"] and cfg["freightower"]["secret"]):
            QMessageBox.warning(self, "提示", "请填写飞驼 API 账号和密码（用于自动获取 Token）。")
            return

        # 收集映射页的取值来源（环节/字段名固定，只更新取值来源）
        new_mapping = []
        for r in range(self.table_mapping.rowCount()):
            new_mapping.append({
                "环节": self.table_mapping.item(r, 0).text(),
                "字段名称": self.table_mapping.item(r, 1).text(),
                "取值来源": self.table_mapping.item(r, 2).text().strip(),
                "英文描述": self.table_mapping.item(r, 3).text(),
            })
        cfg["field_mapping"] = new_mapping

        # 收集飞书映射页的多维表格列名（环节/字段名固定，只更新列名）
        new_feishu_mapping = []
        for r in range(self.table_feishu_mapping.rowCount()):
            new_feishu_mapping.append({
                "环节": self.table_feishu_mapping.item(r, 0).text(),
                "字段名称": self.table_feishu_mapping.item(r, 1).text(),
                "多维表格列名": self.table_feishu_mapping.item(r, 2).text().strip(),
            })
        cfg["feishu_field_mapping"] = new_feishu_mapping

        # 判断：配置文件是否已存在
        cfg_file = config.get_config_file()
        if os.path.exists(cfg_file):
            # 已存在：直接保存，不弹窗
            config.save_config(cfg)
            QMessageBox.information(self, "保存成功", "配置已保存，下次启动自动读取。")
            self.statusBar().showMessage(f"配置已保存：{cfg_file}")
            return

        # 不存在：弹"另存为"让用户选择配置文件放哪
        default_name = config.DEFAULT_CONFIG_FILE   # 默认建议放 exe 同目录
        path, _ = QFileDialog.getSaveFileName(
            self, "选择配置文件保存位置（生成 config.json）", default_name, "配置文件 (*.json)"
        )
        if not path:
            return   # 用户取消
        if not path.endswith(".json"):
            path += ".json"
        config.save_config(cfg, path)
        QMessageBox.information(
            self, "保存成功",
            f"配置文件已创建：\n{path}\n\n下次启动会自动读取此文件，无需再填账号密码。"
        )
        self.statusBar().showMessage(f"配置文件已创建：{path}")

    # ================================================================
    # 查询页交互逻辑
    # ================================================================

    def _current_carrier_short(self):
        """从下拉框取当前选中的船司简称（支持手动输入简称/中文名）。"""
        text = self.combo_carrier.currentText().strip()
        short = self._display_to_short.get(text)   # 1) 完整命中下拉项
        if short:
            return short
        if text.upper() in CARRIERS:               # 2) 直接是船司简称（大小写不敏感）
            return text.upper()
        for display, s in self._display_to_short.items():   # 3) 中文名/部分字符
            if text and text in display:
                return s
        return text

    def _collect_query_payload(self):
        """收集界面上的查询条件，组装成查询参数。

        返回：
            (payload, error) 二元组：
              payload: 查询参数字典（bill_no/container_no/bill_category/carrier_short）
              error:   错误提示文字；没有错误时为 None
        """
        # 兜底补全：点"查询"前先按当前输入把船司简称/中文名补成全称（失焦信号可能尚未触发）
        self._try_fill_carrier_fullname()
        carrier_short = self._current_carrier_short()
        no = self.input_no.text().strip()   # 单号框：提单号/订舱号/箱号（三选一）

        # ---- 校验 ----
        if not carrier_short:
            return None, "请先选择船公司。"
        if not get_carrier_info(carrier_short):
            return None, f"没找到船司「{carrier_short}」，请从下拉列表选择。"
        if not no:
            return None, "请输入单号/箱号。"

        # ---- 按单号类型组装参数 ----
        if self.rb_cn.isChecked():
            # 箱号类型：只传箱号，单号和单号类型留空
            payload = {
                "carrier_short": carrier_short,
                "bill_no": "",
                "container_no": no,
                "bill_category": "",
            }
        else:
            # 提单号：传单号 + 类型 BL（订舱号查询已从界面移除）
            payload = {
                "carrier_short": carrier_short,
                "bill_no": no,
                "container_no": "",
                "bill_category": "BL",
            }
        return payload, None

    def on_query_clicked(self):
        """点"查询"按钮：
           轮询中点它 = 停止自动抓取；
           平时点它 = 校验输入 → 后台线程查询 → 结果刷新界面。
        """
        # ---- 正在自动轮询时，点按钮 = 停止抓取 ----
        if self.polling:
            self._stop_polling(stopped_by_user=True)
            return

        payload, error = self._collect_query_payload()
        if error:
            QMessageBox.warning(self, "提示", error)
            return

        self.btn_query.setEnabled(False)
        self.btn_query.setText("查询中...")
        # 先清空上一次的查询结果：概要和表格先变空白，查到新数据后再显示，
        # 避免旧数据留在界面上让人误以为是本次查询的结果
        self._clear_result()
        self.lbl_status.setText("查询中...")
        self.lbl_status_detail.setText("")
        self._paint_status("")   # 中性色（深灰），表示既不是成功也不是失败
        kw = payload["bill_no"] or payload["container_no"]
        type_cn = "箱号" if self.rb_cn.isChecked() else "提单号"
        self.statusBar().showMessage(f"正在查询 {payload['carrier_short']} / {type_cn} {kw}，请稍候...")

        self.worker = QueryWorker(payload)
        self.worker.finished_signal.connect(self.on_query_finished)
        self.worker.start()

    # ================================================================
    # 订阅中自动轮询（新箱号首次订阅，飞驼抓数据要几分钟）
    # ================================================================

    def _start_polling(self):
        """开启自动轮询：每 20 秒自动重查一次，直到出数据或达到上限。

        背景：飞驼是"订阅+查询"模式。全新的单号/箱号第一次查询时，
        飞驼要先向船司抓数据（通常 1~5 分钟），期间返回"订阅中"无节点。
        这里让程序自己每隔 20 秒重查，用户不用手动反复点查询。
        """
        self.polling = True
        self.poll_count = 0
        self.btn_query.setEnabled(True)                       # 按钮可点（点了=停止）
        self.btn_query.setText("停止抓取")
        self.statusBar().showMessage(
            "首次订阅：飞驼正在向船司抓取数据（通常 1~5 分钟），程序每 20 秒自动刷新，可随时点【停止抓取】"
        )
        self.poll_timer.start()

    def _stop_polling(self, stopped_by_user=False):
        """停止自动轮询（出数据 / 达上限 / 用户手动点停止）。"""
        self.poll_timer.stop()
        self.polling = False
        self.btn_query.setText("查 询")
        if stopped_by_user:
            self.statusBar().showMessage("已停止自动抓取，可稍后手动点【查询】刷新")

    def _poll_once(self):
        """定时器每 20 秒触发一次：自动重新查询当前输入的条件。"""
        # 防御：输入被清空就没法查了，直接停
        if not self.input_no.text().strip():
            self._stop_polling()
            return

        self.poll_count += 1
        payload, error = self._collect_query_payload()
        if error:
            self._stop_polling()
            return

        self.btn_query.setText(f"抓取中 {self.poll_count}/{self.poll_max}")
        self.worker = QueryWorker(payload)
        self.worker.finished_signal.connect(self.on_query_finished)
        self.worker.start()

    def on_query_finished(self, result):
        """后台查询完成后回到界面：更新概要、表格和状态栏。

        订阅中的特殊处理：新单号首次查询飞驼还没抓到数据（START 且 0 节点），
        这里会启动"自动轮询"——每 20 秒重查一次，出数据自动刷新。
        """
        self.worker = None
        self.last_result = result

        if not result["success"]:
            self._stop_polling()
            self.btn_query.setEnabled(True)
            self.btn_query.setText("查 询")
            self._clear_result()
            self.statusBar().showMessage("查询未成功")
            QMessageBox.warning(self, "查询失败", result["message"])
            return

        s = result["summary"]
        nodes = result["nodes"]

        # ---- 订阅中/船司无数据 且没有节点：飞驼可能还在抓数据 → 自动轮询（静默，不弹窗） ----
        # START=订阅中刚建档；NODATA=该单在船司暂无数据（实测 HPL 订舱号常在几分钟后才有
        # 节点）。两者都先等飞驼抓一下，出数据自动刷新，比直接放弃更符合业务习惯。
        if not nodes and str(s.get("statusCategory", "")).upper() in ("START", "NODATA"):
            self.lbl_bill_no.setText(f"单号：{s['billNo'] or '—'}")
            self.lbl_status.setText(s["statusCn"])
            cat = str(s.get("statusCategory", "")).upper()
            self._paint_status(cat)
            self.lbl_status_detail.setText(f"（{s['statusDescription'] or '—'}）")
            if not self.polling:
                # 第一次发现无节点数据：静默开启轮询（状态栏已有提示，不打扰用户）
                self._start_polling()
            elif self.poll_count >= self.poll_max:
                # 轮询到上限还没数据：停止，让用户稍后再查
                self._stop_polling()
                self.statusBar().showMessage(
                    "已自动刷新 10 次仍未有数据，飞驼抓取较慢，请过几分钟手动点【查询】"
                )
            # 轮询期间表格/概要维持"抓取中"的空状态即可
            return

        # ---- 正常出数据（或非订阅中的无数据）：先停掉轮询，再刷新界面 ----
        if self.polling:
            self._stop_polling()
        self.btn_query.setEnabled(True)
        self.btn_query.setText("查 询")

        self.lbl_bill_no.setText(f"单号：{s['billNo'] or '—'}")
        self.lbl_status.setText(s["statusCn"])
        self._paint_status(s["statusCategory"])
        self.lbl_status_detail.setText(f"（{s['statusDescription'] or '—'}）")
        # 最新节点：只显示"实际发生"的（和节点明细口径一致）
        self.lbl_current.setText(f"{s['currentEventCn'] or '—'}（{s['currentEventCode'] or ''}）")
        self.lbl_current_time.setText(s["currentEventTime"] or "—")
        self.lbl_current_place.setText(s["currentEventPlace"] or "—")
        # 下一节点（预计）+ 时间 + 地点
        if s.get("nextEventCn"):
            self.lbl_next.setText(f"{s['nextEventCn']}（{s.get('nextEventCode') or ''}）")
            self.lbl_next_time.setText(s.get("nextEventTime") or "—")
            self.lbl_next_place.setText(s.get("nextEventPlace") or "—")
        else:
            self.lbl_next.setText("—")
            self.lbl_next_time.setText("—")
            self.lbl_next_place.setText("—")
        self.lbl_carrier.setText(s["carrierCn"] or "—")
        self.lbl_vessel.setText(f"{s['vessel'] or '—'} / {s['voyage'] or '—'}")
        self.lbl_route.setText(f"{s['polName'] or '—'} → {s['podName'] or '—'}")
        self.lbl_update.setText(s["updateTime"] or "—")

        # 对接字段：按飞驼对接规范抽取的 32 个业务字段
        self._fill_fields_table(result.get("fields", []))

        # 统计实际/预计数量，让业务一眼看清
        n_actual = sum(1 for n in nodes if n.get("isEsti") != "Y")
        n_esti = len(nodes) - n_actual
        self.lbl_node_count.setText(f"共 {len(nodes)} 条节点（实际 {n_actual} + 预计 {n_esti}，按时间倒序）")
        self.table.setRowCount(len(nodes))
        for row, n in enumerate(nodes):
            # 单元格内容统一居中（表头也居中，整张表格保证视觉对齐）
            item_t = QTableWidgetItem(n.get("eventTime", ""))
            item_t.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, item_t)

            item_d = QTableWidgetItem(n.get("descriptionCn") or n.get("eventCode", ""))
            item_d.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, item_d)

            # 实际/预计列：预计的橙色显示，实际的黑字
            item_esti = QTableWidgetItem("预计" if n.get("isEsti") == "Y" else "实际")
            item_esti.setTextAlignment(Qt.AlignCenter)
            if n.get("isEsti") == "Y":
                item_esti.setForeground(QColor("#d97706"))   # 预计节点橙色显示
            self.table.setItem(row, 2, item_esti)

            item_p = QTableWidgetItem(n.get("eventPlace", ""))
            item_p.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, item_p)

            item_c = QTableWidgetItem(n.get("containerNo", ""))
            item_c.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, item_c)

            # 运输方式一列：做成彩色小标签的样子（浅底 + 同色系文字），对应设计稿 tag
            mode_cn = TRANSPORT_MODE_MAP.get(n.get("transportMode", ""), n.get("transportMode", ""))
            item_mode = QTableWidgetItem(mode_cn)
            item_mode.setTextAlignment(Qt.AlignCenter)
            bg, fg = TRANSPORT_TAG_COLORS.get(n.get("transportMode", ""), ("#f4f5f7", "#6b7280"))
            item_mode.setBackground(QColor(bg))
            item_mode.setForeground(QColor(fg))
            self.table.setItem(row, 5, item_mode)

            item_v = QTableWidgetItem(f"{n.get('vslName') or '—'} / {n.get('voy') or '—'}")
            item_v.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 6, item_v)

        # 当前行高亮：找到"实际发生中时间最新"的那一行（对应设计稿 current 左蓝条行），
        # 整行刷浅蓝背景 + 加粗，让用户一眼看到最新动态
        current_row = -1
        best_time = ""
        for row, n in enumerate(nodes):
            if n.get("isEsti") == "Y":
                continue   # 预计节点不算实际动态
            t = n.get("eventTime", "")
            if t >= best_time:
                best_time = t
                current_row = row
        if current_row >= 0:
            for c in range(len(NODE_HEADERS)):
                it = self.table.item(current_row, c)
                if it is not None:
                    it.setBackground(QColor("#eef4ff"))
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)

        self.statusBar().showMessage(f"查询成功：{s['billNo'] or '箱号查询'}，{s['statusCn']}，共 {len(nodes)} 条节点")

    def _paint_status(self, category):
        """根据运单总状态切换"总状态"徽章的底色（浅色底 + 同色系文字）。"""
        colors = {
            "PROCESS": ("#e8f1ff", "#2f6fed"),
            "COMPLETE": ("#e9f7ef", "#16a34a"),
            "START": ("#fdf4e9", "#d97706"),
            "NODATA": ("#fdecec", "#dc2626"),
            "ABNORMAL": ("#fdecec", "#dc2626"),
        }
        bg, fg = colors.get(str(category).upper(), ("#eef1f6", "#475569"))
        self.lbl_status.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:4px; "
            f"padding:3px 12px; font-size:15px; font-weight:700;"
        )

    def _clear_result(self):
        """查询失败时，把上一次的结果清空。"""
        self.lbl_bill_no.setText("单号：—")
        self.lbl_status.setText("—")
        self.lbl_status_detail.setText("")
        self.lbl_current.setText("—")
        self.lbl_current_time.setText("—")
        self.lbl_current_place.setText("—")
        self.lbl_next.setText("—")
        self.lbl_next_time.setText("—")
        self.lbl_next_place.setText("—")
        self.lbl_carrier.setText("—")
        self.lbl_vessel.setText("—")
        self.lbl_route.setText("—")
        self.lbl_update.setText("—")
        self.lbl_node_count.setText("")
        self.table.setRowCount(0)
        self.lbl_fields_count.setText("")
        self.table_fields.setRowCount(0)

    # ---------- 配置页回填（供测试/启动时把已有配置填进输入框） ----------
    def refresh_config_form(self):
        """把当前配置内容回显到配置页输入框（启动时调用一次）。"""
        cfg = config.get_config()
        fw = cfg.get("freightower", {})
        self.input_client_id.setText(fw.get("client_id", ""))
        self.input_secret.setText(fw.get("secret", ""))
        fs = cfg.get("feishu", {})
        self.input_app_id.setText(fs.get("app_id", ""))
        self.input_app_secret.setText(fs.get("app_secret", ""))
        self.input_table_link.setText(fs.get("table_link", ""))
        self.input_webhook_url.setText(fs.get("webhook_url", ""))
        self.input_webhook_secret.setText(fs.get("webhook_secret", ""))


def _looks_like_container(no):
    """判断一个单号长得像不像"箱号"（4位字母+7位数字，如 FFAU3658493）。

    参数：
        no: 用户输入的单号/箱号
    返回：
        True=像箱号（批量查询时按箱号查），False=按提单号查
    """
    return bool(re.fullmatch(r"[A-Za-z]{4}\d{7}", (no or "").strip()))


def write_batch_template(path):
    """生成批量查询模板 Excel（表头：船公司/提单号/箱号），供用户下载后填写。

    参数：
        path: 保存的 .xlsx 文件路径
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "批量查询模板"

    # 表头：三个固定列
    headers = ["船公司", "提单号", "箱号"]
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="2F6FED")
    for c, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = head_font
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # 示例行（提示用户格式；导入时按列读）
    ws.append(["MSC", "177MASASS106510A", "TCKU1559530"])
    ws.append(["ONE", "", "FFAU3658493"])

    # 列宽
    for c, w in enumerate([18, 30, 22], start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A2"

    wb.save(path)


def read_batch_template(path):
    """读取批量查询模板 Excel，返回每行的 (船公司, 提单号, 箱号)。

    模板规则：
      · 第一行是表头，按表头找"船公司/提单号/箱号"列（名称包含关键词即可）
      · 如果表头里找不到，就用前 3 列按顺序对应
      · 返回从第二行起的有效数据（船公司非空）

    参数：
        path: .xlsx/.xls 文件路径
    返回：
        [(carrier, bill_no, container_no), ...]
    """
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    # 表头定位列
    header = None
    rows_iter = ws.iter_rows(values_only=True)
    for row in rows_iter:
        if row and any(c is not None for c in row):
            header = [str(c or "").strip() for c in row]
            break
    if header is None:
        return []

    def find_col(keywords, fallback):
        for i, h in enumerate(header):
            if any(k in h for k in keywords):
                return i
        return fallback

    col_carrier = find_col(["船公司", "船司", "carrier"], 0)
    col_bill = find_col(["提单号", "单号", "bill"], 1)
    col_container = find_col(["箱号", "container"], 2)

    rows = []
    for row in rows_iter:
        vals = list(row)
        carrier = str(vals[col_carrier] or "").strip() if col_carrier < len(vals) else ""
        bill = str(vals[col_bill] or "").strip() if col_bill < len(vals) else ""
        container = str(vals[col_container] or "").strip() if col_container < len(vals) else ""
        if carrier:
            rows.append((carrier, bill, container))
    return rows


def export_batch_to_excel(batch_results, path):
    """把批量查询结果导出成 .xlsx 文件（需要 openpyxl 库）。

    表格结构（面向业务，不含技术注释）：
      第一行表头：船公司 / 提单号 / 箱号 / 状态 / 总状态 + 36 个对接字段
      （"环节-字段名"，如 起运港-截单时间）
      之后每行：一条运单的查询结果；空值直接留空（不写 None/—）

    参数：
        batch_results: on_batch_item 里攒的列表
                       [{"船公司","提单号","箱号","状态","总状态","fields":[...]}]
        path: 保存的 .xlsx 文件路径
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter

    # ---- 表头：前五列固定（船公司/提单号/箱号/状态/总状态）+ 所有对接字段列 ----
    headers = ["船公司", "提单号", "箱号", "状态", "总状态"]
    # 用第一条结果的 fields 定列；不同单字段序一致（都是解析器固定顺序）
    field_keys = []
    if batch_results:
        for f in batch_results[0].get("fields", []):
            field_keys.append(f"{f.get('环节', '')}-{f.get('字段名称', '')}")

    wb = Workbook()
    ws = wb.active
    ws.title = "批量查询结果"

    # 表头样式：白字蓝底加粗（一眼看清是标题行）
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="2F6FED")
    for c, h in enumerate(headers + field_keys, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = head_font
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # ---- 数据行：每个单号一行（空值直接留空，不写 None/—） ----
    for r, row in enumerate(batch_results, start=2):
        ws.cell(row=r, column=1, value=row.get("船公司", ""))
        ws.cell(row=r, column=2, value=row.get("提单号", ""))
        ws.cell(row=r, column=3, value=row.get("箱号", ""))
        ws.cell(row=r, column=4, value=row.get("状态", ""))
        ws.cell(row=r, column=5, value=row.get("总状态", ""))
        # 字段列：按 field_keys 顺序，从该条结果的 fields 里找对应值
        fields = row.get("fields", [])
        for c, key in enumerate(field_keys, start=6):
            value = ""
            for f in fields:
                if f"{f.get('环节', '')}-{f.get('字段名称', '')}" == key:
                    value = f.get("值") or ""
                    break
            ws.cell(row=r, column=c, value=value)

    # ---- 列宽：前五列固定，字段列按内容自适应（超过26列要用列字母） ----
    for c, h in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(c)].width = 22 if c == 1 else 14
    for c in range(len(headers) + 1, len(headers) + len(field_keys) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 20

    # 冻结表头（滚动数据时始终能看到第一行）
    ws.freeze_panes = "A2"

    wb.save(path)


def main():
    """程序入口：创建窗口并运行事件循环。"""
    app = QApplication(sys.argv)
    app.setWindowIcon(load_app_icon())   # 全局应用图标（任务栏显示为吉祥物）
    app.setStyleSheet(APP_STYLE)
    win = MainWindow()   # 构造时已回填配置
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
