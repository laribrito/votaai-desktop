import csv
from PySide6.QtCore import QObject, Slot, Signal, Property, QAbstractTableModel, Qt, QSortFilterProxyModel

class CsvTableModel(QAbstractTableModel):
    def __init__(self, data=None, headers=None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self._headers = headers or []

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return self._data[index.row()][index.column()]
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if section < len(self._headers):
                return self._headers[section]
        return None

    def roleNames(self):
        return {Qt.DisplayRole: b"display"}

    def update_data(self, headers, data):
        self.beginResetModel()
        self._headers = headers
        self._data = data
        self.endResetModel()

class CsvController(QObject):
    modelChanged = Signal()

    def __init__(self, institutional_domain="@uesc.br"):
        super().__init__()
        self.institutional_domain = institutional_domain
        self._csv_model = CsvTableModel()
        self._proxy_model = QSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._csv_model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(-1)

    @Property(QObject, notify=modelChanged)
    def csvModel(self):
        return self._proxy_model

    @Slot(str)
    def search(self, query):
        self._proxy_model.setFilterFixedString(query)

    @Slot(str, result=str)
    def validateCsv(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers or len(headers) < 2:
                    self._csv_model.update_data([], [])
                    return "O CSV deve ter as colunas nomeCompleto e email."
                if headers[0].strip() != 'nomeCompleto' or headers[1].strip() != 'email':
                    self._csv_model.update_data([], [])
                    return "As colunas devem ser nomeCompleto e email."
                
                rows = []
                for row in reader:
                    if len(row) >= 2:
                        email = row[1].strip()
                        if not email.endswith(self.institutional_domain):
                            self._csv_model.update_data([], [])
                            return f"Apenas serão aceitos eleitores com emails institucionais ({self.institutional_domain})."
                        rows.append([row[0].strip(), email])
                
                if not rows:
                    self._csv_model.update_data([], [])
                    return "O arquivo CSV não contém nenhum eleitor válido."
                
                self._csv_model.update_data([h.strip() for h in headers[:2]], rows)
                self.modelChanged.emit()
                return ""
        except Exception as e:
            print(f"Erro ao ler CSV: {e}")
            self._csv_model.update_data([], [])
            return f"Erro ao ler o arquivo: {e}"

    @Slot(str)
    def saveTemplate(self, filepath):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"nomeCompleto,email\nJoão da Silva,joao{self.institutional_domain}\n")
        except Exception as e:
            print(f"Erro ao salvar template: {e}")
