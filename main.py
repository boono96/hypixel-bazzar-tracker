import datetime
import os

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

from file_handeler import file_handeler

DATA_FILE = 'bazzar_static_file.json'

BOLD_FONT = QFont()
BOLD_FONT.setBold(True)

HEADER_FONT = QFont("Segoe UI", 12, QFont.Bold)
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


def safe_get_last(arr):
    return arr[-1] if arr else 0


class BazaarDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hypixel SkyBlock — Bazaar Dashboard")
        self.resize(1320, 820)
        self.setMinimumSize(900, 600)

        self.data = {}
        self._all_product_keys = []
        self._current_product = None
        self._chart_widget = None
        self._toolbar = None

        self._setup_ui()
        self._load_data()
        self._populate_table()

    # ── UI construction ──────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 4)
        main_layout.setSpacing(6)

        # Title bar
        title = QLabel("Hypixel SkyBlock · Bazaar Tracker")
        title.setFont(TITLE_FONT)
        title.setStyleSheet("color: #cdd6f4; padding: 4px 0;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Top toolbar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search products...  (type to filter, ↑↓ to navigate)")
        self.search_input.setMinimumWidth(280)
        self.search_input.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_input, stretch=1)

        refresh_btn = QPushButton(" Refresh")
        refresh_btn.setToolTip("Reload data from disk (Ctrl+R)")
        refresh_btn.clicked.connect(self._load_data)
        top_bar.addWidget(refresh_btn)

        self._update_label = QLabel("")
        self._update_label.setStyleSheet("color: #a6adc8; padding-right: 8px;")
        top_bar.addWidget(self._update_label)

        main_layout.addLayout(top_bar)

        # Splitter: table | charts
        splitter = QSplitter(Qt.Horizontal)

        # ── LEFT: product table ──
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Product", "Buy Price", "Sell Price", "Spread", "Margin %",
             "Sell Volume", "Buy Volume"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 7):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)

        self.table.itemSelectionChanged.connect(self._on_product_selected)
        self.table.itemDoubleClicked.connect(self._on_product_double_clicked)

        left_layout.addWidget(self.table)
        splitter.addWidget(left_panel)

        # ── RIGHT: chart + stats ──
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(4)

        # Chart tabs
        self.chart_tabs = QTabWidget()
        self.chart_tabs.currentChanged.connect(self._on_tab_changed)
        right_layout.addWidget(self.chart_tabs, stretch=1)

        # Placeholder for each tab
        for label in ["Price", "Volume", "Orders", "All Metrics"]:
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            self.chart_tabs.addTab(tab, label)

        # Stats group
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
            header = QLabel(text)
            header.setStyleSheet("color: #a6adc8; font-size: 11px;")
            stats_layout.addWidget(header, row, col)
            stats_layout.addWidget(lbl, row, col + 1)

        right_layout.addWidget(self.stats_group, stretch=0)
        splitter.addWidget(right_panel)

        splitter.setSizes([480, 780])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, stretch=1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Shortcuts
        refresh_action = QAction(self)
        refresh_action.setShortcut("Ctrl+R")
        refresh_action.triggered.connect(self._load_data)
        self.addAction(refresh_action)

        # Keyboard navigation in table: typing in table triggers search
        self.table.keyPressEvent = self._table_key_press

    def _table_key_press(self, event):
        """Redirect printable key presses into the search box."""
        key = event.key()
        if Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9 or key in (
                Qt.Key_Space, Qt.Key_Minus, Qt.Key_Underscore, Qt.Key_Period):
            self.search_input.setFocus()
            self.search_input.insert(event.text())
        else:
            QTableWidget.keyPressEvent(self.table, event)

    # ── Data loading ─────────────────────────────────────────────────

    def _load_data(self):
        try:
            self.data = file_handeler.load_json_file(DATA_FILE)
        except (FileNotFoundError, Exception):
            self.data = {'time': []}

        self._all_product_keys = sorted(
            k for k in self.data.keys() if k not in ('time', 'BAZAAR_COOKIE')
        )

        # Update header info
        if self.data.get('time') and len(self.data['time']) > 0:
            ts = datetime.datetime.fromtimestamp(self.data['time'][-1] / 1000.0)
            self._update_label.setText(
                f"Last update: {ts.strftime('%Y-%m-%d %H:%M:%S')} · "
                f"{len(self._all_product_keys)} products · "
                f"{len(self.data['time'])} snapshots"
            )
        else:
            self._update_label.setText("No data loaded")

        self._populate_table()

    # ── Table population & filtering ─────────────────────────────────

    def _populate_table(self):
        query = self.search_input.text().lower().strip()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for name in self._all_product_keys:
            if query and query not in name.lower():
                continue

            prod = self.data.get(name, {})
            bp = safe_get_last(prod.get('buy_price', []))
            sp = safe_get_last(prod.get('sell_price', []))
            sv = safe_get_last(prod.get('sell_volume', []))
            bv = safe_get_last(prod.get('buy_volume', []))
            spread = sp - bp
            margin = (spread / bp * 100) if bp else 0

            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, NumericItem(f"{bp:,.1f}", bp))
            self.table.setItem(row, 2, NumericItem(f"{sp:,.1f}", sp))
            self.table.setItem(row, 3, NumericItem(f"{spread:+,.1f}", spread))

            color = "#a6e3a1" if margin > 0 else "#f38ba8" if margin < 0 else "#a6adc8"
            margin_item = NumericItem(f"{margin:+.1f}%", margin)
            margin_item.setForeground(QColor(color))
            self.table.setItem(row, 4, margin_item)

            self.table.setItem(row, 5, NumericItem(f"{sv:,}", sv))
            self.table.setItem(row, 6, NumericItem(f"{bv:,}", bv))

        self.table.setSortingEnabled(True)
        self.status_bar.showMessage(
            f"{self.table.rowCount()} products filtered"
            if query else f"{len(self._all_product_keys)} products loaded"
        )

    def _on_search_changed(self):
        self._populate_table()

    # ── Product selection ────────────────────────────────────────────

    def _on_product_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        name = self.table.item(selected[0].row(), 0).text()
        if name == self._current_product:
            return
        self._current_product = name
        self._update_stats()
        self._draw_chart()

    def _on_product_double_clicked(self):
        self._on_product_selected()

    def _on_tab_changed(self):
        if self._current_product:
            self._draw_chart()

    def _update_stats(self):
        name = self._current_product
        if not name or name not in self.data:
            return
        prod = self.data[name]
        now = self.data['time'][-1] if self.data.get('time') else 0
        ts = datetime.datetime.fromtimestamp(now / 1000.0).strftime('%H:%M:%S') if now else '—'

        bp = safe_get_last(prod.get('buy_price', []))
        sp = safe_get_last(prod.get('sell_price', []))
        sv = safe_get_last(prod.get('sell_volume', []))
        bv = safe_get_last(prod.get('buy_volume', []))
        so = safe_get_last(prod.get('sell_order', []))
        bo = safe_get_last(prod.get('buy_order', []))

        spread = sp - bp
        margin = (spread / bp * 100) if bp else 0
        ratio = sp / bp if bp else 0

        set_text = lambda k, v: self._stat_labels[k].setText(str(v))

        set_text('buy_price', f"{bp:,.1f}")
        set_text('sell_price', f"{sp:,.1f}")
        set_text('spread', f"{spread:+,.1f}")
        set_text('margin_%', f"{margin:+.1f}%")
        set_text('sell_volume', f"{sv:,}")
        set_text('buy_volume', f"{bv:,}")
        set_text('sell_orders', f"{so:,}")
        set_text('buy_orders', f"{bo:,}")
        set_text('sell_buy_ratio', f"{ratio:.3f}")
        self.stats_group.setTitle(f"Item Statistics — {name}  (last: {ts})")

    # ── Charts ───────────────────────────────────────────────────────

    def _draw_chart(self):
        name = self._current_product
        if not name or name not in self.data:
            return

        prod = self.data[name]
        start = prod.get('start_time', [0])[0]
        src = self.data.get('time', [])
        x_data = np.array(src[start::]).astype('datetime64[ms]')

        tab_idx = self.chart_tabs.currentIndex()

        if tab_idx == 0:      # Price
            fig = self._build_two_line_fig(x_data, prod, 'sell_price', 'buy_price',
                                           "Price (Sell vs Buy)", "Price")
        elif tab_idx == 1:    # Volume
            fig = self._build_two_line_fig(x_data, prod, 'sell_volume', 'buy_volume',
                                           "Volume (Sell vs Buy)", "Volume")
        elif tab_idx == 2:    # Orders
            fig = self._build_two_line_fig(x_data, prod, 'sell_order', 'buy_order',
                                           "Orders (Sell vs Buy)", "Orders")
        else:                 # All Metrics
            fig = self._build_all_fig(x_data, prod)

        if fig is None:
            return

        self._set_chart_widget(fig, self.chart_tabs.currentWidget())

    def _clear_chart_area(self, tab_widget):
        if self._chart_widget:
            layout = tab_widget.layout()
            if layout:
                if self._chart_widget in [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i)]:
                    layout.removeWidget(self._chart_widget)
            self._chart_widget.deleteLater()
            self._chart_widget = None
        if self._toolbar:
            self._toolbar.deleteLater()
            self._toolbar = None

    def _set_chart_widget(self, fig, tab_widget):
        self._clear_chart_area(tab_widget)
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, tab_widget)
        toolbar.setStyleSheet("background: #181825; border: none;")
        layout = tab_widget.layout()
        if layout:
            layout.addWidget(toolbar)
            layout.addWidget(canvas)
        self._chart_widget = canvas
        self._toolbar = toolbar

    def _build_two_line_fig(self, x_data, prod, key1, key2, title, ylabel):
        fig = Figure(figsize=(8, 4), dpi=100, facecolor='#181825')
        ax = fig.add_subplot(111)
        ax.set_facecolor('#1e1e2e')
        ax.plot(x_data, prod.get(key1, []), color='#89b4fa', linewidth=1.2, label=key1)
        ax.plot(x_data, prod.get(key2, []), color='#f38ba8', linewidth=1.2, label=key2)
        ax.set_title(title, color='#cdd6f4', fontsize=13, fontweight='bold')
        ax.set_ylabel(ylabel, color='#a6adc8')
        ax.legend(facecolor='#313244', edgecolor='#45475a', labelcolor='#cdd6f4')
        ax.tick_params(colors='#a6adc8', labelsize=9, rotation=30)
        ax.spines['bottom'].set_color('#45475a')
        ax.spines['left'].set_color('#45475a')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(True, color='#313244', linewidth=0.5, alpha=0.7)
        ax.ticklabel_format(style='plain', axis='y')
        fig.tight_layout(pad=2)
        return fig

    def _build_all_fig(self, x_data, prod):
        fig = Figure(figsize=(9, 6), dpi=100, facecolor='#181825')
        keys = ['sell_price', 'buy_price', 'sell_volume',
                'buy_volume', 'sell_order', 'buy_order']
        for idx, key in enumerate(keys):
            ax = fig.add_subplot(2, 3, idx + 1)
            ax.set_facecolor('#1e1e2e')
            ax.plot(x_data, prod.get(key, []), color='#89b4fa', linewidth=1.0)
            ax.set_title(key, color='#cdd6f4', fontsize=10)
            ax.tick_params(colors='#a6adc8', labelsize=8, rotation=45)
            ax.spines['bottom'].set_color('#45475a')
            ax.spines['left'].set_color('#45475a')
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.grid(True, color='#313244', linewidth=0.4, alpha=0.7)
            ax.ticklabel_format(style='plain', axis='y')
        fig.subplots_adjust(left=0.08, bottom=0.10, right=0.97, top=0.94,
                            wspace=0.30, hspace=0.45)
        return fig


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
