from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem


class SortItem(QTableWidgetItem):
    """Table item that sorts by a numeric/text key instead of its display text."""

    def __init__(self, text: str, key=None, align_right: bool = False):
        super().__init__(text)
        self._key = text if key is None else key
        self.setFlags(self.flags() & ~Qt.ItemIsEditable)
        if align_right:
            self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, other):
        return self._key < getattr(other, "_key", other.text())


def make_table(headers: list[str], sortable: bool = True, stretch_col: int | None = None) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    h = t.horizontalHeader()
    h.setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_col is not None and stretch_col >= 0:
        h.setSectionResizeMode(stretch_col, QHeaderView.Stretch)
    elif stretch_col is None:
        h.setStretchLastSection(True)
    h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    t.verticalHeader().setDefaultSectionSize(36)
    t.setSortingEnabled(sortable)
    return t
