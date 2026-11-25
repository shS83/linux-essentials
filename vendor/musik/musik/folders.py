"""One directory picker with multi-selection and a basket across locations."""
from pathlib import Path

from PySide6.QtCore import QDir, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QFileSystemModel, QHBoxLayout,
    QLabel, QListWidget, QPushButton, QTreeView, QVBoxLayout,
)


class FolderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add folders · including subfolders")
        self.resize(720, 620)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select folders with Ctrl / Shift. Add selections to collect folders from different locations."))
        self.model = QFileSystemModel(self)
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)
        self.model.setRootPath("")
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        for column in range(1, self.model.columnCount()):
            self.tree.hideColumn(column)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setHeaderHidden(True)
        home = self.model.index(QDir.homePath())
        self.tree.expand(home)
        self.tree.scrollTo(home)
        layout.addWidget(self.tree, 3)
        row = QHBoxLayout()
        add = QPushButton("Add selected folders ↓")
        add.clicked.connect(self.collect)
        row.addWidget(add)
        remove = QPushButton("Remove from selection")
        remove.clicked.connect(self.remove_selected)
        row.addWidget(remove)
        layout.addLayout(row)
        layout.addWidget(QLabel("Folders to import (subfolders included):"))
        self.basket = QListWidget()
        self.basket.setStyleSheet("QListWidget { background: #201b29; border: 1px solid #786780; border-radius: 6px; }")
        self.basket.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.basket, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def collect(self):
        existing = {self.basket.item(i).text().casefold() for i in range(self.basket.count())}
        for index in self.tree.selectionModel().selectedRows():
            path = self.model.filePath(index)
            if Path(path).is_dir() and path.casefold() not in existing:
                self.basket.addItem(path)
                existing.add(path.casefold())
        self.tree.clearSelection()

    def remove_selected(self):
        for item in self.basket.selectedItems():
            self.basket.takeItem(self.basket.row(item))

    def accept(self):
        self.collect()
        if self.basket.count():
            super().accept()

    def folders(self):
        return [self.basket.item(i).text() for i in range(self.basket.count())]


def choose_folders(parent=None):
    dialog = FolderDialog(parent)
    return dialog.folders() if dialog.exec() == QDialog.DialogCode.Accepted else []
