import base64
import json
import struct
import sys
import zlib
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QImage, QTextDocument
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QSplitter, QTextBrowser, QVBoxLayout, QWidget,
)

MAGIC = b"MSTAJUDA\x01"


def encode_help(payload: dict) -> bytes:
    """Serializa o contêiner .ajuda com versão, compressão e verificação CRC32."""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, 9)
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    return MAGIC + struct.pack(">II", len(compressed), crc) + compressed


def decode_help(data: bytes) -> dict:
    if not data.startswith(MAGIC) or len(data) < len(MAGIC) + 8:
        raise ValueError("Arquivo .ajuda inválido ou incompatível.")
    offset = len(MAGIC)
    size, expected_crc = struct.unpack(">II", data[offset:offset + 8])
    compressed = data[offset + 8:offset + 8 + size]
    if len(compressed) != size:
        raise ValueError("Arquivo .ajuda truncado.")
    raw = zlib.decompress(compressed)
    if (zlib.crc32(raw) & 0xFFFFFFFF) != expected_crc:
        raise ValueError("Falha de integridade no arquivo .ajuda.")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("topics"), list):
        raise ValueError("Estrutura .ajuda inválida.")
    return payload


def write_help(path, payload: dict):
    Path(path).write_bytes(encode_help(payload))


def read_help(path) -> dict:
    return decode_help(Path(path).read_bytes())


def project_to_help_payload(project) -> dict:
    """Compila todo o projeto em um único binário .ajuda, inclusive idiomas e imagens."""
    languages = list(project.languages())
    topics = []
    for topic in project.topics:
        titles = {lang: project.topic_title(topic, lang) for lang in languages}
        bodies = {lang: project.topic_html(topic, lang) for lang in languages}
        topics.append({
            "id": topic.id,
            "parent_id": topic.parent_id,
            "order": topic.order,
            "kind": topic.kind,
            "titles": titles,
            "bodies": bodies,
        })
    assets = {
        aid: {
            "filename": asset.filename,
            "mime": asset.mime,
            "data_b64": asset.data_b64,
        }
        for aid, asset in project.assets.items()
    }
    return {
        "format": 2,
        "kind": "manual",
        "title": str(project.meta.get("title", "Manual")),
        "version": str(project.meta.get("version", "1.0")),
        "default_language": str(project.meta.get("language", "pt-BR")),
        "languages": languages,
        "topics": topics,
        "assets": assets,
    }


def export_project_help(project, path):
    path = str(path)
    if not path.lower().endswith(".ajuda"):
        path += ".ajuda"
    write_help(path, project_to_help_payload(project))
    return path


def bundled_help_path() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "manual_studio.ajuda"
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "manual_studio.ajuda"
    return Path(__file__).resolve().parent.parent / "manual_studio.ajuda"


class HelpViewerDialog(QDialog):
    """Visualizador simples do formato .ajuda; já suporta arquivos multilíngues do editor."""
    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload
        self.all_topics = list(payload.get("topics") or [])
        self.visible_topics = []
        self.languages = list(payload.get("languages") or [])
        self.current_language = str(payload.get("default_language") or (self.languages[0] if self.languages else ""))
        self.setWindowTitle(str(payload.get("title") or "Ajuda"))
        self.resize(1000, 700)

        root = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Pesquisar:"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Digite um termo da ajuda...")
        self.search.textChanged.connect(self._rebuild)
        top.addWidget(self.search, 1)
        if self.languages:
            top.addWidget(QLabel("Idioma:"))
            self.language = QComboBox()
            for lang in self.languages:
                self.language.addItem(lang, lang)
            idx = self.language.findData(self.current_language)
            self.language.setCurrentIndex(max(0, idx))
            self.language.currentIndexChanged.connect(self._change_language)
            top.addWidget(self.language)
        root.addLayout(top)

        split = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._show_topic)
        left_layout.addWidget(self.list)
        split.addWidget(left)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self._register_assets()
        split.addWidget(self.browser)
        split.setSizes([280, 720])
        root.addWidget(split, 1)
        self._rebuild()

    def _register_assets(self):
        for aid, raw in (self.payload.get("assets") or {}).items():
            try:
                data = base64.b64decode(str(raw.get("data_b64") or "").encode("ascii"))
                image = QImage.fromData(data)
                if not image.isNull():
                    self.browser.document().addResource(
                        QTextDocument.ImageResource, QUrl("asset://" + str(aid)), image
                    )
            except Exception:
                continue

    def _change_language(self):
        self.current_language = str(self.language.currentData() or "")
        self._rebuild()

    def _topic_text(self, topic):
        # Formato 2: textos por idioma. Formato 1: título/html direto.
        if "titles" in topic or "bodies" in topic:
            titles = topic.get("titles") or {}
            bodies = topic.get("bodies") or {}
            default = str(self.payload.get("default_language") or "")
            title = str(titles.get(self.current_language) or titles.get(default) or next(iter(titles.values()), "Tópico"))
            body = str(bodies.get(self.current_language) or bodies.get(default) or next(iter(bodies.values()), ""))
            return title, body
        return str(topic.get("title") or "Tópico"), str(topic.get("html") or "")

    def _rebuild(self):
        needle = self.search.text().strip().lower()
        self.visible_topics = []
        self.list.clear()
        ordered = sorted(self.all_topics, key=lambda t: (int(t.get("order", 0)), self._topic_text(t)[0].lower()))
        for topic in ordered:
            title, body = self._topic_text(topic)
            plain = body.replace("<", " ").replace(">", " ").lower()
            if needle and needle not in title.lower() and needle not in plain:
                continue
            self.visible_topics.append(topic)
            self.list.addItem(title)
        if self.visible_topics:
            self.list.setCurrentRow(0)
        else:
            self.browser.setHtml("<p>Nenhum resultado.</p>")

    def _show_topic(self, row):
        if 0 <= row < len(self.visible_topics):
            topic = self.visible_topics[row]
            title, body = self._topic_text(topic)
            self._register_assets()
            self.browser.setHtml(
                "<style>body{font-family:'Segoe UI',Arial;font-size:10.5pt;color:#222;}"
                "h1{font-size:20pt;} h2{font-size:15pt;} code{background:#eee;padding:2px 4px;}"
                "table{border-collapse:collapse;}td,th{border:1px solid #bbb;padding:5px;}img{max-width:100%;height:auto;}</style>"
                f"<h1>{title}</h1>{body}"
            )
            # setHtml pode limpar recursos dependendo da versão do Qt; registre novamente.
            self._register_assets()


def open_help_file(parent=None, path=None):
    if path is None:
        path = bundled_help_path()
    try:
        payload = read_help(path)
    except Exception as exc:
        QMessageBox.warning(parent, "Ajuda", f"Não foi possível abrir o arquivo de ajuda.\n\n{exc}")
        return
    HelpViewerDialog(payload, parent).exec_()


def choose_and_open_help(parent=None):
    path, _ = QFileDialog.getOpenFileName(parent, "Abrir arquivo de ajuda", "", "Manual Studio Help (*.ajuda);;Todos (*.*)")
    if path:
        open_help_file(parent, path)
