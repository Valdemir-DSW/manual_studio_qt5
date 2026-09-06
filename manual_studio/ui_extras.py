import html
from pathlib import Path

from PyQt5.QtCore import Qt, pyqtSignal, QSizeF, QRectF, QPointF, QUrl, QTimer, QBuffer, QByteArray, QIODevice
from PyQt5.QtGui import QColor, QBrush, QLinearGradient, QPainter, QPen, QFont, QImage, QTextDocument
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QDoubleSpinBox, QTextEdit, QTextBrowser, QColorDialog, QVBoxLayout, QWidget, QTabWidget,
)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineProfile
    from PyQt5.QtWebEngineCore import QWebEngineUrlSchemeHandler
except Exception:
    QWebEngineView = None
    QWebEnginePage = None
    QWebEngineProfile = None
    QWebEngineUrlSchemeHandler = None


if QWebEngineUrlSchemeHandler is not None:
    class _MemoryPreviewSchemeHandler(QWebEngineUrlSchemeHandler):
        """Serve o HTML da prévia direto de bytes em memória, sem diretório temporário."""
        def __init__(self, parent=None):
            super().__init__(parent)
            self._html = b"<html><body></body></html>"

        def set_html(self, text):
            self._html = str(text).encode("utf-8")

        def requestStarted(self, job):
            data = QByteArray(self._html)
            buf = QBuffer(job)
            buf.setData(data)
            buf.open(QIODevice.ReadOnly)
            job.reply(QByteArray(b"text/html"), buf)
else:
    _MemoryPreviewSchemeHandler = None


PAGE_DIMS = {
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "Carta": (215.9, 279.4),
    "Ofício": (215.9, 355.6),
}

LANG_NAMES = {
    "pt-BR": "Português (Brasil)",
    "en-US": "English (US)",
    "es-ES": "Español",
    "de-DE": "Deutsch",
    "fr-FR": "Français",
    "it-IT": "Italiano",
}


def _color_button_text(color):
    c = QColor(color)
    return c.name() if c.isValid() else "#ffffff"


class MarginRuler(QWidget):
    """Régua horizontal estilo editor de texto, com margens arrastáveis e proteção."""

    marginsChanging = pyqtSignal(float, float, bool)  # left, right, dragging
    marginsCommitted = pyqtSignal(float, float)

    def __init__(self, project_getter, parent=None, editor_getter=None):
        super().__init__(parent)
        self._project_getter = project_getter
        self._editor_getter = editor_getter
        self._drag = None
        self.setMinimumHeight(42)
        self.setMaximumHeight(42)
        self.setMouseTracking(True)
        self.setToolTip("Arraste os marcadores para ajustar as margens esquerda e direita. A área útil mínima é protegida.")

    def _meta(self):
        p = self._project_getter()
        return p.meta if p else {}

    def _page_width_mm(self):
        m = self._meta()
        w, h = PAGE_DIMS.get(str(m.get("page_size", "A4")), PAGE_DIMS["A4"])
        if m.get("page_orientation", "portrait") == "landscape":
            w, h = h, w
        return float(w)

    def _geometry(self):
        # Sempre que possível, a régua mede a mesma largura física mostrada
        # pelo QTextDocument. Isso evita o marcador dizer 20 mm enquanto o
        # texto usa outra escala porque a janela foi redimensionada.
        x0 = 4.0
        available = max(10.0, self.width() - 8.0)
        span = available
        if self._editor_getter:
            try:
                editor = self._editor_getter()
                if editor is not None:
                    span = min(available, max(10.0, float(editor.page_width_px())))
            except Exception:
                pass
        x1 = x0 + span
        return x0, x1, span

    def _x_for_mm(self, mm):
        x0, _x1, span = self._geometry()
        return x0 + max(0.0, min(self._page_width_mm(), mm)) / self._page_width_mm() * span

    def _mm_for_x(self, x):
        x0, _x1, span = self._geometry()
        return max(0.0, min(self._page_width_mm(), (x - x0) / span * self._page_width_mm()))

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        m = self._meta()
        page_w = self._page_width_mm()
        left = float(m.get("margin_left_mm", 18))
        right = float(m.get("margin_right_mm", 18))
        x0, x1, span = self._geometry()
        base_y = 27

        p.fillRect(self.rect(), QColor("#f1f3f5"))
        p.fillRect(QRectF(x0, 6, span, 25), QColor("#ffffff"))
        p.fillRect(QRectF(x0, 6, self._x_for_mm(left) - x0, 25), QColor("#d9dde2"))
        right_x = self._x_for_mm(page_w - right)
        p.fillRect(QRectF(right_x, 6, x1 - right_x, 25), QColor("#d9dde2"))
        p.setPen(QPen(QColor("#aab0b7"), 1))
        p.drawRect(QRectF(x0, 6, span, 25))

        # marcações de 5 mm, números a cada 10 mm
        for mm in range(0, int(page_w) + 1, 5):
            x = self._x_for_mm(mm)
            major = (mm % 10 == 0)
            p.setPen(QColor("#666b72"))
            p.drawLine(int(x), base_y - (8 if major else 4), int(x), base_y)
            if major and mm not in (0, int(page_w)):
                p.setFont(QFont("Arial", 7))
                p.drawText(QRectF(x - 15, 7, 30, 11), Qt.AlignHCenter | Qt.AlignTop, str(mm))

        # marcadores triangulares
        p.setBrush(QColor("#1769aa"))
        p.setPen(Qt.NoPen)
        lx = self._x_for_mm(left)
        rx = self._x_for_mm(page_w - right)
        from PyQt5.QtGui import QPolygonF
        from PyQt5.QtCore import QPointF
        p.drawPolygon(QPolygonF([QPointF(lx-6, 34), QPointF(lx+6, 34), QPointF(lx, 27)]))
        p.drawPolygon(QPolygonF([QPointF(rx-6, 34), QPointF(rx+6, 34), QPointF(rx, 27)]))
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        m = self._meta()
        page_w = self._page_width_mm()
        left_x = self._x_for_mm(float(m.get("margin_left_mm", 18)))
        right_x = self._x_for_mm(page_w - float(m.get("margin_right_mm", 18)))
        if abs(event.x() - left_x) <= 12:
            self._drag = "left"
        elif abs(event.x() - right_x) <= 12:
            self._drag = "right"
        if self._drag:
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._drag:
            return super().mouseMoveEvent(event)
        m = self._meta()
        page_w = self._page_width_mm()
        min_usable = 40.0
        left = float(m.get("margin_left_mm", 18))
        right = float(m.get("margin_right_mm", 18))
        pos_mm = self._mm_for_x(event.x())
        if self._drag == "left":
            left = max(0.0, min(pos_mm, page_w - right - min_usable))
        else:
            right = max(0.0, min(page_w - pos_mm, page_w - left - min_usable))
        m["margin_left_mm"] = round(left, 1)
        m["margin_right_mm"] = round(right, 1)
        self.marginsChanging.emit(left, right, True)
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag and event.button() == Qt.LeftButton:
            m = self._meta()
            left = float(m.get("margin_left_mm", 18))
            right = float(m.get("margin_right_mm", 18))
            self._drag = None
            self.marginsChanging.emit(left, right, False)
            self.marginsCommitted.emit(left, right)
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Novo manual")
        self.resize(520, 320)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Escolha uma base. Tudo pode ser alterado depois."))
        self.combo = QComboBox()
        self.combo.addItem("Em branco — somente Introdução", "blank")
        self.combo.addItem("Manual técnico — estrutura completa", "technical")
        self.combo.addItem("Manual de software — estrutura completa", "software")
        root.addWidget(self.combo)
        info = QLabel(
            "Os modelos completos incluem capítulos usuais e histórico de revisões. "
            "A Introdução nasce sem cabeçalho/rodapé para funcionar como página inicial limpa."
        )
        info.setWordWrap(True)
        root.addWidget(info)
        root.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def template(self):
        return str(self.combo.currentData() or "blank")


class TopicPageOptionsDialog(QDialog):
    def __init__(self, topic, parent=None):
        super().__init__(parent)
        self.topic = topic
        self.setWindowTitle("Opções da página/tópico")
        self.resize(480, 300)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.header = QComboBox(); self.footer = QComboBox()
        for box in (self.header, self.footer):
            box.addItem("Usar padrão do documento", None)
            box.addItem("Exibir", True)
            box.addItem("Ocultar", False)
        self._set_nullable(self.header, topic.show_header)
        self._set_nullable(self.footer, topic.show_footer)
        self.exclude = QCheckBox("Não incluir este tópico no sumário automático")
        self.exclude.setChecked(bool(topic.exclude_from_toc))
        form.addRow("Cabeçalho:", self.header)
        form.addRow("Rodapé:", self.footer)
        form.addRow(self.exclude)
        root.addLayout(form)
        note = QLabel("O padrão é herdar o documento. Para páginas de introdução, capa local ou sumário especial, você pode ocultar individualmente.")
        note.setWordWrap(True); note.setStyleSheet("color:#666")
        root.addWidget(note); root.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _set_nullable(self, box, value):
        idx = box.findData(value)
        box.setCurrentIndex(max(0, idx))

    def apply(self):
        self.topic.show_header = self.header.currentData()
        self.topic.show_footer = self.footer.currentData()
        self.topic.exclude_from_toc = self.exclude.isChecked()


class LanguageManagerDialog(QDialog):
    """Gerenciador de idiomas com uma fonte editorial explícita e cópias seguras."""
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.original_languages = list(project.languages())
        self.pending_copies = []
        self.setWindowTitle("Gerenciador de idiomas")
        self.resize(760, 640)
        root = QVBoxLayout(self)

        info = QLabel(
            "A estrutura de tópicos é única para todos os idiomas. O idioma padrão é a fonte editorial. "
            "Você pode copiar seus títulos e textos para novos idiomas e depois traduzir cada cópia sem tradução automática."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        source_group = QGroupBox("Idioma padrão / fonte")
        source_form = QFormLayout(source_group)
        self.default = QComboBox()
        existing = project.languages()
        codes = list(LANG_NAMES.keys()) + [c for c in existing if c not in LANG_NAMES]
        for code in codes:
            self.default.addItem(f"{LANG_NAMES.get(code, code)} — {code}", code)
        idx = self.default.findData(str(project.meta.get("language", "pt-BR")))
        self.default.setCurrentIndex(max(0, idx))
        source_form.addRow("Idioma padrão:", self.default)
        root.addWidget(source_group)

        langs_group = QGroupBox("Idiomas incluídos no manual")
        langs_layout = QVBoxLayout(langs_group)
        self.grid = QGridLayout()
        self.checks = {}
        active = set(existing)
        for code in codes:
            self._add_language_check(code, code in active)
        langs_layout.addLayout(self.grid)
        custom_row = QHBoxLayout()
        self.custom = QLineEdit()
        self.custom.setPlaceholderText("Código BCP-47, ex.: pt-PT, ja-JP")
        add = QPushButton("Adicionar idioma")
        add.clicked.connect(self._add_custom)
        custom_row.addWidget(self.custom, 1)
        custom_row.addWidget(add)
        langs_layout.addLayout(custom_row)
        root.addWidget(langs_group)

        behavior = QGroupBox("Comportamento de cópia")
        behavior_layout = QVBoxLayout(behavior)
        self.copy_on_add = QCheckBox("Ao adicionar um idioma, copiar títulos e textos do idioma padrão")
        self.copy_on_add.setChecked(bool(project.meta.get("language_copy_on_add", True)))
        self.sync_untranslated = QCheckBox("Quando o padrão mudar, atualizar apenas cópias que ainda não foram traduzidas")
        self.sync_untranslated.setChecked(bool(project.meta.get("language_sync_untranslated_from_default", True)))
        self.seed_new_topics = QCheckBox("Ao criar novos tópicos, criar a mesma cópia nos demais idiomas")
        self.seed_new_topics.setChecked(bool(project.meta.get("language_seed_new_topics", True)))
        for cb in (self.copy_on_add, self.sync_untranslated, self.seed_new_topics):
            behavior_layout.addWidget(cb)
        note = QLabel(
            "A sincronização nunca deve sobrescrever texto já traduzido: ela só acompanha cópias ainda idênticas à última versão da fonte."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#666")
        behavior_layout.addWidget(note)
        root.addWidget(behavior)

        copy_group = QGroupBox("Cópia manual entre idiomas")
        copy_layout = QGridLayout(copy_group)
        self.copy_source = QComboBox()
        self.copy_target = QComboBox()
        self._refresh_copy_combos()
        copy_layout.addWidget(QLabel("Origem:"), 0, 0)
        copy_layout.addWidget(self.copy_source, 0, 1)
        copy_layout.addWidget(QLabel("Destino:"), 1, 0)
        copy_layout.addWidget(self.copy_target, 1, 1)
        queue_btn = QPushButton("Copiar estrutura textual →")
        queue_btn.setToolTip("A árvore é compartilhada; esta ação copia os títulos e o conteúdo de todos os tópicos.")
        queue_btn.clicked.connect(self._queue_copy)
        copy_layout.addWidget(queue_btn, 0, 2, 2, 1)
        self.copy_status = QLabel("Nenhuma cópia manual agendada.")
        self.copy_status.setWordWrap(True)
        self.copy_status.setStyleSheet("color:#666")
        copy_layout.addWidget(self.copy_status, 2, 0, 1, 3)
        root.addWidget(copy_group)

        root.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _all_codes(self):
        codes = []
        for code in list(self.checks.keys()):
            if code not in codes:
                codes.append(code)
        default = str(self.default.currentData() or "pt-BR")
        if default not in codes:
            codes.insert(0, default)
        return codes

    def _refresh_copy_combos(self):
        current_source = self.copy_source.currentData() if hasattr(self, "copy_source") else None
        current_target = self.copy_target.currentData() if hasattr(self, "copy_target") else None
        if not hasattr(self, "copy_source"):
            return
        self.copy_source.clear(); self.copy_target.clear()
        for code in self._all_codes():
            label = f"{LANG_NAMES.get(code, code)} — {code}"
            self.copy_source.addItem(label, code)
            self.copy_target.addItem(label, code)
        if current_source:
            i = self.copy_source.findData(current_source)
            if i >= 0: self.copy_source.setCurrentIndex(i)
        if current_target:
            i = self.copy_target.findData(current_target)
            if i >= 0: self.copy_target.setCurrentIndex(i)
        elif self.copy_target.count() > 1:
            self.copy_target.setCurrentIndex(1)

    def _add_language_check(self, code, checked=True):
        if code in self.checks:
            self.checks[code].setChecked(checked or self.checks[code].isChecked())
            return
        cb = QCheckBox(f"{LANG_NAMES.get(code, code)} — {code}")
        cb.setChecked(bool(checked))
        self.checks[code] = cb
        i = len(self.checks) - 1
        self.grid.addWidget(cb, i // 2, i % 2)
        if hasattr(self, "copy_source"):
            self._refresh_copy_combos()

    def _add_custom(self):
        code = self.custom.text().strip()
        if not code or " " in code or len(code) > 24:
            QMessageBox.warning(self, "Idioma", "Informe um código de idioma válido, por exemplo pt-PT ou ja-JP.")
            return
        self._add_language_check(code, True)
        if self.default.findData(code) < 0:
            self.default.addItem(f"{LANG_NAMES.get(code, code)} — {code}", code)
        self.custom.clear()
        self._refresh_copy_combos()

    def _queue_copy(self):
        source = str(self.copy_source.currentData() or "")
        target = str(self.copy_target.currentData() or "")
        if not source or not target or source == target:
            QMessageBox.information(self, "Copiar idioma", "Escolha dois idiomas diferentes.")
            return
        answer = QMessageBox.question(
            self,
            "Copiar conteúdo do idioma",
            f"Copiar todos os títulos e textos de {source} para {target}?\n\n"
            "O conteúdo existente no idioma de destino será substituído. A estrutura de tópicos não é duplicada porque já é comum a todos os idiomas.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.pending_copies.append((source, target))
        self.copy_status.setText("Cópias agendadas: " + ", ".join(f"{a} → {b}" for a, b in self.pending_copies))

    def apply(self):
        default = str(self.default.currentData() or "pt-BR")
        langs = [code for code, cb in self.checks.items() if cb.isChecked()]
        if default not in langs:
            langs.insert(0, default)

        # Primeiro define a fonte editorial; depois cria as cópias dos novos idiomas.
        self.project.change_default_language(default)
        self.project.meta["language_copy_on_add"] = self.copy_on_add.isChecked()
        self.project.meta["language_sync_untranslated_from_default"] = self.sync_untranslated.isChecked()
        self.project.meta["language_seed_new_topics"] = self.seed_new_topics.isChecked()
        self.project.meta["languages"] = [default] + [x for x in langs if x != default]

        if self.copy_on_add.isChecked():
            for lang in self.project.meta["languages"]:
                if lang != default and lang not in self.original_languages:
                    self.project.seed_language_from_default(lang, overwrite=False)

        for source, target in self.pending_copies:
            if source in self.project.meta["languages"] and target in self.project.meta["languages"]:
                self.project.copy_language(source, target, overwrite=True, mark_seeded=(source == default))


class PdfCoverPreview(QWidget):
    """Prévia proporcional da capa. Arrastar reposiciona a imagem de fundo."""
    backgroundPositionChanged = pyqtSignal(float, float)

    def __init__(self, project, meta_getter, parent=None):
        super().__init__(parent)
        self.project = project
        self.meta_getter = meta_getter
        self._dragging_bg = False
        self.setMinimumSize(310, 430)
        self.setToolTip("Prévia da capa. Quando houver imagem de fundo, arraste sobre a folha para reposicioná-la.")

    def _page_rect(self):
        m = self.meta_getter()
        w_mm, h_mm = PAGE_DIMS.get(str(m.get("page_size", "A4")), PAGE_DIMS["A4"])
        if m.get("page_orientation", "portrait") == "landscape":
            w_mm, h_mm = h_mm, w_mm
        outer = QRectF(14, 14, max(20, self.width() - 28), max(20, self.height() - 28))
        ratio = w_mm / h_mm
        if outer.width() / outer.height() > ratio:
            h = outer.height(); w = h * ratio
        else:
            w = outer.width(); h = w / ratio
        return QRectF(outer.center().x() - w/2, outer.center().y() - h/2, w, h), w_mm, h_mm

    def _asset_image(self, asset_id, preview_path_key=""):
        m = self.meta_getter()
        path = str(m.get(preview_path_key, "") or "") if preview_path_key else ""
        if path:
            img = QImage(path)
            if not img.isNull():
                return img
        asset = self.project.assets.get(asset_id)
        return QImage.fromData(asset.bytes()) if asset else QImage()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor("#e9ecef"))
        page, w_mm, h_mm = self._page_rect()
        p.setPen(QPen(QColor("#aab1b9"), 1))
        p.setBrush(QColor("white"))
        p.drawRect(page)
        m = self.meta_getter()

        # Fundo
        kind = str(m.get("pdf_cover_background_type", "none"))
        c1 = QColor(str(m.get("pdf_cover_background_color1", "#ffffff")))
        c2 = QColor(str(m.get("pdf_cover_background_color2", "#e9edf2")))
        p.save(); p.setClipRect(page)
        if kind == "solid":
            p.fillRect(page, c1)
        elif kind == "gradient":
            direction = str(m.get("pdf_cover_gradient_direction", "vertical"))
            if direction == "horizontal": g = QLinearGradient(page.left(), page.top(), page.right(), page.top())
            elif direction == "diagonal": g = QLinearGradient(page.left(), page.top(), page.right(), page.bottom())
            else: g = QLinearGradient(page.left(), page.top(), page.left(), page.bottom())
            g.setColorAt(0, c1); g.setColorAt(1, c2); p.fillRect(page, QBrush(g))
        elif kind == "image":
            img = self._asset_image(str(m.get("pdf_cover_background_asset", "")), "_preview_cover_background_path")
            if not img.isNull():
                p.fillRect(page, c1)
                fit = str(m.get("pdf_cover_background_fit", "cover"))
                scale = max(10.0, min(400.0, float(m.get("pdf_cover_background_scale_percent", 100)))) / 100.0
                if fit == "stretch":
                    sw = max(1, int(page.width()*scale)); sh = max(1, int(page.height()*scale))
                    scaled = img.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                else:
                    mode = Qt.KeepAspectRatioByExpanding if fit == "cover" else Qt.KeepAspectRatio
                    base = img.scaled(max(1,int(page.width())), max(1,int(page.height())), mode, Qt.SmoothTransformation)
                    scaled = base.scaled(max(1,int(base.width()*scale)), max(1,int(base.height()*scale)), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                xpos = max(0.0,min(100.0,float(m.get("pdf_cover_background_x_percent",50))))/100.0
                ypos = max(0.0,min(100.0,float(m.get("pdf_cover_background_y_percent",50))))/100.0
                cx = page.left()+page.width()*xpos; cy = page.top()+page.height()*ypos
                x = cx-scaled.width()/2; y = cy-scaled.height()/2
                p.setOpacity(max(0.0,min(100.0,float(m.get("pdf_cover_background_opacity",100))))/100.0)
                p.drawImage(QRectF(x,y,scaled.width(),scaled.height()),scaled)
        p.restore()

        # Guias das margens físicas
        ml=float(m.get("margin_left_mm",18)); mr=float(m.get("margin_right_mm",18)); mt=float(m.get("margin_top_mm",16)); mb=float(m.get("margin_bottom_mm",16))
        safe = QRectF(page.left()+page.width()*ml/w_mm, page.top()+page.height()*mt/h_mm,
                      page.width()*(w_mm-ml-mr)/w_mm, page.height()*(h_mm-mt-mb)/h_mm)
        p.setPen(QPen(QColor(100,110,120,95), 1, Qt.DashLine)); p.setBrush(Qt.NoBrush); p.drawRect(safe)

        # Cabeçalho/rodapé da capa quando habilitados.
        self._draw_cover_band(p, page, w_mm, h_mm, "header", bool(m.get("pdf_header_on_cover", False)))
        self._draw_cover_band(p, page, w_mm, h_mm, "footer", bool(m.get("pdf_footer_on_cover", False)))

        # Conteúdo principal da capa
        align = str(m.get("pdf_cover_alignment", "center"))
        x_align = Qt.AlignLeft if align=="left" else (Qt.AlignRight if align=="right" else Qt.AlignHCenter)
        y = page.top() + page.height()*max(0.0,min(h_mm,float(m.get("pdf_cover_vertical_offset_mm",42))))/h_mm
        logo_id = str(m.get("pdf_cover_logo_asset", "") or m.get("logo_asset", ""))
        logo = self._asset_image(logo_id, "_preview_cover_logo_path")
        if bool(m.get("pdf_cover_show_logo",True)) and not logo.isNull():
            target_w = page.width()*float(m.get("pdf_cover_logo_width_mm",42))/w_mm
            scaled = logo.scaledToWidth(max(1,int(target_w)), Qt.SmoothTransformation)
            if align=="left": lx=safe.left()
            elif align=="right": lx=safe.right()-scaled.width()
            else: lx=page.center().x()-scaled.width()/2
            p.drawImage(QPointF(lx,y),scaled); y += scaled.height()+page.height()*7/h_mm

        title = str(m.get("pdf_cover_title", "") or m.get("title", "Manual"))
        if bool(m.get("pdf_cover_show_title",True)):
            font=QFont(str(m.get("body_font_family","Arial"))); font.setBold(True)
            font.setPointSizeF(max(8.0,float(m.get("pdf_cover_title_size_pt",30))*min(1.0,page.width()/500.0)))
            p.setFont(font); p.setPen(QColor(str(m.get("pdf_cover_title_color","#1f2933"))))
            tr=QRectF(safe.left(),y,safe.width(),max(40,page.height()*0.16)); p.drawText(tr, x_align|Qt.TextWordWrap, title)
            y += max(38, page.height()*0.11)
        p.setPen(QColor("#4f5965"))
        font=QFont(str(m.get("body_font_family","Arial"))); font.setPointSizeF(max(7.0, 11*min(1.0,page.width()/500.0))); p.setFont(font)
        subtitle=str(m.get("pdf_cover_subtitle", ""))
        details=[]
        if subtitle: details.append(subtitle)
        if bool(m.get("pdf_cover_show_author",True)) and m.get("author"): details.append(str(m.get("author")))
        if bool(m.get("pdf_cover_show_version",True)) and m.get("version"): details.append("Versão "+str(m.get("version")))
        if bool(m.get("pdf_cover_show_language",True)) and len(self.project.languages())>1: details.append(str(m.get("language","pt-BR")))
        if details:
            p.drawText(QRectF(safe.left(),y,safe.width(),safe.bottom()-y), x_align|Qt.TextWordWrap, "\n".join(details))

        p.setPen(QColor("#68717b")); p.drawText(QRectF(page.left(),page.bottom()+2,page.width(),18),Qt.AlignCenter,"Prévia proporcional • linha pontilhada = margens")
        p.end()

    def _draw_cover_band(self, painter, page, w_mm, h_mm, section, enabled_on_cover):
        m = self.meta_getter()
        if not enabled_on_cover or not bool(m.get(f"{section}_enabled", True)):
            return
        ml=float(m.get("margin_left_mm",18)); mr=float(m.get("margin_right_mm",18))
        h=float(m.get(f"{section}_height_mm",8 if section=="header" else 9))
        x=page.left()+page.width()*ml/w_mm; width=page.width()*(w_mm-ml-mr)/w_mm
        y=page.top()+page.height()*float(m.get("margin_top_mm",16))/h_mm if section=="header" else page.bottom()-page.height()*(float(m.get("margin_bottom_mm",16))+h)/h_mm
        rect=QRectF(x,y,width,page.height()*h/h_mm)
        kind=str(m.get(f"{section}_background_type","none")); c1=QColor(str(m.get(f"{section}_background_color1","#ffffff"))); c2=QColor(str(m.get(f"{section}_background_color2","#e9edf2")))
        painter.save(); painter.setOpacity(max(0.0,min(100.0,float(m.get(f"{section}_background_opacity",100))))/100.0)
        if kind=="solid": painter.fillRect(rect,c1)
        elif kind=="gradient":
            direction=str(m.get(f"{section}_gradient_direction","horizontal")); g=QLinearGradient(rect.left(),rect.top(),rect.right() if direction!="vertical" else rect.left(),rect.bottom() if direction!="horizontal" else rect.top()); g.setColorAt(0,c1); g.setColorAt(1,c2); painter.fillRect(rect,QBrush(g))
        painter.restore()
        template=str(m.get(f"{section}_template_html","<p></p>")); values={"title":str(m.get("title","Manual")),"author":str(m.get("author","")),"version":str(m.get("version","1.0")),"page":"1","pages":"1","topic":"","category":"","date":"06/09/2026","language":str(m.get("language","pt-BR")),"footer_text":str(m.get("footer_text",""))}
        for k,v in values.items(): template=template.replace("{{"+k+"}}",html.escape(v))
        logo_id=str(m.get("logo_asset",""))
        if logo_id in self.project.assets: template=template.replace("{{logo}}",f'<img src="asset://{logo_id}" width="32">')
        else: template=template.replace("{{logo}}","")
        doc=QTextDocument(); doc.setDocumentMargin(0)
        for aid,asset in self.project.assets.items():
            img=QImage.fromData(asset.bytes())
            if not img.isNull(): doc.addResource(QTextDocument.ImageResource,QUrl("asset://"+aid),img)
        doc.setHtml(template); doc.setTextWidth(max(1,rect.width()-8))
        painter.save(); painter.translate(rect.left()+4,rect.top()+2); doc.drawContents(painter,QRectF(0,0,rect.width()-8,rect.height()-4)); painter.restore()
        if bool(m.get(f"{section}_separator_enabled",True)):
            painter.setPen(QPen(QColor(str(m.get(f"{section}_separator_color","#c8cdd3"))),1)); sy=rect.bottom() if section=="header" else rect.top(); painter.drawLine(int(rect.left()),int(sy),int(rect.right()),int(sy))

    def mousePressEvent(self, event):
        page, _w, _h = self._page_rect()
        if event.button()==Qt.LeftButton and page.contains(event.pos()) and str(self.meta_getter().get("pdf_cover_background_type",""))=="image":
            self._dragging_bg=True
            self._update_drag(event.pos(), page)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_bg:
            page, _w, _h = self._page_rect(); self._update_drag(event.pos(), page)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._dragging_bg=False
        super().mouseReleaseEvent(event)

    def _update_drag(self, pos, page):
        x=max(0.0,min(100.0,(pos.x()-page.left())/max(1.0,page.width())*100.0))
        y=max(0.0,min(100.0,(pos.y()-page.top())/max(1.0,page.height())*100.0))
        self.backgroundPositionChanged.emit(x,y)


class PdfSettingsDialog(QDialog):
    """Configuração específica do PDF com prévia realista da capa."""
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Configuração do PDF")
        self.resize(1120, 760)
        self._cover_bg_path = None
        self._cover_logo_path = None
        self._cover_logo_use_main = False
        root = QVBoxLayout(self)

        intro = QLabel("O PDF é composto por seções independentes. A capa possui configuração própria e a prévia ao lado usa as mesmas dimensões e opções salvas no projeto.")
        intro.setWordWrap(True); root.addWidget(intro)
        tabs=QTabWidget(); root.addWidget(tabs,1)

        # Estrutura
        structure=QWidget(); sl=QVBoxLayout(structure)
        g=QGroupBox("Composição por tópicos"); gf=QFormLayout(g)
        self.topic_title=QCheckBox("Mostrar título grande quando a página não tiver cabeçalho"); self.topic_title.setChecked(bool(project.meta.get("pdf_topic_title_enabled",True)))
        self.topic_numbering=QCheckBox("Numerar tópicos (1, 1.1, 1.2...)"); self.topic_numbering.setChecked(bool(project.meta.get("pdf_topic_numbering",True)))
        self.title_size=QDoubleSpinBox(); self.title_size.setRange(10,42); self.title_size.setDecimals(1); self.title_size.setSuffix(" pt"); self.title_size.setValue(float(project.meta.get("pdf_topic_title_size_pt",project.meta.get("heading1_size_pt",20))))
        self.reclaim=QCheckBox("Recuperar o espaço quando cabeçalho/rodapé estiver oculto nesta página"); self.reclaim.setChecked(bool(project.meta.get("pdf_reclaim_hidden_header_footer_space",True)))
        gf.addRow(self.topic_title); gf.addRow(self.topic_numbering); gf.addRow("Tamanho do título:",self.title_size); gf.addRow(self.reclaim)
        sl.addWidget(g); sl.addStretch(1); tabs.addTab(structure,"Estrutura")

        # Capa com painel de controles + preview
        cover_tab=QWidget(); cover_root=QHBoxLayout(cover_tab)
        controls=QWidget(); cv=QVBoxLayout(controls); cv.setContentsMargins(0,0,8,0)
        general=QGroupBox("Conteúdo da capa"); cf=QFormLayout(general)
        self.cover_enabled=QCheckBox("Gerar capa no PDF"); self.cover_enabled.setChecked(bool(project.meta.get("pdf_cover_enabled",project.meta.get("cover_enabled",True))))
        self.header_cover=QCheckBox("Exibir cabeçalho na capa"); self.header_cover.setChecked(bool(project.meta.get("pdf_header_on_cover",False)))
        self.footer_cover=QCheckBox("Exibir rodapé na capa"); self.footer_cover.setChecked(bool(project.meta.get("pdf_footer_on_cover",False)))
        self.cover_title=QLineEdit(str(project.meta.get("pdf_cover_title",""))); self.cover_title.setPlaceholderText("Vazio = título do manual")
        self.cover_subtitle=QLineEdit(str(project.meta.get("pdf_cover_subtitle","")))
        self.cover_title_color=_HtmlColorButton(str(project.meta.get("pdf_cover_title_color","#1f2933")))
        self.cover_title_size=QDoubleSpinBox(); self.cover_title_size.setRange(16,60); self.cover_title_size.setDecimals(1); self.cover_title_size.setSuffix(" pt"); self.cover_title_size.setValue(float(project.meta.get("pdf_cover_title_size_pt",30)))
        self.cover_logo_width=QDoubleSpinBox(); self.cover_logo_width.setRange(8,120); self.cover_logo_width.setDecimals(1); self.cover_logo_width.setSuffix(" mm"); self.cover_logo_width.setValue(float(project.meta.get("pdf_cover_logo_width_mm",42)))
        self.cover_align=QComboBox(); self.cover_align.addItem("Esquerda","left"); self.cover_align.addItem("Centro","center"); self.cover_align.addItem("Direita","right"); self.cover_align.setCurrentIndex(max(0,self.cover_align.findData(project.meta.get("pdf_cover_alignment","center"))))
        self.cover_offset=QDoubleSpinBox(); self.cover_offset.setRange(0,180); self.cover_offset.setDecimals(1); self.cover_offset.setSuffix(" mm"); self.cover_offset.setValue(float(project.meta.get("pdf_cover_vertical_offset_mm",42)))
        self.cover_show_logo=QCheckBox("Mostrar logo"); self.cover_show_logo.setChecked(bool(project.meta.get("pdf_cover_show_logo",True)))
        self.cover_show_title=QCheckBox("Mostrar título"); self.cover_show_title.setChecked(bool(project.meta.get("pdf_cover_show_title",True)))
        self.cover_show_author=QCheckBox("Mostrar autor"); self.cover_show_author.setChecked(bool(project.meta.get("pdf_cover_show_author",True)))
        self.cover_show_version=QCheckBox("Mostrar versão"); self.cover_show_version.setChecked(bool(project.meta.get("pdf_cover_show_version",True)))
        self.cover_show_language=QCheckBox("Mostrar idioma quando houver vários"); self.cover_show_language.setChecked(bool(project.meta.get("pdf_cover_show_language",True)))
        logo_row=QWidget(); lh=QHBoxLayout(logo_row); lh.setContentsMargins(0,0,0,0)
        lb=QPushButton("Logo específico..."); lb.clicked.connect(self._choose_cover_logo); lmain=QPushButton("Usar logo principal"); lmain.clicked.connect(self._use_main_cover_logo); lh.addWidget(lb); lh.addWidget(lmain)
        cf.addRow(self.cover_enabled); cf.addRow(self.header_cover); cf.addRow(self.footer_cover); cf.addRow("Título:",self.cover_title); cf.addRow("Subtítulo:",self.cover_subtitle); cf.addRow("Cor do título:",self.cover_title_color); cf.addRow("Tamanho do título:",self.cover_title_size); cf.addRow("Logo:",logo_row); cf.addRow("Largura do logo:",self.cover_logo_width); cf.addRow("Alinhamento:",self.cover_align); cf.addRow("Posição vertical:",self.cover_offset); cf.addRow(self.cover_show_logo); cf.addRow(self.cover_show_title); cf.addRow(self.cover_show_author); cf.addRow(self.cover_show_version); cf.addRow(self.cover_show_language)
        cv.addWidget(general)

        bg=QGroupBox("Fundo da capa / ajuste da imagem"); bf=QFormLayout(bg)
        self.cover_bg_type=QComboBox(); self.cover_bg_type.addItem("Sem fundo","none"); self.cover_bg_type.addItem("Cor sólida","solid"); self.cover_bg_type.addItem("Gradiente","gradient"); self.cover_bg_type.addItem("Imagem","image"); self.cover_bg_type.setCurrentIndex(max(0,self.cover_bg_type.findData(project.meta.get("pdf_cover_background_type","none"))))
        self.cover_bg=_HtmlColorButton(str(project.meta.get("pdf_cover_background_color1",project.meta.get("pdf_cover_background_color","#ffffff"))))
        self.cover_bg2=_HtmlColorButton(str(project.meta.get("pdf_cover_background_color2","#e9edf2")))
        self.cover_gradient=QComboBox(); self.cover_gradient.addItem("Vertical","vertical"); self.cover_gradient.addItem("Horizontal","horizontal"); self.cover_gradient.addItem("Diagonal","diagonal"); self.cover_gradient.setCurrentIndex(max(0,self.cover_gradient.findData(project.meta.get("pdf_cover_gradient_direction","vertical"))))
        self.cover_fit=QComboBox(); self.cover_fit.addItem("Cobrir folha","cover"); self.cover_fit.addItem("Conter inteira","contain"); self.cover_fit.addItem("Esticar","stretch"); self.cover_fit.setCurrentIndex(max(0,self.cover_fit.findData(project.meta.get("pdf_cover_background_fit","cover"))))
        self.cover_scale=QSpinBox(); self.cover_scale.setRange(10,400); self.cover_scale.setSuffix(" %"); self.cover_scale.setValue(int(project.meta.get("pdf_cover_background_scale_percent",100)))
        self.cover_x=QSpinBox(); self.cover_x.setRange(0,100); self.cover_x.setSuffix(" %"); self.cover_x.setValue(int(project.meta.get("pdf_cover_background_x_percent",50)))
        self.cover_y=QSpinBox(); self.cover_y.setRange(0,100); self.cover_y.setSuffix(" %"); self.cover_y.setValue(int(project.meta.get("pdf_cover_background_y_percent",50)))
        self.cover_opacity=QSpinBox(); self.cover_opacity.setRange(0,100); self.cover_opacity.setSuffix(" %"); self.cover_opacity.setValue(int(project.meta.get("pdf_cover_background_opacity",100)))
        bgrow=QWidget(); bgh=QHBoxLayout(bgrow); bgh.setContentsMargins(0,0,0,0); bgbtn=QPushButton("Escolher imagem..."); bgbtn.clicked.connect(self._choose_cover_background); bgclear=QPushButton("Limpar"); bgclear.clicked.connect(self._clear_cover_background); bgh.addWidget(bgbtn); bgh.addWidget(bgclear)
        bf.addRow("Tipo:",self.cover_bg_type); bf.addRow("Cor 1:",self.cover_bg); bf.addRow("Cor 2:",self.cover_bg2); bf.addRow("Gradiente:",self.cover_gradient); bf.addRow("Imagem:",bgrow); bf.addRow("Encaixe:",self.cover_fit); bf.addRow("Escala:",self.cover_scale); bf.addRow("Posição X:",self.cover_x); bf.addRow("Posição Y:",self.cover_y); bf.addRow("Opacidade:",self.cover_opacity)
        cv.addWidget(bg); cv.addStretch(1)
        cover_root.addWidget(controls,1)
        preview_box=QWidget(); pv=QVBoxLayout(preview_box); pv.setContentsMargins(8,0,0,0); pv.addWidget(QLabel("Prévia da capa")); self.cover_preview=PdfCoverPreview(project,self._cover_preview_meta,self); self.cover_preview.backgroundPositionChanged.connect(self._cover_dragged); pv.addWidget(self.cover_preview,1); cover_root.addWidget(preview_box,1)
        tabs.addTab(cover_tab,"Capa")

        # Sumário
        toc=QWidget(); tl=QVBoxLayout(toc); tg=QGroupBox("Sumário do PDF"); tf=QFormLayout(tg)
        self.toc_enabled=QCheckBox("Gerar sumário automático"); self.toc_enabled.setChecked(bool(project.meta.get("pdf_toc_enabled",project.meta.get("toc_enabled",True))))
        self.toc_pages=QCheckBox("Mostrar o número da página de cada tópico"); self.toc_pages.setChecked(bool(project.meta.get("pdf_toc_page_numbers",True)))
        self.toc_title=QLineEdit(str(project.meta.get("pdf_toc_title","Sumário")))
        self.toc_font=QDoubleSpinBox(); self.toc_font.setRange(7,24); self.toc_font.setDecimals(1); self.toc_font.setSuffix(" pt"); self.toc_font.setValue(float(project.meta.get("pdf_toc_font_size_pt",project.meta.get("body_font_size_pt",10.5))))
        self.toc_intro=QTextEdit(); self.toc_intro.setAcceptRichText(True); self.toc_intro.setHtml(str(project.meta.get("pdf_toc_intro_html",""))); self.toc_intro.setMinimumHeight(120)
        self.header_toc=QCheckBox("Exibir cabeçalho no sumário"); self.header_toc.setChecked(bool(project.meta.get("pdf_header_on_toc",False)))
        self.footer_toc=QCheckBox("Exibir rodapé no sumário"); self.footer_toc.setChecked(bool(project.meta.get("pdf_footer_on_toc",False)))
        tf.addRow(self.toc_enabled); tf.addRow(self.toc_pages); tf.addRow("Título:",self.toc_title); tf.addRow("Texto introdutório:",self.toc_intro); tf.addRow("Fonte das entradas:",self.toc_font); tf.addRow(self.header_toc); tf.addRow(self.footer_toc)
        tl.addWidget(tg); note=QLabel("O sumário é medido em múltiplas passagens e recebe os números reais das páginas antes da gravação final."); note.setWordWrap(True); note.setStyleSheet("color:#666"); tl.addWidget(note); tl.addStretch(1); tabs.addTab(toc,"Sumário")

        # Saída
        output=QWidget(); ol=QVBoxLayout(output); og=QGroupBox("Qualidade e numeração"); of=QFormLayout(og)
        self.dpi=QComboBox(); [self.dpi.addItem(f"{v} dpi",v) for v in (150,300,600)]; self.dpi.setCurrentIndex(max(0,self.dpi.findData(int(project.meta.get("pdf_resolution_dpi",300)))))
        self.page_start=QSpinBox(); self.page_start.setRange(1,9999); self.page_start.setValue(int(project.meta.get("pdf_page_number_start",1)))
        of.addRow("Resolução do dispositivo PDF:",self.dpi); of.addRow("Primeiro número de página:",self.page_start); ol.addWidget(og); ol.addStretch(1); tabs.addTab(output,"Saída")

        self._wire_cover_preview()
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _cover_preview_meta(self):
        m=dict(self.project.meta)
        m.update({
            "pdf_cover_enabled":self.cover_enabled.isChecked(), "pdf_header_on_cover":self.header_cover.isChecked(), "pdf_footer_on_cover":self.footer_cover.isChecked(),
            "pdf_cover_title":self.cover_title.text().strip(), "pdf_cover_subtitle":self.cover_subtitle.text().strip(), "pdf_cover_title_color":self.cover_title_color.value(),
            "pdf_cover_title_size_pt":self.cover_title_size.value(), "pdf_cover_logo_width_mm":self.cover_logo_width.value(), "pdf_cover_alignment":self.cover_align.currentData(), "pdf_cover_vertical_offset_mm":self.cover_offset.value(),
            "pdf_cover_show_logo":self.cover_show_logo.isChecked(), "pdf_cover_show_title":self.cover_show_title.isChecked(), "pdf_cover_show_author":self.cover_show_author.isChecked(), "pdf_cover_show_version":self.cover_show_version.isChecked(), "pdf_cover_show_language":self.cover_show_language.isChecked(),
            "pdf_cover_background_type":self.cover_bg_type.currentData(), "pdf_cover_background_color1":self.cover_bg.value(), "pdf_cover_background_color2":self.cover_bg2.value(), "pdf_cover_gradient_direction":self.cover_gradient.currentData(),
            "pdf_cover_background_fit":self.cover_fit.currentData(), "pdf_cover_background_scale_percent":self.cover_scale.value(), "pdf_cover_background_x_percent":self.cover_x.value(), "pdf_cover_background_y_percent":self.cover_y.value(), "pdf_cover_background_opacity":self.cover_opacity.value(),
        })
        if self._cover_bg_path and self.cover_bg_type.currentData()=="image": m["_preview_cover_background_path"]=self._cover_bg_path
        if self._cover_logo_use_main:
            m["pdf_cover_logo_asset"]=""
        elif self._cover_logo_path:
            m["_preview_cover_logo_path"]=self._cover_logo_path
        return m

    def _wire_cover_preview(self):
        for w in (self.cover_enabled,self.header_cover,self.footer_cover,self.cover_show_logo,self.cover_show_title,self.cover_show_author,self.cover_show_version,self.cover_show_language): w.toggled.connect(self.cover_preview.update)
        for w in (self.cover_title,self.cover_subtitle): w.textChanged.connect(self.cover_preview.update)
        for w in (self.cover_title_size,self.cover_logo_width,self.cover_offset,self.cover_scale,self.cover_x,self.cover_y,self.cover_opacity): w.valueChanged.connect(self.cover_preview.update)
        for w in (self.cover_align,self.cover_bg_type,self.cover_gradient,self.cover_fit): w.currentIndexChanged.connect(self.cover_preview.update)
        self.cover_bg.colorChanged.connect(self.cover_preview.update); self.cover_bg2.colorChanged.connect(self.cover_preview.update); self.cover_title_color.colorChanged.connect(self.cover_preview.update)

    def _cover_dragged(self,x,y):
        self.cover_x.blockSignals(True); self.cover_y.blockSignals(True); self.cover_x.setValue(round(x)); self.cover_y.setValue(round(y)); self.cover_x.blockSignals(False); self.cover_y.blockSignals(False); self.cover_preview.update()

    def _choose_cover_background(self):
        path,_=QFileDialog.getOpenFileName(self,"Imagem de fundo da capa","","Imagens (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path: self._cover_bg_path=path; self.cover_bg_type.setCurrentIndex(max(0,self.cover_bg_type.findData("image"))); self.cover_preview.update()

    def _clear_cover_background(self):
        self._cover_bg_path=""; self.cover_bg_type.setCurrentIndex(max(0,self.cover_bg_type.findData("solid"))); self.cover_preview.update()

    def _choose_cover_logo(self):
        path,_=QFileDialog.getOpenFileName(self,"Logo específico da capa","","Imagens (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self._cover_logo_path=path
            self._cover_logo_use_main=False
            self.cover_show_logo.setChecked(True)
            self.cover_preview.update()

    def _use_main_cover_logo(self):
        self._cover_logo_path=""
        self._cover_logo_use_main=True
        self.cover_show_logo.setChecked(True)
        self.cover_preview.update()

    def apply(self):
        m=self.project.meta
        m["pdf_topic_title_enabled"]=self.topic_title.isChecked(); m["pdf_topic_numbering"]=self.topic_numbering.isChecked(); m["pdf_topic_title_size_pt"]=self.title_size.value(); m["pdf_reclaim_hidden_header_footer_space"]=self.reclaim.isChecked()
        m["pdf_cover_enabled"]=self.cover_enabled.isChecked(); m["pdf_header_on_cover"]=self.header_cover.isChecked(); m["pdf_footer_on_cover"]=self.footer_cover.isChecked(); m["pdf_cover_title"]=self.cover_title.text().strip(); m["pdf_cover_subtitle"]=self.cover_subtitle.text().strip(); m["pdf_cover_title_color"]=self.cover_title_color.value(); m["pdf_cover_title_size_pt"]=self.cover_title_size.value(); m["pdf_cover_logo_width_mm"]=self.cover_logo_width.value(); m["pdf_cover_show_version"]=self.cover_show_version.isChecked(); m["pdf_cover_show_author"]=self.cover_show_author.isChecked(); m["pdf_cover_show_logo"]=self.cover_show_logo.isChecked(); m["pdf_cover_show_title"]=self.cover_show_title.isChecked(); m["pdf_cover_show_language"]=self.cover_show_language.isChecked(); m["pdf_cover_alignment"]=self.cover_align.currentData(); m["pdf_cover_vertical_offset_mm"]=self.cover_offset.value()
        m["pdf_cover_background_type"]=self.cover_bg_type.currentData(); m["pdf_cover_background_color"]=self.cover_bg.value(); m["pdf_cover_background_color1"]=self.cover_bg.value(); m["pdf_cover_background_color2"]=self.cover_bg2.value(); m["pdf_cover_gradient_direction"]=self.cover_gradient.currentData(); m["pdf_cover_background_fit"]=self.cover_fit.currentData(); m["pdf_cover_background_scale_percent"]=self.cover_scale.value(); m["pdf_cover_background_x_percent"]=self.cover_x.value(); m["pdf_cover_background_y_percent"]=self.cover_y.value(); m["pdf_cover_background_opacity"]=self.cover_opacity.value()
        if self.cover_bg_type.currentData()!="image":
            m["pdf_cover_background_asset"]=""
        elif self._cover_bg_path:
            asset=self.project.add_asset_from_file(self._cover_bg_path)
            m["pdf_cover_background_asset"]=asset.id
            m["pdf_cover_background_type"]="image"
        if self._cover_logo_use_main:
            m["pdf_cover_logo_asset"]=""
        elif self._cover_logo_path:
            asset=self.project.add_asset_from_file(self._cover_logo_path)
            m["pdf_cover_logo_asset"]=asset.id
        m["pdf_toc_enabled"]=self.toc_enabled.isChecked(); m["pdf_toc_page_numbers"]=self.toc_pages.isChecked(); m["pdf_toc_title"]=self.toc_title.text().strip() or "Sumário"; m["pdf_toc_intro_html"]=self.toc_intro.toHtml(); m["pdf_toc_font_size_pt"]=self.toc_font.value(); m["pdf_header_on_toc"]=self.header_toc.isChecked(); m["pdf_footer_on_toc"]=self.footer_toc.isChecked(); m["pdf_resolution_dpi"]=int(self.dpi.currentData() or 300); m["pdf_page_number_start"]=self.page_start.value()


class PdfLanguageExportDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Idioma do PDF")
        root = QVBoxLayout(self)
        self.mode = QComboBox()
        self.mode.addItem("Um idioma", "single")
        self.mode.addItem("Todos os idiomas em um único PDF", "combined")
        self.mode.addItem("Um PDF separado para cada idioma", "separate")
        root.addWidget(QLabel("Como deseja exportar?")); root.addWidget(self.mode)
        self.language = QComboBox()
        for lang in project.languages():
            self.language.addItem(f"{LANG_NAMES.get(lang, lang)} — {lang}", lang)
        root.addWidget(QLabel("Idioma para exportação única:")); root.addWidget(self.language)
        self.mode.currentIndexChanged.connect(lambda: self.language.setEnabled(self.mode.currentData() == "single"))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def values(self):
        return str(self.mode.currentData()), str(self.language.currentData() or "")


class _HtmlColorButton(QPushButton):
    colorChanged = pyqtSignal(str)
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self._color = QColor(color if QColor(color).isValid() else "#ffffff")
        self.clicked.connect(self.choose)
        self.sync()
    def value(self): return self._color.name()
    def setValue(self, value):
        c = QColor(value)
        if c.isValid():
            self._color = c; self.sync(); self.colorChanged.emit(self._color.name())
    def sync(self):
        fg = "#000" if self._color.lightness() > 145 else "#fff"
        self.setText(self._color.name().upper())
        self.setStyleSheet(f"QPushButton{{background:{self._color.name()};color:{fg};border:1px solid #777;padding:6px 12px;}}")
    def choose(self):
        c = QColorDialog.getColor(self._color, self, "Selecionar cor")
        if c.isValid():
            self._color = c; self.sync(); self.colorChanged.emit(c.name())


class HtmlStyleDialog(QDialog):
    """Configuração do WebHelp com pré-compilação navegável inteiramente em RAM."""
    PROJECT_URL = "https://github.com/Valdemir-DSW/manual_studio_qt5"

    def __init__(self, project, parent=None, meta=None, current_topic_id=None, current_language=None):
        super().__init__(parent)
        self.project = project
        self.meta = meta if meta is not None else project.meta
        self.current_topic_id = current_topic_id
        self.current_language = current_language or str(project.meta.get("language", "pt-BR"))
        self._icon_path = None
        self.setWindowTitle("HTML / WebHelp")
        self.resize(1320, 820)
        root = QVBoxLayout(self)
        split = QHBoxLayout(); root.addLayout(split, 1)

        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0,0,6,0)
        tabs = QTabWidget(); ll.addWidget(tabs,1); split.addWidget(left,1)

        visual=QWidget(); vf=QFormLayout(visual)
        self.accent=_HtmlColorButton(str(self.meta.get("html_accent","#1769aa")))
        self.bg=_HtmlColorButton(str(self.meta.get("html_background","#ffffff")))
        self.fg=_HtmlColorButton(str(self.meta.get("html_text","#1f2933")))
        self.side=_HtmlColorButton(str(self.meta.get("html_sidebar_background","#f5f7fa")))
        self.topbar=_HtmlColorButton(str(self.meta.get("html_topbar_background","#ffffff")))
        self.sidebar=QSpinBox(); self.sidebar.setRange(180,520); self.sidebar.setSuffix(" px"); self.sidebar.setValue(int(self.meta.get("html_sidebar_width_px",300)))
        self.content=QSpinBox(); self.content.setRange(520,1600); self.content.setSuffix(" px"); self.content.setValue(int(self.meta.get("html_content_width_px",900)))
        self.tree_lines=QCheckBox("Mostrar linhas-guia na árvore"); self.tree_lines.setChecked(bool(self.meta.get("html_tree_lines",True)))
        self.tree_open=QCheckBox("Abrir ramos da árvore por padrão"); self.tree_open.setChecked(bool(self.meta.get("html_tree_expand_default",True)))
        vf.addRow("Cor de destaque:",self.accent); vf.addRow("Fundo:",self.bg); vf.addRow("Texto:",self.fg); vf.addRow("Fundo da árvore:",self.side); vf.addRow("Fundo da barra superior:",self.topbar); vf.addRow("Largura da árvore:",self.sidebar); vf.addRow("Largura máxima do conteúdo:",self.content); vf.addRow(self.tree_lines); vf.addRow(self.tree_open)
        self.preset=QComboBox(); self.preset.addItems(["Técnico claro","Cinza neutro","Escuro"]); preset_btn=QPushButton("Aplicar preset"); preset_btn.clicked.connect(self._preset); prow=QWidget(); ph=QHBoxLayout(prow); ph.setContentsMargins(0,0,0,0); ph.addWidget(self.preset); ph.addWidget(preset_btn); vf.addRow("Preset:",prow)
        iconrow=QWidget(); ih=QHBoxLayout(iconrow); ih.setContentsMargins(0,0,0,0); ib=QPushButton("Escolher ícone..."); ib.clicked.connect(self._choose_icon); ic=QPushButton("Usar logo"); ic.clicked.connect(self._use_logo_icon); ih.addWidget(ib); ih.addWidget(ic); vf.addRow("Ícone do manual:",iconrow)
        repo=QLabel(f'<a href="{self.PROJECT_URL}">{self.PROJECT_URL}</a>'); repo.setOpenExternalLinks(True); repo.setTextInteractionFlags(Qt.TextBrowserInteraction); vf.addRow("Projeto:",repo)
        self.project_url=QLineEdit(str(self.meta.get("html_project_url",self.PROJECT_URL) or self.PROJECT_URL)); self.project_url.setPlaceholderText(self.PROJECT_URL)
        self.show_project_link=QCheckBox("Mostrar link do projeto/suporte na página inicial"); self.show_project_link.setChecked(bool(self.meta.get("html_show_project_link",True)))
        vf.addRow("Link do projeto/suporte:",self.project_url); vf.addRow(self.show_project_link)
        tabs.addTab(visual,"Visual")

        structure=QWidget(); sf=QFormLayout(structure)
        self.toc_enabled=QCheckBox("Gerar página de sumário automaticamente"); self.toc_enabled.setChecked(bool(self.meta.get("html_toc_enabled",True)))
        self.toc_title=QLineEdit(str(self.meta.get("html_toc_title","Sumário"))); self.toc_desc=QLineEdit(str(self.meta.get("html_toc_description","Navegue pelos tópicos deste manual.")))
        sf.addRow(self.toc_enabled); sf.addRow("Título do sumário:",self.toc_title); sf.addRow("Descrição:",self.toc_desc); note=QLabel("O sumário HTML é criado pelo exportador e é independente do sumário do PDF."); note.setWordWrap(True); sf.addRow(note); tabs.addTab(structure,"Sumário")

        intro=QWidget(); inf=QFormLayout(intro)
        self.intro_enabled=QCheckBox("Gerar página inicial / introdução"); self.intro_enabled.setChecked(bool(self.meta.get("html_intro_enabled",True)))
        self.intro_title=QLineEdit(str(self.meta.get("html_intro_title",""))); self.intro_title.setPlaceholderText("Vazio = título do manual")
        self.intro_subtitle=QLineEdit(str(self.meta.get("html_intro_subtitle","Manual do usuário")))
        self.intro_show_logo=QCheckBox("Mostrar logo"); self.intro_show_logo.setChecked(bool(self.meta.get("html_intro_show_logo",True)))
        self.intro_show_version=QCheckBox("Mostrar versão"); self.intro_show_version.setChecked(bool(self.meta.get("html_intro_show_version",True)))
        self.intro_show_author=QCheckBox("Mostrar autor"); self.intro_show_author.setChecked(bool(self.meta.get("html_intro_show_author",True)))
        self.intro_show_toc=QCheckBox("Mostrar botão para o sumário"); self.intro_show_toc.setChecked(bool(self.meta.get("html_intro_show_toc",True)))
        self.intro_body=QTextEdit(); self.intro_body.setAcceptRichText(True); self.intro_body.setHtml(str(self.meta.get("html_intro_body_html","<p>Selecione um tópico para começar.</p>"))); self.intro_body.setMinimumHeight(160)
        inf.addRow(self.intro_enabled); inf.addRow("Título:",self.intro_title); inf.addRow("Subtítulo:",self.intro_subtitle); inf.addRow(self.intro_show_logo); inf.addRow(self.intro_show_version); inf.addRow(self.intro_show_author); inf.addRow(self.intro_show_toc); inf.addRow("Conteúdo:",self.intro_body); tabs.addTab(intro,"Introdução")

        cssw=QWidget(); cl=QVBoxLayout(cssw); cl.addWidget(QLabel("CSS adicional — aplicado por último e com prioridade sobre o estilo base:")); self.css=QTextEdit(); self.css.setAcceptRichText(False); self.css.setPlainText(str(self.meta.get("html_custom_css",""))); self.css.setPlaceholderText(".content { max-width: 980px; }\n.sidebar a { font-weight: 500; }\npre { border-radius: 8px; }"); cl.addWidget(self.css,1); tabs.addTab(cssw,"CSS")

        right=QWidget(); rl=QVBoxLayout(right); rl.setContentsMargins(6,0,0,0)
        preview_head=QHBoxLayout(); self.preview_status=QLabel(); preview_head.addWidget(self.preview_status,1); refresh=QPushButton("Atualizar agora"); refresh.clicked.connect(self._refresh_preview); preview_head.addWidget(refresh); rl.addLayout(preview_head)
        if QWebEngineView is not None:
            self.preview=QWebEngineView()
            self.preview_profile=QWebEngineProfile(self.preview)
            self.preview_profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
            self.preview_profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
            self.preview_profile.setHttpCacheMaximumSize(32*1024*1024)
            self.preview_page=QWebEnginePage(self.preview_profile,self.preview)
            self.preview.setPage(self.preview_page)
            self.preview_handler = _MemoryPreviewSchemeHandler(self.preview) if _MemoryPreviewSchemeHandler is not None else None
            if self.preview_handler is not None:
                try:
                    self.preview_profile.installUrlSchemeHandler(b"manualpreview", self.preview_handler)
                except Exception:
                    self.preview_handler = None
            self._preview_revision = 0
            self.preview_status.setText("Prévia real • Qt WebEngine • compilação e cache em RAM")
        else:
            self.preview=QTextBrowser(); self.preview.setOpenExternalLinks(False)
            self.preview_status.setText("Prévia compatível • instale PyQtWebEngine para usar o navegador Qt completo")
        self.preview.setMinimumWidth(590); rl.addWidget(self.preview,1); split.addWidget(right,1)

        self.preview_timer=QTimer(self); self.preview_timer.setSingleShot(True); self.preview_timer.setInterval(220); self.preview_timer.timeout.connect(self._refresh_preview)
        for w in (self.accent,self.bg,self.fg,self.side,self.topbar): w.colorChanged.connect(self._schedule_preview)
        for w in (self.sidebar,self.content): w.valueChanged.connect(self._schedule_preview)
        for w in (self.tree_lines,self.tree_open,self.toc_enabled,self.intro_enabled,self.intro_show_logo,self.intro_show_version,self.intro_show_author,self.intro_show_toc,self.show_project_link): w.toggled.connect(self._schedule_preview)
        for w in (self.toc_title,self.toc_desc,self.intro_title,self.intro_subtitle,self.project_url): w.textChanged.connect(self._schedule_preview)
        self.intro_body.textChanged.connect(self._schedule_preview); self.css.textChanged.connect(self._schedule_preview)
        self._refresh_preview()

        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _choose_icon(self):
        path,_=QFileDialog.getOpenFileName(self,"Ícone do manual","","Imagens (*.png *.jpg *.jpeg *.ico *.webp)")
        if path: self._icon_path=path; self._schedule_preview()

    def _use_logo_icon(self):
        self._icon_path="__logo__"; self._schedule_preview()

    def _preset(self):
        name=self.preset.currentText(); vals=("#3b82f6","#111418","#edf2f7","#191d22","#111418") if name=="Escuro" else (("#4b6478","#ffffff","#252a30","#eceff2","#ffffff") if name=="Cinza neutro" else ("#1769aa","#ffffff","#1f2933","#f5f7fa","#ffffff"))
        for btn,val in zip((self.accent,self.bg,self.fg,self.side,self.topbar),vals): btn.setValue(val)

    def _preview_meta(self):
        m=dict(self.meta)
        m.update({
            "html_accent":self.accent.value(), "html_background":self.bg.value(), "html_text":self.fg.value(), "html_sidebar_background":self.side.value(), "html_topbar_background":self.topbar.value(),
            "html_sidebar_width_px":self.sidebar.value(), "html_content_width_px":self.content.value(), "html_tree_lines":self.tree_lines.isChecked(), "html_tree_expand_default":self.tree_open.isChecked(),
            "html_toc_enabled":self.toc_enabled.isChecked(), "html_toc_title":self.toc_title.text().strip() or "Sumário", "html_toc_description":self.toc_desc.text().strip(),
            "html_intro_enabled":self.intro_enabled.isChecked(), "html_intro_title":self.intro_title.text().strip(), "html_intro_subtitle":self.intro_subtitle.text().strip(), "html_intro_show_logo":self.intro_show_logo.isChecked(), "html_intro_show_version":self.intro_show_version.isChecked(), "html_intro_show_author":self.intro_show_author.isChecked(), "html_intro_show_toc":self.intro_show_toc.isChecked(), "html_intro_body_html":self.intro_body.toHtml(),
            "html_custom_css":self.css.toPlainText(), "html_project_url":self.project_url.text().strip() or self.PROJECT_URL, "html_show_project_link":self.show_project_link.isChecked(),
        })
        return m

    def _schedule_preview(self,*_args):
        self.preview_timer.start()

    def _refresh_preview(self):
        try:
            from .exporters import build_html_preview_document
            doc=build_html_preview_document(self.project,self._preview_meta(),self.current_topic_id,self.current_language)
            if QWebEngineView is not None and isinstance(self.preview,QWebEngineView):
                if getattr(self, "preview_handler", None) is not None:
                    self.preview_handler.set_html(doc)
                    self._preview_revision = int(getattr(self, "_preview_revision", 0)) + 1
                    self.preview.setUrl(QUrl(f"manualpreview://preview/index.html?r={self._preview_revision}"))
                else:
                    self.preview.setHtml(doc,QUrl("about:blank"))
            else:
                self.preview.setHtml(doc)
            self.preview_status.setToolTip("A prévia é compilada em memória a partir do projeto aberto; não cria pasta temporária.")
        except Exception as exc:
            fallback=f"<h3>Falha na prévia</h3><pre>{html.escape(str(exc))}</pre>"
            self.preview.setHtml(fallback)

    def apply(self):
        m=self.meta; pm=self._preview_meta(); m.update(pm)
        if self._icon_path=="__logo__":
            m["html_manual_icon_asset"]=str(m.get("logo_asset",""))
        elif self._icon_path:
            asset=self.project.add_asset_from_file(self._icon_path); m["html_manual_icon_asset"]=asset.id


class BandPreview(QWidget):
    """Prévia leve do cabeçalho/rodapé sem depender do exportador."""
    def __init__(self, project, section, meta_getter, parent=None):
        super().__init__(parent)
        self.project = project; self.section = section; self.meta_getter = meta_getter
        self.setMinimumHeight(90); self.setMaximumHeight(130)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing, True)
        m = self.meta_getter()
        rect = QRectF(6, 8, self.width()-12, self.height()-16)
        p.fillRect(self.rect(), QColor("#e7e9ec"))
        p.fillRect(rect, QColor("#ffffff"))
        if not bool(m.get(f"{self.section}_enabled", True)):
            p.setPen(QColor("#777")); p.drawText(rect, Qt.AlignCenter, "Desativado"); p.end(); return
        kind = str(m.get(f"{self.section}_background_type", "none"))
        opacity = max(0.0, min(1.0, float(m.get(f"{self.section}_background_opacity", 100))/100.0))
        p.save(); p.setOpacity(opacity)
        c1 = QColor(str(m.get(f"{self.section}_background_color1", "#ffffff")))
        c2 = QColor(str(m.get(f"{self.section}_background_color2", "#e9edf2")))
        if kind == "solid": p.fillRect(rect, c1)
        elif kind == "gradient":
            direction = str(m.get(f"{self.section}_gradient_direction", "horizontal"))
            if direction == "vertical": g = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
            elif direction == "diagonal": g = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
            else: g = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
            g.setColorAt(0,c1); g.setColorAt(1,c2); p.fillRect(rect, QBrush(g))
        elif kind == "image":
            preview_path = str(m.get(f"{self.section}_preview_background_path", "") or "")
            if preview_path:
                img = QImage(preview_path)
            else:
                aid = m.get(f"{self.section}_background_asset", "")
                asset = self.project.assets.get(aid)
                img = QImage.fromData(asset.bytes()) if asset else QImage()
            if not img.isNull(): p.drawImage(rect, img)
        p.restore()
        if bool(m.get(f"{self.section}_separator_enabled", True)):
            p.setPen(QPen(QColor(str(m.get(f"{self.section}_separator_color", "#c8cdd3"))), 1))
            y = rect.bottom() if self.section == "header" else rect.top(); p.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))

        template = str(m.get(f"{self.section}_template_html", "<p></p>"))
        values = {
            "title": str(m.get("title", "Manual")), "author": str(m.get("author", "")),
            "version": str(m.get("version", "1.0")), "page": "12", "pages": "84",
            "topic": "Sensor de fase", "category": "Sincronização", "date": "06/09/2026",
            "language": str(m.get("language", "pt-BR")), "footer_text": str(m.get("footer_text", "")),
        }
        for k,v in values.items(): template = template.replace("{{"+k+"}}", html.escape(v))
        logo_id = m.get("logo_asset", "")
        preview_logo_path = str(m.get("_preview_logo_path", "") or "")
        if preview_logo_path:
            doc_logo_url = QUrl.fromLocalFile(preview_logo_path).toString()
            template = template.replace("{{logo}}", f'<img src="{doc_logo_url}" width="45">')
        elif logo_id in self.project.assets:
            template = template.replace("{{logo}}", f'<img src="asset://{logo_id}" width="45">')
        else: template = template.replace("{{logo}}", "")
        doc = QTextDocument(); doc.setDocumentMargin(0)
        for aid, asset in self.project.assets.items():
            img = QImage.fromData(asset.bytes())
            if not img.isNull(): doc.addResource(QTextDocument.ImageResource, QUrl("asset://"+aid), img)
        doc.setHtml(template); doc.setTextWidth(max(1, rect.width()-20))
        p.save(); p.translate(rect.left()+10, rect.top()+10); doc.drawContents(p, QRectF(0,0,rect.width()-20,rect.height()-20)); p.restore(); p.end()
