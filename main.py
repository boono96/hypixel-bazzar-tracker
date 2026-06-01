"""PySide6 dashboard for Hypixel SkyBlock Bazaar data — powered by SQLite."""
import datetime

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QAction, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QHBoxLayout, QWidget, QLineEdit, QStatusBar,
    QHeaderView, QLabel, QPushButton, QSizePolicy, QFrame, QGroupBox,
    QGridLayout, QAbstractItemView,
)

from bazzar_db import BazaarDB

DB_PATH = "bazzar.db"

BOLD_FONT = QFont()
BOLD_FONT.setBold(True)
TITLE_FONT = QFont("Segoe UI", 16, QFont.Bold)

DARK_STYLESHEET = """
QMainWindow {
    background-color: #1e1e2e;
}
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI";
    font-size: 12px;
}
QTableWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    gridline-color: #313244;
    border: 1px solid #313244;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}
QTableWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid #313244;
}
QTableWidget::item:selected {
    background-color: #585b70;
}
QHeaderView::section {
    background-color: #11111b;
    color: #a6adc8;
    padding: 6px 8px;
    border: none;
    border-bottom: 2px solid #45475a;
    font-weight: bold;
}
QHeaderView::section:hover {
    background-color: #313244;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #181825;
}
QTabBar::tab {
    background-color: #1e1e2e;
    color: #a6adc8;
    padding: 8px 16px;
    border: 1px solid #313244;
    border-bottom: none;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #313244;
    color: #cdd6f4;
    font-weight: bold;
}
QTabBar::tab:hover {
    background-color: #45475a;
}
QLineEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
}
QLineEdit:focus {
    border: 1px solid #89b4fa;
}
QPushButton {
    background-color: #45475a;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #585b70;
}
QPushButton:pressed {
    background-color: #313244;
}
QStatusBar {
    background-color: #11111b;
    color: #a6adc8;
    border-top: 1px solid #313244;
}
QSplitter::handle {
    background-color: #313244;
    width: 2px;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #a6adc8;
}
QLabel {
    background: transparent;
}
"""


class NumericItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by numeric value stored in UserRole."""

    def __init__(self, text, value):
        super().__init__(text)
        self.setData(Qt.UserRole, value)

    def __lt__(self, other):
        a = self.data(Qt.UserRole)
        b = other.data(Qt.UserRole)
        if a is None and b is None:
            return self.text() < other.text()
        return (a or 0) < (b or 0)


def safe_div(a, b):
    return a / b if b else 0


class BazaarDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hypixel SkyBlock — Bazaar Dashboard")
        self.resize(1320, 820)
        self.setMinimumSize(900, 600)

        self.db = BazaarDB(DB_PATH)
        self._all_products = []
        self._latest_data = {}     # {product_id: {field: val}}
        self._current_product = None
        self._chart_widget = None
        self._toolbar = None

        self._setup_ui()
        self._reload()

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 4)
        main_layout.setSpacing(6)

        title = QLabel("Hypixel SkyBlock · Bazaar Tracker")
        title.setFont(TITLE_FONT)
        title.setStyleSheet("color: #cdd6f4; padding: 4px 0;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Top bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search products...")
        self.search_input.textChanged.connect(self._populate_table)
        top_bar.addWidget(self.search_input, stretch=1)

        refresh_btn = QPushButton(" Refresh")
        refresh_btn.setToolTip("Refresh from database (Ctrl+R)")
        refresh_btn.clicked.connect(self._reload)
        top_bar.addWidget(refresh_btn)

        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color: #a6adc8; padding-right: 8px;")
        top_bar.addWidget(self._info_label)

        main_layout.addLayout(top_bar)

        # Splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left: table
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Product", "Buy Price", "Sell Price", "Spread", "Margin %",
            "Sell Volume", "Buy Volume",
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection)
        left_layout.addWidget(self.table)
        splitter.addWidget(left)

        # Right: charts + stats
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(4)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._draw_chart)
        for label in ["Price", "Volume", "Orders", "All Metrics"]:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            self.tabs.addTab(tab, label)
        right_layout.addWidget(self.tabs, stretch=1)

        self.stats_group = QGroupBox("Item Statistics")
        stats_layout = QGridLayout(self.stats_group)
        stats_layout.setSpacing(4)
        labels = [
            ("Buy Price:", 0, 0), ("Sell Price:", 0, 2), ("Spread:", 0, 4),
            ("Margin %:", 1, 0), ("Sell Volume:", 1, 2), ("Buy Volume:", 1, 4),
            ("Sell Orders:", 2, 0), ("Buy Orders:", 2, 2),
            ("Sell/Buy Ratio:", 2, 4),
        ]
        self._stat_labels = {}
        for text, row, col in labels:
            lbl = QLabel("—")
            lbl.setFont(BOLD_FONT)
            lbl.setStyleSheet("color: #f5c2e7; font-size: 13px;")
            key = text.replace(":", "").replace(" ", "_").replace("/", "_").lower()
            self._stat_labels[key] = lbl
            hdr = QLabel(text)
            hdr.setStyleSheet("color: #a6adc8; font-size: 11px;")
            stats_layout.addWidget(hdr, row, col)
            stats_layout.addWidget(lbl, row, col + 1)
        right_layout.addWidget(self.stats_group, stretch=0)
        splitter.addWidget(right)

        splitter.setSizes([480, 780])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, stretch=1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Shortcuts
        act = QAction(self)
        act.setShortcut("Ctrl+R")
        act.triggered.connect(self._reload)
        self.addAction(act)

        self.table.keyPressEvent = self._table_keypress

    def _table_keypress(self, event):
        key = event.key()
        if Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9 or key in (
                Qt.Key_Space, Qt.Key_Minus, Qt.Key_Underscore, Qt.Key_Period):
            self.search_input.setFocus()
            self.search_input.insert(event.text())
        else:
            QTableWidget.keyPressEvent(self.table, event)

    # ── Data ──────────────────────────────────────────────────────────

    def _reload(self):
        self._all_products = [
            p for p in self.db.get_product_ids()
            if p != "BAZAAR_COOKIE"
        ]
        self._latest_data = self.db.get_latest_for_all()
        self._info_label.setText(
            f"{len(self._all_products)} products · "
            f"{self.db.get_snapshot_count():,} total snapshots"
        )
        last_ts = self.db.get_latest_timestamp()
        if last_ts:
            ts = datetime.datetime.fromtimestamp(last_ts / 1000.0)
            self._info_label.setText(
                self._info_label.text() +
                f" · last: {ts.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        self._populate_table()

    def _populate_table(self):
        query = self.search_input.text().lower().strip()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for name in self._all_products:
            if query and query not in name.lower():
                continue
            d = self._latest_data.get(name, {})
            bp = d.get("buy_price", 0) or 0
            sp = d.get("sell_price", 0) or 0
            sv = d.get("sell_volume", 0) or 0
            bv = d.get("buy_volume", 0) or 0
            spread = sp - bp
            margin = (spread / bp * 100) if bp else 0

            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, NumericItem(f"{bp:,.1f}", bp))
            self.table.setItem(row, 2, NumericItem(f"{sp:,.1f}", sp))
            self.table.setItem(row, 3, NumericItem(f"{spread:+,.1f}", spread))
            color = "#a6e3a1" if margin > 0 else "#f38ba8" if margin < 0 else "#a6adc8"
            mi = NumericItem(f"{margin:+.1f}%", margin)
            mi.setForeground(QColor(color))
            self.table.setItem(row, 4, mi)
            self.table.setItem(row, 5, NumericItem(f"{sv:,}", sv))
            self.table.setItem(row, 6, NumericItem(f"{bv:,}", bv))

        self.table.setSortingEnabled(True)
        self.status_bar.showMessage(
            f"{self.table.rowCount()} products shown"
        )

    # ── Selection & stats ─────────────────────────────────────────────

    def _on_selection(self):
        sel = self.table.selectedItems()
        if not sel:
            return
        name = self.table.item(sel[0].row(), 0).text()
        if name == self._current_product:
            return
        self._current_product = name
        self._update_stats()
        self._draw_chart()

    def _update_stats(self):
        name = self._current_product
        d = self._latest_data.get(name, {})
        bp = d.get("buy_price", 0) or 0
        sp = d.get("sell_price", 0) or 0
        sv = d.get("sell_volume", 0) or 0
        bv = d.get("buy_volume", 0) or 0
        so = d.get("sell_orders", 0) or 0
        bo = d.get("buy_orders", 0) or 0
        spread = sp - bp
        margin = (spread / bp * 100) if bp else 0
        ratio = sp / bp if bp else 0

        st = lambda k, v: self._stat_labels[k].setText(str(v))
        st('buy_price', f"{bp:,.1f}")
        st('sell_price', f"{sp:,.1f}")
        st('spread', f"{spread:+,.1f}")
        st('margin_%', f"{margin:+.1f}%")
        st('sell_volume', f"{sv:,}")
        st('buy_volume', f"{bv:,}")
        st('sell_orders', f"{so:,}")
        st('buy_orders', f"{bo:,}")
        st('sell_buy_ratio', f"{ratio:.3f}")
        ts = d.get("timestamp_ms", 0)
        ts_str = datetime.datetime.fromtimestamp(ts / 1000.0).strftime("%H:%M:%S") if ts else "—"
        self.stats_group.setTitle(f"Item Statistics — {name}  (last: {ts_str})")

    # ── Charts ────────────────────────────────────────────────────────

    def _draw_chart(self):
        name = self._current_product
        if not name:
            return
        data = self.db.get_history(name, fields=(
            "sell_price", "buy_price", "sell_volume",
            "buy_volume", "sell_orders", "buy_orders",
        ))
        if not data["time"]:
            return
        x = np.array(data["time"]).astype("datetime64[ms]")

        idx = self.tabs.currentIndex()
        if idx == 0:       # Price
            fig = self._fig_two(x, data, "sell_price", "buy_price", "Price (Sell vs Buy)", "Price")
        elif idx == 1:     # Volume
            fig = self._fig_two(x, data, "sell_volume", "buy_volume", "Volume (Sell vs Buy)", "Volume")
        elif idx == 2:     # Orders
            fig = self._fig_two(x, data, "sell_orders", "buy_orders", "Orders (Sell vs Buy)", "Orders")
        else:              # All
            fig = self._fig_all(x, data)

        self._embed_chart(fig, self.tabs.currentWidget())

    def _fig_two(self, x, data, k1, k2, title, ylabel):
        fig = Figure(figsize=(8, 4), dpi=100, facecolor="#181825")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#1e1e2e")
        ax.plot(x, data.get(k1, []), color="#89b4fa", linewidth=1.2, label=k1)
        ax.plot(x, data.get(k2, []), color="#f38ba8", linewidth=1.2, label=k2)
        ax.set_title(title, color="#cdd6f4", fontsize=13, fontweight="bold")
        ax.set_ylabel(ylabel, color="#a6adc8")
        ax.legend(facecolor="#313244", edgecolor="#45475a", labelcolor="#cdd6f4")
        ax.tick_params(colors="#a6adc8", labelsize=9, rotation=30)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color("#45475a")
        ax.spines["left"].set_color("#45475a")
        ax.grid(True, color="#313244", linewidth=0.5, alpha=0.7)
        ax.ticklabel_format(style="plain", axis="y")
        fig.tight_layout(pad=2)
        return fig

    def _fig_all(self, x, data):
        fig = Figure(figsize=(9, 6), dpi=100, facecolor="#181825")
        keys = ["sell_price", "buy_price", "sell_volume",
                "buy_volume", "sell_orders", "buy_orders"]
        for i, k in enumerate(keys):
            ax = fig.add_subplot(2, 3, i + 1)
            ax.set_facecolor("#1e1e2e")
            ax.plot(x, data.get(k, []), color="#89b4fa", linewidth=1.0)
            ax.set_title(k, color="#cdd6f4", fontsize=10)
            ax.tick_params(colors="#a6adc8", labelsize=8, rotation=45)
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)
            ax.spines["bottom"].set_color("#45475a")
            ax.spines["left"].set_color("#45475a")
            ax.grid(True, color="#313244", linewidth=0.4, alpha=0.7)
            ax.ticklabel_format(style="plain", axis="y")
        fig.subplots_adjust(left=0.08, bottom=0.10, right=0.97, top=0.94,
                            wspace=0.30, hspace=0.45)
        return fig

    def _embed_chart(self, fig, tab_widget):
        if self._chart_widget:
            layout = tab_widget.layout()
            if layout:
                layout.removeWidget(self._chart_widget)
            self._chart_widget.deleteLater()
            self._chart_widget = None
        if self._toolbar:
            self._toolbar.deleteLater()
            self._toolbar = None

        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, tab_widget)
        toolbar.setStyleSheet("background: #181825; border: none;")
        layout = tab_widget.layout()
        if layout:
            layout.addWidget(toolbar)
            layout.addWidget(canvas)
        self._chart_widget = canvas
        self._toolbar = toolbar


def main():
    import sys
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLESHEET)
    window = BazaarDashboard()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
