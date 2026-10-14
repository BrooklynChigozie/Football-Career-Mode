"""A read-only, sortable table. Prosper may replace this with a themed version; keep the same methods."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


class _Item(QTableWidgetItem):
    """Sorts numbers numerically and text alphabetically."""

    def __init__(self, value):
        text = "" if value is None else (f"{value:.1f}" if isinstance(value, float) else str(value))
        super().__init__(text)
        self._num = isinstance(value, (int, float)) and not isinstance(value, bool)
        self._key = value if self._num else text.lower()
        if self._num:
            self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        if isinstance(other, _Item) and self._num == other._num:
            return self._key < other._key
        return super().__lt__(other)


class DataTable(QTableWidget):
    HIGHLIGHT = QColor(80, 140, 255, 70)

    def __init__(self, headers, parent=None):
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setStretchLastSection(True)

    def set_rows(self, rows, row_ids=None, highlight=None):
        """rows: list of lists. row_ids: optional id per row (read back with selected_id()).
        highlight: set of row indexes to tint (for example the user's club)."""
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = _Item(value)
                if c == 0 and row_ids is not None:
                    item.setData(Qt.ItemDataRole.UserRole, row_ids[r])
                if highlight and r in highlight:
                    item.setBackground(QBrush(self.HIGHLIGHT))
                self.setItem(r, c, item)
        self.setSortingEnabled(True)

    def selected_id(self):
        row = self.currentRow()
        if row < 0 or self.item(row, 0) is None:
            return None
        return self.item(row, 0).data(Qt.ItemDataRole.UserRole)