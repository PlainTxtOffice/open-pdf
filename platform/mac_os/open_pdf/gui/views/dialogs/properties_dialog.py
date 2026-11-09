"""Document-properties dialog for standard, custom, and XMP metadata."""

from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

type DocumentPropertyValues = tuple[
    dict[str, str],
    dict[str, str],
    str,
]

_PDF_INFO_PROPERTY_FIELDS = (
    ("title", "Title", True),
    ("author", "Author", True),
    ("subject", "Subject", True),
    ("keywords", "Keywords", True),
    ("creator", "Creator", True),
    ("producer", "Producer", True),
    ("creationDate", "Creation Date", True),
    ("modDate", "Modification Date", True),
    ("trapped", "Trapped", True),
    ("format", "Format", False),
    ("encryption", "Encryption", False),
)
_CUSTOM_PROPERTY_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_STANDARD_PDF_PROPERTY_NAMES = frozenset(
    {
        "Title",
        "Author",
        "Subject",
        "Keywords",
        "Creator",
        "Producer",
        "CreationDate",
        "ModDate",
        "Trapped",
    },
)


class DocumentPropertiesDialog(QDialog):
    """Edit the supported PDF document-property representations."""

    def __init__(
        self,
        *,
        current_info_dict: dict[str, str],
        current_custom_info_dict: dict[str, str],
        current_xmp_xml: str,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the dialog with the document's current properties."""
        super().__init__(parent)
        self._current_info_dict = current_info_dict
        self._accepted_values: DocumentPropertyValues | None = None
        self.setWindowTitle("Properties")
        self.resize(720, 560)

        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        layout.addWidget(tabs)
        tabs.addTab(self._build_info_tab(), "Info Dict")
        tabs.addTab(
            self._build_custom_tab(current_custom_info_dict),
            "Custom",
        )
        tabs.addTab(self._build_xmp_tab(current_xmp_xml), "XMP")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_info_tab(self) -> QWidget:
        info_tab = QWidget(self)
        info_layout = QFormLayout(info_tab)
        self._info_inputs: dict[str, QLineEdit] = {}
        for key, label, is_editable in _PDF_INFO_PROPERTY_FIELDS:
            field = QLineEdit(info_tab)
            field.setText(self._current_info_dict.get(key, ""))
            field.setReadOnly(not is_editable)
            info_layout.addRow(f"{label}:", field)
            if is_editable:
                self._info_inputs[key] = field
        return info_tab

    def _build_custom_tab(
        self,
        current_custom_info_dict: dict[str, str],
    ) -> QWidget:
        custom_tab = QWidget(self)
        layout = QVBoxLayout(custom_tab)
        explanation = QLabel(
            "Custom properties are stored inside the PDF. They may not be "
                "displayed by file managers. Names may contain letters, "
            "numbers, periods, underscores, and hyphens.",
            custom_tab,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self._custom_table = QTableWidget(custom_tab)
        self._custom_table.setObjectName("customPropertiesTable")
        self._custom_table.setColumnCount(2)
        self._custom_table.setHorizontalHeaderLabels(["Name", "Value"])
        self._custom_table.horizontalHeader().setStretchLastSection(True)
        self._custom_table.setColumnWidth(0, 240)
        self._custom_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows,
        )
        self._custom_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        for name, value in sorted(current_custom_info_dict.items()):
            self._append_custom_row(name, value)
        layout.addWidget(self._custom_table)

        button_layout = QHBoxLayout()
        add_button = QPushButton("Add", custom_tab)
        add_button.clicked.connect(self._add_custom_property)
        button_layout.addWidget(add_button)
        self._delete_button = QPushButton("Delete", custom_tab)
        self._delete_button.clicked.connect(self._delete_custom_property)
        button_layout.addWidget(self._delete_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        self._custom_table.itemSelectionChanged.connect(
            self._refresh_delete_button,
        )
        self._refresh_delete_button()
        return custom_tab

    def _build_xmp_tab(self, current_xmp_xml: str) -> QWidget:
        xmp_tab = QWidget(self)
        layout = QVBoxLayout(xmp_tab)
        self._xmp_input = QTextEdit(xmp_tab)
        self._xmp_input.setAcceptRichText(False)
        self._xmp_input.setPlaceholderText("No XMP metadata present.")
        self._xmp_input.setPlainText(current_xmp_xml)
        layout.addWidget(self._xmp_input)
        return xmp_tab

    def _append_custom_row(self, name: str, value: str) -> QTableWidgetItem:
        row = self._custom_table.rowCount()
        self._custom_table.insertRow(row)
        name_item = QTableWidgetItem(name)
        self._custom_table.setItem(row, 0, name_item)
        self._custom_table.setItem(row, 1, QTableWidgetItem(value))
        return name_item

    def _add_custom_property(self) -> None:
        name_item = self._append_custom_row("", "")
        row = self._custom_table.rowCount() - 1
        self._custom_table.setCurrentCell(row, 0)
        self._custom_table.editItem(name_item)

    def _delete_custom_property(self) -> None:
        selected_rows = {
            index.row() for index in self._custom_table.selectedIndexes()
        }
        for row in sorted(selected_rows, reverse=True):
            self._custom_table.removeRow(row)
        self._refresh_delete_button()

    def _refresh_delete_button(self) -> None:
        self._delete_button.setEnabled(
            bool(self._custom_table.selectedIndexes()),
        )

    def values(self) -> DocumentPropertyValues:
        """Return the edited properties after validating custom names."""
        info_dict = dict(self._current_info_dict)
        for key, field in self._info_inputs.items():
            info_dict[key] = field.text()

        custom_info_dict: dict[str, str] = {}
        for row in range(self._custom_table.rowCount()):
            name_item = self._custom_table.item(row, 0)
            value_item = self._custom_table.item(row, 1)
            name = "" if name_item is None else name_item.text().strip()
            if not name:
                msg = "Each custom property requires a name."
                raise ValueError(msg)
            if _CUSTOM_PROPERTY_NAME_RE.fullmatch(name) is None:
                msg = (
                    "Custom property names may contain only letters, "
                    "numbers, periods, underscores, and hyphens."
                )
                raise ValueError(msg)
            if name in _STANDARD_PDF_PROPERTY_NAMES:
                msg = f"{name} is a standard PDF property name."
                raise ValueError(msg)
            if name in custom_info_dict:
                msg = f"Custom property names must be unique: {name}"
                raise ValueError(msg)
            custom_info_dict[name] = (
                "" if value_item is None else value_item.text()
            )
        return info_dict, custom_info_dict, self._xmp_input.toPlainText()

    def _accept_if_valid(self) -> None:
        try:
            self._accepted_values = self.values()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid Custom Property", str(error))
            return
        self.accept()

    def accepted_values(self) -> DocumentPropertyValues:
        """Return the properties accepted through the dialog."""
        if self._accepted_values is None:
            msg = "Document properties have not been accepted."
            raise RuntimeError(msg)
        return self._accepted_values


def prompt_document_properties(
    *,
    current_info_dict: dict[str, str],
    current_custom_info_dict: dict[str, str],
    current_xmp_xml: str,
    parent: QWidget | None = None,
) -> DocumentPropertyValues | None:
    """Show the properties dialog and return accepted metadata values."""
    dialog = DocumentPropertiesDialog(
        current_info_dict=current_info_dict,
        current_custom_info_dict=current_custom_info_dict,
        current_xmp_xml=current_xmp_xml,
        parent=parent,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.accepted_values()
