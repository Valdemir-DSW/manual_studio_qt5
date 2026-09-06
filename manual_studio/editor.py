from pathlib import Path
import html
from PyQt5.QtCore import Qt, QUrl, QPoint, QSizeF
from PyQt5.QtGui import (
    QFont,
    QImage,
    QColor,
    QPainter,
    QPen,
    QKeySequence,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextImageFormat,
    QTextListFormat,
    QTextLength,
    QTextFormat,
    QTextTableFormat,
)
from PyQt5.QtWidgets import (
    QAction,
    QColorDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFontDialog,
    QFrame,
    QInputDialog,
    QMenu,
    QMessageBox,
    QTextEdit,
    QToolBar,
    QToolTip,
    QApplication,
)

from .dialogs import (
    PAGE_DIMENSIONS_MM,
    ImageInsertDialog,
    ImageTextLayoutDialog,
    TableInsertDialog,
    TablePropertiesDialog,
)


SCREEN_DPI = 96.0
LAYOUT_TABLE_PROPERTY = int(QTextFormat.UserProperty) + 91


def _alignment(value):
    """Retorna sempre uma Qt.AlignmentFlag real, evitando int vindo de QComboBox.currentData()."""
    try:
        raw = int(value)
    except (TypeError, ValueError):
        raw = int(Qt.AlignLeft)
    if raw & int(Qt.AlignRight):
        return Qt.AlignRight
    if raw & int(Qt.AlignHCenter):
        return Qt.AlignHCenter
    if raw & int(Qt.AlignJustify):
        return Qt.AlignJustify
    return Qt.AlignLeft


class _ImageResizeHandle(QFrame):
    """Alça visual simples para redimensionamento direto da imagem selecionada."""

    def __init__(self, editor):
        super().__init__(editor.viewport())
        self.editor = editor
        self.setFixedSize(14, 14)
        self.setCursor(Qt.SizeFDiagCursor)
        self.setStyleSheet(
            "QFrame { background:#ffffff; border:2px solid #1769aa; border-radius:2px; }"
        )
        self.hide()
        self._dragging = False
        self._start_global_x = 0
        self._start_width = 0.0
        self._start_height = 0.0

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            cursor = self.editor._selected_image_cursor()
            if cursor is not None:
                fmt = cursor.charFormat().toImageFormat()
                self._dragging = True
                self._start_global_x = event.globalX()
                self._start_width = float(fmt.width())
                self._start_height = float(fmt.height())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.editor._resize_selected_image_from_drag(
                self._start_width,
                self._start_height,
                event.globalX() - self._start_global_x,
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self.editor._refresh_image_handle()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class RichTextEditor(QTextEdit):
    def __init__(self, project_getter, parent=None):
        super().__init__(parent)
        self._project_getter = project_getter
        self.setAcceptRichText(True)
        self.setTabStopWidth(32)
        self.setLineWrapMode(QTextEdit.FixedPixelWidth)
        self.setMouseTracking(True)

        self._selected_image_pos = None
        self._image_move_state = None
        self._margin_guides = None
        self._image_handle = _ImageResizeHandle(self)
        self.verticalScrollBar().valueChanged.connect(self._refresh_image_handle)
        self.horizontalScrollBar().valueChanged.connect(self._refresh_image_handle)
        self.cursorPositionChanged.connect(self._refresh_image_handle)
        self.refresh_project_layout()

    def set_margin_guides(self, left_fraction=None, right_fraction=None, visible=False):
        if visible and left_fraction is not None and right_fraction is not None:
            self._margin_guides = (max(0.0, min(1.0, float(left_fraction))), max(0.0, min(1.0, float(right_fraction))))
        else:
            self._margin_guides = None
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._margin_guides:
            return
        left_fraction, right_fraction = self._margin_guides
        p = QPainter(self.viewport())
        pen = QPen(QColor("#5591c9"), 1, Qt.DotLine)
        p.setPen(pen)
        # A guia acompanha a largura física da página, não a largura total do painel.
        page_w = self.page_width_px()
        x0 = 4.0 - float(self.horizontalScrollBar().value())
        p.drawLine(int(x0 + page_w * left_fraction), 0, int(x0 + page_w * left_fraction), self.viewport().height())
        p.drawLine(int(x0 + page_w * right_fraction), 0, int(x0 + page_w * right_fraction), self.viewport().height())
        p.end()

    def _project(self):
        return self._project_getter()

    def usable_width_mm(self):
        project = self._project()
        meta = project.meta if project else {}
        page_name = str(meta.get("page_size", "A4"))
        w, h = PAGE_DIMENSIONS_MM.get(page_name, PAGE_DIMENSIONS_MM["A4"])
        if meta.get("page_orientation", "portrait") == "landscape":
            w, h = h, w
        return max(40.0, w - float(meta.get("margin_left_mm", 18)) - float(meta.get("margin_right_mm", 18)))

    def available_width_mm_for_cursor(self, cursor=None):
        """Largura disponível no ponto atual; dentro de tabela respeita a largura da coluna."""
        cursor = QTextCursor(cursor or self.textCursor())
        table = cursor.currentTable()
        if table is None:
            return self.usable_width_mm()

        total = self.usable_width_mm()
        table_fmt = table.format()
        table_width = table_fmt.width()
        if table_width.type() == QTextLength.PercentageLength and table_width.rawValue() > 0:
            total *= table_width.rawValue() / 100.0
        elif table_width.type() == QTextLength.FixedLength and table_width.rawValue() > 0:
            total = table_width.rawValue() / SCREEN_DPI * 25.4

        cell = table.cellAt(cursor)
        column = cell.column() if cell.isValid() else 0
        constraints = table_fmt.columnWidthConstraints()
        if constraints and column < len(constraints):
            length = constraints[column]
            if length.type() == QTextLength.PercentageLength:
                total *= max(0.01, length.rawValue() / 100.0)
            elif length.type() == QTextLength.FixedLength and length.rawValue() > 0:
                total = length.rawValue() / SCREEN_DPI * 25.4
            else:
                total /= max(1, table.columns())
        else:
            total /= max(1, table.columns())

        padding_px = max(0.0, float(table_fmt.cellPadding())) * 2.0
        return max(15.0, total - padding_px / SCREEN_DPI * 25.4)

    def refresh_project_layout(self):
        project = self._project()
        meta = project.meta if project else {}
        family = str(meta.get("body_font_family", "Arial"))
        body = float(meta.get("body_font_size_pt", 10.5))
        line_height = int(meta.get("line_height_percent", 118))
        paragraph = float(meta.get("paragraph_spacing_pt", 5))
        self.document().setDefaultStyleSheet(
            f"body {{ font-family:'{family}'; font-size:{body}pt; line-height:{line_height}%; }} "
            f"p {{ margin-top:0; margin-bottom:{paragraph}pt; }} "
            "img { max-width:100%; height:auto; }"
        )
        font = QFont(family)
        font.setPointSizeF(body)
        self.document().setDefaultFont(font)
        self.setCurrentFont(font)

        # O editor agora usa a largura FÍSICA completa da folha e aplica as
        # margens no frame raiz. Antes a largura de quebra já era a área útil
        # e a margem visual não participava do layout, por isso o texto podia
        # parecer ignorar a régua.
        page_name = str(meta.get("page_size", "A4"))
        page_w_mm, page_h_mm = PAGE_DIMENSIONS_MM.get(page_name, PAGE_DIMENSIONS_MM["A4"])
        if meta.get("page_orientation", "portrait") == "landscape":
            page_w_mm, page_h_mm = page_h_mm, page_w_mm
        mm_to_px = SCREEN_DPI / 25.4
        page_w_px = max(320.0, page_w_mm * mm_to_px)
        page_h_px = max(420.0, page_h_mm * mm_to_px)
        left_px = max(0.0, float(meta.get("margin_left_mm", 18.0)) * mm_to_px)
        right_px = max(0.0, float(meta.get("margin_right_mm", 18.0)) * mm_to_px)
        top_px = max(0.0, float(meta.get("margin_top_mm", 16.0)) * mm_to_px)
        bottom_px = max(0.0, float(meta.get("margin_bottom_mm", 16.0)) * mm_to_px)

        # Proteção final: nunca deixa menos de 40 mm de área útil.
        min_content_px = 40.0 * mm_to_px
        if page_w_px - left_px - right_px < min_content_px:
            excess = min_content_px - (page_w_px - left_px - right_px)
            right_px = max(0.0, right_px - excess)

        self.document().setDocumentMargin(0)
        root = self.document().rootFrame()
        frame_fmt = root.frameFormat()
        frame_fmt.setLeftMargin(left_px)
        frame_fmt.setRightMargin(right_px)
        frame_fmt.setTopMargin(top_px)
        frame_fmt.setBottomMargin(bottom_px)
        root.setFrameFormat(frame_fmt)

        self.document().setPageSize(QSizeF(page_w_px, page_h_px))
        self.document().setTextWidth(page_w_px)
        self.setLineWrapMode(QTextEdit.FixedPixelWidth)
        self.setLineWrapColumnOrWidth(int(page_w_px))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.viewport().setAutoFillBackground(True)
        self._refresh_image_handle()

    def page_width_px(self):
        project = self._project()
        meta = project.meta if project else {}
        page_name = str(meta.get("page_size", "A4"))
        w, h = PAGE_DIMENSIONS_MM.get(page_name, PAGE_DIMENSIONS_MM["A4"])
        if meta.get("page_orientation", "portrait") == "landscape":
            w, h = h, w
        return float(w) / 25.4 * SCREEN_DPI

    def register_project_assets(self):
        project = self._project()
        if not project:
            return
        for asset_id, asset in project.assets.items():
            image = QImage.fromData(asset.bytes())
            if not image.isNull():
                self.document().addResource(
                    QTextDocument.ImageResource,
                    QUrl("asset://" + asset_id),
                    image,
                )

    def set_topic_html(self, html: str):
        self._clear_image_selection()
        self.clear()
        self.refresh_project_layout()
        self.register_project_assets()
        self.setHtml(html or "<p></p>")
        # setHtml() recria parte do layout interno do QTextDocument; reaplicar
        # o layout aqui é essencial para que as margens físicas não sejam perdidas.
        self.refresh_project_layout()
        self.register_project_assets()
        self.enforce_margin_protection()

    def enforce_margin_protection(self):
        """Limita imagens/tabelas à área útil. É reaplicado ao carregar conteúdo antigo."""
        doc = self.document()
        seen_tables = set()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.charFormat().isImageFormat():
                    c = QTextCursor(doc)
                    c.setPosition(frag.position())
                    c.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
                    fmt = frag.charFormat().toImageFormat()
                    available = self.available_width_mm_for_cursor(c) / 25.4 * SCREEN_DPI
                    bfmt = c.blockFormat()
                    left = max(0.0, float(bfmt.leftMargin()))
                    max_w = max(20.0, available - left)
                    w = float(fmt.width()) if fmt.width() > 0 else max_w * 0.7
                    h = float(fmt.height()) if fmt.height() > 0 else 0.0
                    if w > max_w:
                        ratio = max_w / max(1.0, w)
                        w = max_w
                        h = h * ratio if h > 0 else 0.0
                    if h <= 0:
                        name = fmt.name()
                        img = self._asset_image(name[len("asset://"):]) if name.startswith("asset://") else QImage()
                        h = w * img.height() / float(max(1, img.width())) if not img.isNull() else w * 0.65
                    fmt.setWidth(w); fmt.setHeight(h); c.setCharFormat(fmt)
                it += 1
            # Também normaliza a tabela associada ao bloco, sem alterar proporções internas.
            bc = QTextCursor(block)
            table = bc.currentTable()
            if table is not None and table.objectIndex() not in seen_tables:
                seen_tables.add(table.objectIndex())
                tf = table.format()
                width = tf.width()
                if width.type() == QTextLength.FixedLength or (width.type() == QTextLength.PercentageLength and width.rawValue() > 100):
                    tf.setWidth(QTextLength(QTextLength.PercentageLength, 100))
                    table.setFormat(tf)
            block = block.next()

    def _asset_image(self, asset_id):
        project = self._project()
        asset = project.assets.get(asset_id) if project else None
        if not asset:
            return QImage()
        return QImage.fromData(asset.bytes())

    def _image_format_for_asset(self, asset_id, image, width_mm):
        width_px = max(1.0, float(width_mm) / 25.4 * SCREEN_DPI)
        height_px = width_px * image.height() / float(max(1, image.width()))
        fmt = QTextImageFormat()
        fmt.setName("asset://" + asset_id)
        fmt.setWidth(width_px)
        fmt.setHeight(height_px)
        return fmt

    def insert_image_from_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Inserir imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Todos os arquivos (*.*)",
        )
        if not path:
            return
        project = self._project()
        asset = project.add_asset_from_file(path)
        image = QImage.fromData(asset.bytes())
        if image.isNull():
            project.assets.pop(asset.id, None)
            QMessageBox.warning(self, "Imagem", "Não foi possível carregar a imagem selecionada.")
            return

        usable = self.available_width_mm_for_cursor()
        dlg = ImageInsertDialog(image, usable, self)
        if not dlg.exec_():
            project.assets.pop(asset.id, None)
            return
        width_mm, alignment = dlg.result_values()

        self.document().addResource(
            QTextDocument.ImageResource,
            QUrl("asset://" + asset.id),
            image,
        )
        self._insert_image_asset(asset.id, image, width_mm, alignment)

    def _insert_image_asset(self, asset_id, image, width_mm, alignment, cursor=None, append_block=True):
        fmt = self._image_format_for_asset(asset_id, image, width_mm)
        cursor = QTextCursor(cursor or self.textCursor())
        cursor.beginEditBlock()
        block_fmt = cursor.blockFormat()
        block_fmt.setAlignment(_alignment(alignment))
        cursor.setBlockFormat(block_fmt)
        cursor.insertImage(fmt)
        image_pos = cursor.position() - 1
        if append_block:
            cursor.insertBlock()
            next_fmt = cursor.blockFormat()
            next_fmt.setAlignment(Qt.AlignLeft)
            cursor.setBlockFormat(next_fmt)
        cursor.endEditBlock()
        self.setTextCursor(cursor)
        self._select_image_position(image_pos, set_editor_cursor=False)
        return image_pos

    def insert_image_text_layout(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Inserir imagem com texto ao lado",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Todos os arquivos (*.*)",
        )
        if not path:
            return
        project = self._project()
        asset = project.add_asset_from_file(path)
        image = QImage.fromData(asset.bytes())
        if image.isNull():
            project.assets.pop(asset.id, None)
            QMessageBox.warning(self, "Imagem", "Não foi possível carregar a imagem selecionada.")
            return

        current_cursor = self.textCursor()
        if current_cursor.hasSelection() and current_cursor.selectedText().strip():
            answer = QMessageBox.warning(
                self, "Imagem + texto",
                "Há texto selecionado. Criar o layout lado a lado pode substituir a seleção atual.\n\nDeseja continuar?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                project.assets.pop(asset.id, None)
                return

        dlg = ImageTextLayoutDialog(image, self.usable_width_mm(), self)
        if not dlg.exec_():
            project.assets.pop(asset.id, None)
            return
        side, image_column_pct, image_fill_pct = dlg.result_values()

        self.document().addResource(QTextDocument.ImageResource, QUrl("asset://" + asset.id), image)
        cursor = self.textCursor()
        table_fmt = QTextTableFormat()
        table_fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        table_fmt.setBorder(0)
        table_fmt.setCellPadding(6)
        table_fmt.setCellSpacing(0)
        left_pct = image_column_pct if side == "left" else 100 - image_column_pct
        right_pct = 100 - left_pct
        table_fmt.setColumnWidthConstraints([
            QTextLength(QTextLength.PercentageLength, left_pct),
            QTextLength(QTextLength.PercentageLength, right_pct),
        ])
        table_fmt.setProperty(LAYOUT_TABLE_PROPERTY, True)
        table = cursor.insertTable(1, 2, table_fmt)
        image_col = 0 if side == "left" else 1
        text_col = 1 - image_col

        image_cursor = table.cellAt(0, image_col).firstCursorPosition()
        image_block = image_cursor.blockFormat()
        image_block.setAlignment(Qt.AlignHCenter)
        image_cursor.setBlockFormat(image_block)
        image_cell_width = self.usable_width_mm() * image_column_pct / 100.0
        image_width_mm = max(8.0, image_cell_width * image_fill_pct / 100.0)
        self._insert_image_asset(
            asset.id,
            image,
            image_width_mm,
            Qt.AlignHCenter,
            cursor=image_cursor,
            append_block=False,
        )

        text_cursor = table.cellAt(0, text_col).firstCursorPosition()
        text_block = text_cursor.blockFormat()
        text_block.setAlignment(Qt.AlignLeft)
        text_cursor.setBlockFormat(text_block)
        self._clear_image_selection()
        self.setTextCursor(text_cursor)
        self.setFocus()

    def _cursor_selecting_image_at_position(self, document_position):
        if document_position is None:
            return None
        doc = self.document()
        max_pos = max(0, doc.characterCount() - 1)
        for pos in (document_position, document_position - 1):
            if pos < 0 or pos >= max_pos:
                continue
            c = QTextCursor(doc)
            c.setPosition(pos)
            if c.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor):
                if c.charFormat().isImageFormat():
                    return c
        return None

    def _image_cursor_at_point(self, point):
        base = self.cursorForPosition(point)
        return self._cursor_selecting_image_at_position(base.position())

    def _image_cursor_at_position(self):
        cursor = self.textCursor()
        if cursor.hasSelection() and cursor.charFormat().isImageFormat():
            return cursor
        if cursor.charFormat().isImageFormat():
            c = QTextCursor(cursor)
            if not c.hasSelection() and c.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor):
                if c.charFormat().isImageFormat():
                    return c
        return self._cursor_selecting_image_at_position(cursor.position())

    def _selected_image_cursor(self):
        if self._selected_image_pos is None:
            return None
        c = self._cursor_selecting_image_at_position(self._selected_image_pos)
        if c is None:
            self._clear_image_selection()
        return c

    def _select_image_position(self, pos, set_editor_cursor=True):
        c = self._cursor_selecting_image_at_position(pos)
        if c is None:
            self._clear_image_selection()
            return None
        self._selected_image_pos = c.selectionStart()
        if set_editor_cursor:
            self.setTextCursor(c)
        self._refresh_image_handle()
        return c

    def _clear_image_selection(self):
        self._selected_image_pos = None
        if hasattr(self, "_image_handle"):
            self._image_handle.hide()

    def _refresh_image_handle(self):
        if not hasattr(self, "_image_handle"):
            return
        c = self._selected_image_cursor()
        if c is None or not self.isVisible():
            self._image_handle.hide()
            return
        start = QTextCursor(self.document())
        start.setPosition(c.selectionStart())
        end = QTextCursor(self.document())
        end.setPosition(c.selectionEnd())
        r1 = self.cursorRect(start)
        r2 = self.cursorRect(end)
        fmt = c.charFormat().toImageFormat()
        width = max(1, int(round(float(fmt.width()))))
        height = max(1, int(round(float(fmt.height()))))
        left = min(r1.left(), r2.left())
        if r2.left() > r1.left():
            right = r2.left()
        else:
            right = left + width
        top = min(r1.top(), r2.top())
        bottom = max(r1.bottom(), r2.bottom(), top + height)
        x = int(right - self._image_handle.width() / 2)
        y = int(bottom - self._image_handle.height() / 2)
        if x < -self._image_handle.width() or y < -self._image_handle.height() or x > self.viewport().width() or y > self.viewport().height():
            self._image_handle.hide()
            return
        self._image_handle.move(x, y)
        self._image_handle.raise_()
        self._image_handle.show()

    def _resize_selected_image_from_drag(self, start_width, start_height, delta_x):
        c = self._selected_image_cursor()
        if c is None:
            return
        fmt = c.charFormat().toImageFormat()
        min_width = 28.0
        available_width = self.available_width_mm_for_cursor(c) / 25.4 * SCREEN_DPI
        left_offset = max(0.0, float(c.blockFormat().leftMargin()))
        max_width = max(min_width, available_width - left_offset)
        new_width = min(max_width, max(min_width, float(start_width) + float(delta_x)))
        if start_width > 0 and start_height > 0:
            ratio = float(start_height) / float(start_width)
        else:
            name = fmt.name()
            image = self._asset_image(name[len("asset://"):]) if name.startswith("asset://") else QImage()
            ratio = image.height() / float(max(1, image.width())) if not image.isNull() else 0.65
        fmt.setWidth(new_width)
        fmt.setHeight(new_width * ratio)
        c.setCharFormat(fmt)
        self._selected_image_pos = c.selectionStart()
        self._refresh_image_handle()

    def _selected_asset_id(self):
        cursor = self._selected_image_cursor() or self._image_cursor_at_position()
        if cursor is None:
            return None, None
        fmt = cursor.charFormat().toImageFormat()
        name = str(fmt.name() or "")
        if not name.startswith("asset://"):
            return cursor, None
        return cursor, name[len("asset://"):]

    def replace_selected_image(self):
        """Troca somente a ocorrência selecionada, preservando largura/posição."""
        cursor, old_asset_id = self._selected_asset_id()
        if cursor is None or not old_asset_id:
            QMessageBox.information(self, "Substituir imagem", "Selecione uma imagem primeiro.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Substituir imagem", "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Todos os arquivos (*.*)",
        )
        if not path:
            return
        project = self._project()
        asset = project.add_asset_from_file(path)
        image = QImage.fromData(asset.bytes())
        if image.isNull():
            project.assets.pop(asset.id, None)
            QMessageBox.warning(self, "Substituir imagem", "Não foi possível carregar a nova imagem.")
            return

        old_fmt = cursor.charFormat().toImageFormat()
        width = float(old_fmt.width()) if old_fmt.width() > 0 else self.available_width_mm_for_cursor(cursor) / 25.4 * SCREEN_DPI * 0.5
        height = width * image.height() / float(max(1, image.width()))
        new_fmt = QTextImageFormat()
        new_fmt.setName("asset://" + asset.id)
        new_fmt.setWidth(width)
        new_fmt.setHeight(height)
        if old_fmt.isAnchor():
            new_fmt.setAnchor(True)
            new_fmt.setAnchorHref(old_fmt.anchorHref())
        self.document().addResource(QTextDocument.ImageResource, QUrl("asset://" + asset.id), image)
        cursor.setCharFormat(new_fmt)
        self._selected_image_pos = cursor.selectionStart()
        self.setTextCursor(cursor)
        self._refresh_image_handle()

    def replace_selected_image_source(self):
        """Troca o recurso mantendo o mesmo asset id; todas as referências passam a usar o novo arquivo."""
        cursor, asset_id = self._selected_asset_id()
        if cursor is None or not asset_id:
            QMessageBox.information(self, "Substituir origem", "Selecione uma imagem primeiro.")
            return
        project = self._project()
        asset = project.assets.get(asset_id) if project else None
        if not asset:
            return
        answer = QMessageBox.question(
            self, "Substituir origem da imagem",
            "Isto substitui o arquivo-fonte deste recurso e pode alterar todas as ocorrências que usam a mesma imagem.\n\nContinuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Nova origem da imagem", "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;Todos os arquivos (*.*)",
        )
        if not path:
            return
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self, "Substituir origem", "O novo arquivo não é uma imagem válida.")
            return
        asset = project.replace_asset_from_file(asset_id, path)
        image = QImage.fromData(asset.bytes()) if asset else QImage()
        self.document().addResource(QTextDocument.ImageResource, QUrl("asset://" + asset_id), image)

        # Atualiza a proporção das ocorrências visíveis deste tópico sem mexer na largura escolhida.
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and frag.charFormat().isImageFormat():
                    f = frag.charFormat().toImageFormat()
                    if f.name() == "asset://" + asset_id:
                        c = QTextCursor(doc)
                        c.setPosition(frag.position())
                        c.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
                        width = float(f.width()) if f.width() > 0 else 100.0
                        f.setHeight(width * image.height() / float(max(1, image.width())))
                        c.setCharFormat(f)
                it += 1
            block = block.next()
        self.viewport().update()
        self._refresh_image_handle()

    def edit_current_image(self):
        cursor = self._selected_image_cursor() or self._image_cursor_at_position()
        if cursor is None:
            QMessageBox.information(self, "Ajustar imagem", "Clique na imagem ou posicione o cursor junto dela.")
            return
        current = cursor.charFormat().toImageFormat()
        name = current.name()
        if not name.startswith("asset://"):
            QMessageBox.warning(self, "Ajustar imagem", "Esta imagem não está vinculada aos recursos do projeto.")
            return
        asset_id = name[len("asset://"):]
        image = self._asset_image(asset_id)
        if image.isNull():
            QMessageBox.warning(self, "Ajustar imagem", "Não foi possível localizar a imagem no projeto.")
            return
        usable = self.available_width_mm_for_cursor(cursor)
        width_mm = (current.width() / SCREEN_DPI * 25.4) if current.width() > 0 else usable * 0.7
        current_alignment = _alignment(cursor.blockFormat().alignment())
        dlg = ImageInsertDialog(
            image,
            usable,
            self,
            title="Ajustar imagem",
            initial_width_mm=width_mm,
            initial_alignment=current_alignment,
        )
        if not dlg.exec_():
            return
        new_width_mm, new_alignment = dlg.result_values()
        width_px = new_width_mm / 25.4 * SCREEN_DPI
        current.setWidth(width_px)
        current.setHeight(width_px * image.height() / float(max(1, image.width())))
        cursor.setCharFormat(current)
        block = cursor.blockFormat()
        block.setAlignment(_alignment(new_alignment))
        block.setLeftMargin(0)
        block.setRightMargin(0)
        cursor.setBlockFormat(block)
        self._selected_image_pos = cursor.selectionStart()
        self.setTextCursor(cursor)
        self._refresh_image_handle()

    def align_current_image(self, alignment):
        cursor = self._selected_image_cursor() or self._image_cursor_at_position()
        if cursor is None:
            return
        block = cursor.blockFormat()
        block.setAlignment(_alignment(alignment))
        block.setLeftMargin(0)
        block.setRightMargin(0)
        cursor.setBlockFormat(block)
        self._selected_image_pos = cursor.selectionStart()
        self.setTextCursor(cursor)
        self._refresh_image_handle()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            c = self._image_cursor_at_point(event.pos())
            if c is not None:
                self._selected_image_pos = c.selectionStart()
                self.setTextCursor(c)
                block = c.blockFormat()
                fmt = c.charFormat().toImageFormat()
                available_px = self.available_width_mm_for_cursor(c) / 25.4 * SCREEN_DPI
                image_w = float(fmt.width()) if fmt.width() > 0 else available_px * 0.5
                align = _alignment(block.alignment())
                if float(block.leftMargin()) > 0:
                    start_left = float(block.leftMargin())
                elif align == Qt.AlignRight:
                    start_left = max(0.0, available_px - image_w)
                elif align == Qt.AlignHCenter:
                    start_left = max(0.0, (available_px - image_w) / 2.0)
                else:
                    start_left = 0.0
                self._image_move_state = {
                    "start_x": event.globalX(), "start_left": start_left,
                    "available": available_px, "image_w": image_w,
                }
                self._refresh_image_handle()
                event.accept()
                return
            self._image_move_state = None
            self._clear_image_selection()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._image_move_state and (event.buttons() & Qt.LeftButton):
            c = self._selected_image_cursor()
            if c is not None:
                state = self._image_move_state
                max_left = max(0.0, float(state["available"]) - float(state["image_w"]))
                left = max(0.0, min(max_left, float(state["start_left"]) + event.globalX() - float(state["start_x"])))
                block = c.blockFormat()
                block.setAlignment(Qt.AlignLeft)
                block.setLeftMargin(left)
                block.setRightMargin(0)
                c.setBlockFormat(block)
                self._selected_image_pos = c.selectionStart()
                self._refresh_image_handle()
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._image_move_state and event.button() == Qt.LeftButton:
            self._image_move_state = None
            self._refresh_image_handle()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _selection_contains_image(self, cursor=None):
        c = QTextCursor(cursor or self.textCursor())
        if not c.hasSelection():
            return bool(c.charFormat().isImageFormat())
        start, end = c.selectionStart(), c.selectionEnd()
        probe = QTextCursor(self.document())
        for pos in range(start, end):
            probe.setPosition(pos)
            if probe.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor) and probe.charFormat().isImageFormat():
                return True
        return False

    def _adjacent_image_cursor(self, backwards=False):
        c = QTextCursor(self.textCursor())
        pos = c.position() - 1 if backwards else c.position()
        return self._cursor_selecting_image_at_position(pos)

    def _show_image_protection_hint(self):
        QApplication.beep()
        QToolTip.showText(
            self.mapToGlobal(self.cursorRect().bottomRight()),
            "Imagem protegida. Use botão direito → Imagem → Excluir imagem...",
            self,
        )

    def keyPressEvent(self, event):
        key = event.key()
        cursor = self.textCursor()
        if self._selection_contains_image(cursor):
            allowed = {Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down, Qt.Key_Escape}
            if event.matches(QKeySequence.Copy):
                return super().keyPressEvent(event)
            if key not in allowed:
                self._show_image_protection_hint()
                event.accept()
                return
        if key == Qt.Key_Backspace and self._adjacent_image_cursor(True) is not None:
            self._show_image_protection_hint(); event.accept(); return
        if key == Qt.Key_Delete and self._adjacent_image_cursor(False) is not None:
            self._show_image_protection_hint(); event.accept(); return
        super().keyPressEvent(event)

    def cut(self):
        if self._selection_contains_image(self.textCursor()):
            self._show_image_protection_hint()
            return
        super().cut()

    def delete_current_image(self):
        c = self._selected_image_cursor() or self._image_cursor_at_position()
        if c is None:
            return
        answer = QMessageBox.question(
            self, "Excluir imagem",
            "Excluir esta imagem do documento?\n\nEsta ação é deliberadamente protegida para evitar remoções acidentais.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        c.removeSelectedText()
        self._clear_image_selection()

    def mouseDoubleClickEvent(self, event):
        c = self._image_cursor_at_point(event.pos())
        if c is not None:
            self._selected_image_pos = c.selectionStart()
            self.setTextCursor(c)
            self.edit_current_image()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_image_handle()

    def remove_selected_image_background(self):
        c = self._selected_image_cursor() or self._image_cursor_at_position()
        if c is None:
            QMessageBox.information(self, "Remover fundo", "Selecione uma imagem primeiro.")
            return
        fmt = c.charFormat().toImageFormat()
        name = fmt.name()
        if not name.startswith("asset://"):
            return
        project = self._project()
        asset = project.assets.get(name[len("asset://"):]) if project else None
        if not asset:
            return
        tolerance, ok = QInputDialog.getInt(
            self, "Remover fundo por cor",
            "Tolerância da cor de fundo (amostra dos quatro cantos):",
            35, 1, 160, 1,
        )
        if not ok:
            return
        try:
            from PIL import Image
            import io, math
            img = Image.open(io.BytesIO(asset.bytes())).convert("RGBA")
            px = img.load(); w, h = img.size
            corners = [px[0,0][:3], px[w-1,0][:3], px[0,h-1][:3], px[w-1,h-1][:3]]
            bg = tuple(sum(c[i] for c in corners)//4 for i in range(3))
            limit2 = int(tolerance) ** 2 * 3
            data = list(img.getdata())
            out = []
            br,bg2,bb = bg
            for r,g,b,a in data:
                d = (r-br)*(r-br) + (g-bg2)*(g-bg2) + (b-bb)*(b-bb)
                out.append((r,g,b,0 if d <= limit2 else a))
            img.putdata(out)
            buf = io.BytesIO(); img.save(buf, format="PNG")
            new_asset = project.add_asset_bytes(buf.getvalue(), Path(asset.filename).stem + "_sem_fundo.png", "image/png")
            qimg = QImage.fromData(new_asset.bytes())
            self.document().addResource(QTextDocument.ImageResource, QUrl("asset://" + new_asset.id), qimg)
            fmt.setName("asset://" + new_asset.id)
            c.setCharFormat(fmt)
            self._selected_image_pos = c.selectionStart()
            self._refresh_image_handle()
        except Exception as exc:
            QMessageBox.warning(self, "Remover fundo", f"Não foi possível processar a imagem.\n\n{exc}")

    def _cell_contains_image(self, cell):
        c = cell.firstCursorPosition(); end = cell.lastCursorPosition().position()
        while c.position() < end:
            probe = QTextCursor(c)
            if probe.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor) and probe.charFormat().isImageFormat():
                return True
            c.movePosition(QTextCursor.NextCharacter)
        return False

    def _is_image_text_layout(self, table):
        if table is None:
            return False
        try:
            if bool(table.format().property(LAYOUT_TABLE_PROPERTY)):
                return True
        except Exception:
            pass
        if table.rows() == 1 and table.columns() == 2 and float(table.format().border()) <= 0.1:
            return self._cell_contains_image(table.cellAt(0,0)) or self._cell_contains_image(table.cellAt(0,1))
        return False

    def _confirm_layout_table_change(self, table, action):
        if not self._is_image_text_layout(table):
            return True
        return QMessageBox.warning(
            self, "Layout imagem + texto",
            f"Esta tabela controla um layout de imagem com texto ao lado. {action} pode desmontar o layout e afetar o texto da outra coluna.\n\nDeseja continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes

    def set_selected_image_link(self):
        cursor = self._selected_image_cursor() or self._image_cursor_at_position()
        if cursor is None:
            QMessageBox.information(self, "Link da imagem", "Selecione uma imagem primeiro.")
            return
        fmt = cursor.charFormat().toImageFormat()
        current = fmt.anchorHref() if fmt.isAnchor() else ""
        url, ok = QInputDialog.getText(
            self, "Link da imagem", "Endereço do link (https://, arquivo relativo ou #âncora):", text=current
        )
        if not ok:
            return
        url = str(url).strip()
        fmt.setAnchor(bool(url))
        fmt.setAnchorHref(url)
        cursor.setCharFormat(fmt)
        self._selected_image_pos = cursor.selectionStart()
        self.setTextCursor(cursor)
        self._refresh_image_handle()

    def remove_selected_image_link(self):
        cursor = self._selected_image_cursor() or self._image_cursor_at_position()
        if cursor is None:
            return
        fmt = cursor.charFormat().toImageFormat()
        fmt.setAnchor(False)
        fmt.setAnchorHref("")
        cursor.setCharFormat(fmt)
        self._selected_image_pos = cursor.selectionStart()
        self._refresh_image_handle()

    def insert_code_block(self):
        language, ok = QInputDialog.getItem(
            self, "Bloco de código", "Linguagem (somente identificação visual):",
            ["Texto", "C/C++", "Python", "JSON", "JavaScript", "HTML", "CSS", "Shell"], 0, False,
        )
        if not ok:
            return
        code, ok = QInputDialog.getMultiLineText(
            self, "Inserir bloco de código", "Código:", ""
        )
        if not ok or not str(code):
            return
        lang_class = {
            "C/C++":"cpp", "Python":"python", "JSON":"json", "JavaScript":"javascript",
            "HTML":"html", "CSS":"css", "Shell":"shell", "Texto":"text",
        }.get(str(language), "text")
        escaped = html.escape(str(code))
        cursor = self.textCursor()
        cursor.beginEditBlock()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        cursor.insertHtml(
            f'<pre data-language="{lang_class}" style="font-family:Consolas, Courier New, monospace; '
            'background:#f2f4f6; border:1px solid #d7dce2; padding:8px; white-space:pre-wrap;">'
            f'<code>{escaped}</code></pre>'
        )
        cursor.insertBlock()
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def contextMenuEvent(self, event):
        point = event.pos()
        cursor = self.cursorForPosition(point)
        image_cursor = self._image_cursor_at_point(point)
        table = cursor.currentTable()
        if table is not None and image_cursor is None and not self.textCursor().hasSelection():
            self.setTextCursor(cursor)

        if image_cursor is not None:
            self._selected_image_pos = image_cursor.selectionStart()
            self.setTextCursor(image_cursor)

        menu = self.createStandardContextMenu()
        if image_cursor is not None:
            menu.addSeparator()
            image_menu = menu.addMenu("Imagem")
            resize = image_menu.addAction("Tamanho e posição...")
            resize.triggered.connect(self.edit_current_image)
            replace_one = image_menu.addAction("Substituir esta imagem...")
            replace_one.triggered.connect(self.replace_selected_image)
            replace_source = image_menu.addAction("Substituir arquivo de origem...")
            replace_source.triggered.connect(self.replace_selected_image_source)
            image_menu.addSeparator()
            image_menu.addAction("Alinhar à esquerda", lambda _=False: self.align_current_image(Qt.AlignLeft))
            image_menu.addAction("Centralizar", lambda _=False: self.align_current_image(Qt.AlignHCenter))
            image_menu.addAction("Alinhar à direita", lambda _=False: self.align_current_image(Qt.AlignRight))
            image_menu.addSeparator()
            link_action = image_menu.addAction("Definir/editar link da imagem...")
            link_action.triggered.connect(self.set_selected_image_link)
            unlink_action = image_menu.addAction("Remover link da imagem")
            unlink_action.triggered.connect(self.remove_selected_image_link)
            image_menu.addSeparator()
            image_menu.addAction("Remover fundo por cor...", self.remove_selected_image_background)
            image_menu.addSeparator()
            delete_img = image_menu.addAction("Excluir imagem...")
            delete_img.triggered.connect(self.delete_current_image)

        if table is not None:
            menu.addSeparator()
            table_menu = menu.addMenu("Tabela")
            props = table_menu.addAction("Propriedades / tamanho...")
            props.triggered.connect(self.edit_current_table)
            table_menu.addAction("Inserir imagem nesta célula...", self.insert_image_from_file)
            table_menu.addSeparator()
            table_menu.addAction("Inserir linha acima", lambda _=False: self.insert_table_row(False))
            table_menu.addAction("Inserir linha abaixo", lambda _=False: self.insert_table_row(True))
            table_menu.addAction("Inserir coluna à esquerda", lambda _=False: self.insert_table_column(False))
            table_menu.addAction("Inserir coluna à direita", lambda _=False: self.insert_table_column(True))
            table_menu.addSeparator()
            table_menu.addAction("Remover linha", self.remove_table_row)
            table_menu.addAction("Remover coluna", self.remove_table_column)

        if self.textCursor().hasSelection() and not self.textCursor().charFormat().isImageFormat():
            menu.addSeparator()
            fmt_menu = menu.addMenu("Formatar seleção")
            fmt_menu.addAction("Fonte...", self.choose_font_for_selection)
            size_menu = fmt_menu.addMenu("Tamanho")
            for pt in (8, 9, 10, 10.5, 11, 12, 14, 16, 18, 20, 24, 28, 32):
                size_menu.addAction(f"{pt:g} pt", lambda _=False, p=pt: self.set_font_size(p))
            fmt_menu.addAction("Cor do texto...", self.choose_text_color)
            fmt_menu.addAction("Realce...", self.choose_highlight_color)

        menu.exec_(event.globalPos())
        menu.deleteLater()
        self._refresh_image_handle()

    def insert_link(self):
        cursor = self.textCursor()
        selected = cursor.selectedText()
        url, ok = QInputDialog.getText(self, "Inserir link", "URL:")
        if not ok or not url.strip():
            return
        label = selected
        if not label:
            label, ok = QInputDialog.getText(self, "Texto do link", "Texto:", text=url)
            if not ok:
                return
        fmt = QTextCharFormat()
        fmt.setAnchor(True)
        fmt.setAnchorHref(url.strip())
        fmt.setForeground(Qt.blue)
        fmt.setFontUnderline(True)
        cursor.insertText(label, fmt)

    def insert_table(self):
        dlg = TableInsertDialog(self)
        if not dlg.exec_():
            return
        rows, cols, width_pct, border, padding, header = dlg.result_values()
        fmt = QTextTableFormat()
        fmt.setCellPadding(padding)
        fmt.setCellSpacing(0)
        fmt.setBorder(border)
        fmt.setWidth(QTextLength(QTextLength.PercentageLength, width_pct))
        fmt.setColumnWidthConstraints([
            QTextLength(QTextLength.PercentageLength, 100.0 / cols) for _ in range(cols)
        ])
        table = self.textCursor().insertTable(rows, cols, fmt)
        if header and rows > 0:
            for col in range(cols):
                c = table.cellAt(0, col).firstCursorPosition()
                char = QTextCharFormat()
                char.setFontWeight(QFont.Bold)
                c.mergeCharFormat(char)

    def edit_current_table(self):
        cursor = self.textCursor()
        table = cursor.currentTable()
        if table is None:
            QMessageBox.information(self, "Tabela", "Posicione o cursor dentro da tabela que deseja editar.")
            return
        if not self._confirm_layout_table_change(table, "Alterar as propriedades"):
            return
        dlg = TablePropertiesDialog(table, self)
        if dlg.exec_():
            dlg.apply_to_table(table)

    def _current_table_cell(self):
        cursor = self.textCursor()
        table = cursor.currentTable()
        if table is None:
            return None, None
        cell = table.cellAt(cursor)
        return table, cell

    def insert_table_row(self, after=True):
        table, cell = self._current_table_cell()
        if table is None or not cell.isValid():
            return
        if not self._confirm_layout_table_change(table, "Inserir uma linha"):
            return
        row = cell.row() + (1 if after else 0)
        table.insertRows(row, 1)

    def insert_table_column(self, after=True):
        table, cell = self._current_table_cell()
        if table is None or not cell.isValid():
            return
        if not self._confirm_layout_table_change(table, "Inserir uma coluna"):
            return
        col = cell.column() + (1 if after else 0)
        old_cols = table.columns()
        table.insertColumns(col, 1)
        fmt = table.format()
        fmt.setColumnWidthConstraints([
            QTextLength(QTextLength.PercentageLength, 100.0 / max(1, old_cols + 1))
            for _ in range(old_cols + 1)
        ])
        table.setFormat(fmt)

    def remove_table_row(self):
        table, cell = self._current_table_cell()
        if table is None or not cell.isValid():
            return
        if not self._confirm_layout_table_change(table, "Remover uma linha"):
            return
        if table.rows() <= 1:
            QMessageBox.information(self, "Tabela", "A tabela precisa manter pelo menos uma linha.")
            return
        table.removeRows(cell.row(), 1)

    def remove_table_column(self):
        table, cell = self._current_table_cell()
        if table is None or not cell.isValid():
            return
        if not self._confirm_layout_table_change(table, "Remover uma coluna"):
            return
        if table.columns() <= 1:
            QMessageBox.information(self, "Tabela", "A tabela precisa manter pelo menos uma coluna.")
            return
        table.removeColumns(cell.column(), 1)
        cols = table.columns()
        fmt = table.format()
        fmt.setColumnWidthConstraints([
            QTextLength(QTextLength.PercentageLength, 100.0 / cols) for _ in range(cols)
        ])
        table.setFormat(fmt)

    def insert_page_break(self):
        cursor = self.textCursor()
        cursor.insertBlock()
        block = cursor.blockFormat()
        block.setPageBreakPolicy(QTextFormat.PageBreak_AlwaysBefore)
        cursor.setBlockFormat(block)
        cursor.insertText(" ")
        cursor.insertBlock()

    def insert_horizontal_rule(self):
        self.textCursor().insertHtml('<hr style="margin:12px 0; border:0; border-top:1px solid #888;">')

    def set_heading_level(self, level: int):
        cursor = self.textCursor()
        block = cursor.blockFormat()
        char = QTextCharFormat()
        project = self._project()
        meta = project.meta if project else {}
        if level <= 0:
            block.setTopMargin(0)
            block.setBottomMargin(float(meta.get("paragraph_spacing_pt", 5)))
            char.setFontPointSize(float(meta.get("body_font_size_pt", 10.5)))
            char.setFontWeight(QFont.Normal)
        else:
            sizes = {
                1: float(meta.get("heading1_size_pt", 20)),
                2: float(meta.get("heading2_size_pt", 16)),
                3: float(meta.get("heading3_size_pt", 13)),
                4: max(10.0, float(meta.get("heading3_size_pt", 13)) - 1),
            }
            char.setFontPointSize(sizes.get(level, 11))
            char.setFontWeight(QFont.Bold)
            block.setTopMargin(12)
            block.setBottomMargin(6)
        cursor.mergeBlockFormat(block)
        cursor.mergeCharFormat(char)
        self.mergeCurrentCharFormat(char)

    def set_font_family(self, font):
        fmt = QTextCharFormat()
        fmt.setFontFamily(font.family())
        self.mergeCurrentCharFormat(fmt)

    def set_font_size(self, size):
        if size <= 0:
            return
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self.mergeCurrentCharFormat(fmt)

    def choose_font_for_selection(self):
        font, ok = QFontDialog.getFont(self.currentFont(), self, "Fonte")
        if not ok:
            return
        fmt = QTextCharFormat()
        fmt.setFont(font)
        self.mergeCurrentCharFormat(fmt)

    def toggle_bullets(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        if cursor.currentList():
            block = cursor.blockFormat()
            block.setIndent(0)
            cursor.setBlockFormat(block)
        else:
            fmt = QTextListFormat()
            fmt.setStyle(QTextListFormat.ListDisc)
            cursor.createList(fmt)
        cursor.endEditBlock()

    def toggle_numbering(self):
        cursor = self.textCursor()
        cursor.beginEditBlock()
        if cursor.currentList():
            block = cursor.blockFormat()
            block.setIndent(0)
            cursor.setBlockFormat(block)
        else:
            fmt = QTextListFormat()
            fmt.setStyle(QTextListFormat.ListDecimal)
            cursor.createList(fmt)
        cursor.endEditBlock()

    def change_indent(self, delta):
        cursor = self.textCursor()
        block = cursor.blockFormat()
        block.setIndent(max(0, block.indent() + int(delta)))
        cursor.mergeBlockFormat(block)

    def choose_text_color(self):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(color)
            self.mergeCurrentCharFormat(fmt)

    def choose_highlight_color(self):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            self.mergeCurrentCharFormat(fmt)


def create_format_toolbar(parent, editor: RichTextEditor) -> QToolBar:
    tb = QToolBar("Formatação", parent)
    tb.setObjectName("format_toolbar")
    tb.setMovable(False)

    font_box = QFontComboBox(tb)
    font_box.setMaximumWidth(180)
    font_box.setCurrentFont(editor.document().defaultFont())
    font_box.currentFontChanged.connect(editor.set_font_family)
    tb.addWidget(font_box)

    size_box = QDoubleSpinBox(tb)
    size_box.setRange(6, 96)
    size_box.setDecimals(1)
    size_box.setSuffix(" pt")
    size_box.setMaximumWidth(82)
    project = editor._project()
    size_box.setValue(float(project.meta.get("body_font_size_pt", 10.5)) if project else 10.5)
    size_box.valueChanged.connect(editor.set_font_size)
    tb.addWidget(size_box)

    tb.addSeparator()
    bold = QAction("B", parent)
    bold.setCheckable(True)
    bold.setShortcut("Ctrl+B")
    bold.triggered.connect(lambda checked: editor.setFontWeight(QFont.Bold if checked else QFont.Normal))
    tb.addAction(bold)

    italic = QAction("I", parent)
    italic.setCheckable(True)
    italic.setShortcut("Ctrl+I")
    italic.triggered.connect(editor.setFontItalic)
    tb.addAction(italic)

    underline = QAction("U", parent)
    underline.setCheckable(True)
    underline.setShortcut("Ctrl+U")
    underline.triggered.connect(editor.setFontUnderline)
    tb.addAction(underline)

    tb.addSeparator()
    for level, label in [(0, "Texto"), (1, "H1"), (2, "H2"), (3, "H3")]:
        act = QAction(label, parent)
        act.triggered.connect(lambda _=False, lv=level: editor.set_heading_level(lv))
        tb.addAction(act)

    tb.addSeparator()
    left = QAction("Esq.", parent)
    left.setCheckable(True)
    left.triggered.connect(lambda: editor.setAlignment(Qt.AlignLeft))
    tb.addAction(left)
    center = QAction("Centro", parent)
    center.setCheckable(True)
    center.triggered.connect(lambda: editor.setAlignment(Qt.AlignHCenter))
    tb.addAction(center)
    right = QAction("Dir.", parent)
    right.setCheckable(True)
    right.triggered.connect(lambda: editor.setAlignment(Qt.AlignRight))
    tb.addAction(right)
    justify = QAction("Just.", parent)
    justify.setCheckable(True)
    justify.triggered.connect(lambda: editor.setAlignment(Qt.AlignJustify))
    tb.addAction(justify)

    tb.addSeparator()
    bullets = QAction("• Lista", parent)
    bullets.triggered.connect(editor.toggle_bullets)
    tb.addAction(bullets)
    numbers = QAction("1. Lista", parent)
    numbers.triggered.connect(editor.toggle_numbering)
    tb.addAction(numbers)
    outdent = QAction("← Recuo", parent)
    outdent.triggered.connect(lambda: editor.change_indent(-1))
    tb.addAction(outdent)
    indent = QAction("Recuo →", parent)
    indent.triggered.connect(lambda: editor.change_indent(1))
    tb.addAction(indent)

    tb.addSeparator()
    img = QAction("Imagem", parent)
    img.triggered.connect(editor.insert_image_from_file)
    tb.addAction(img)
    image_text = QAction("Imagem + texto", parent)
    image_text.triggered.connect(editor.insert_image_text_layout)
    tb.addAction(image_text)
    image_props = QAction("Ajustar imagem", parent)
    image_props.triggered.connect(editor.edit_current_image)
    tb.addAction(image_props)
    table = QAction("Tabela", parent)
    table.triggered.connect(editor.insert_table)
    tb.addAction(table)
    link = QAction("Link", parent)
    link.triggered.connect(editor.insert_link)
    tb.addAction(link)
    code = QAction("Código", parent)
    code.triggered.connect(editor.insert_code_block)
    tb.addAction(code)

    tb.addSeparator()
    color = QAction("Cor", parent)
    color.triggered.connect(editor.choose_text_color)
    tb.addAction(color)
    highlight = QAction("Realce", parent)
    highlight.triggered.connect(editor.choose_highlight_color)
    tb.addAction(highlight)

    def sync_char_format(fmt):
        font_box.blockSignals(True)
        size_box.blockSignals(True)
        bold.blockSignals(True)
        italic.blockSignals(True)
        underline.blockSignals(True)
        try:
            if fmt.fontFamily():
                font_box.setCurrentFont(QFont(fmt.fontFamily()))
            size = fmt.fontPointSize()
            if size > 0:
                size_box.setValue(size)
            bold.setChecked(fmt.fontWeight() >= QFont.Bold)
            italic.setChecked(fmt.fontItalic())
            underline.setChecked(fmt.fontUnderline())
        finally:
            font_box.blockSignals(False)
            size_box.blockSignals(False)
            bold.blockSignals(False)
            italic.blockSignals(False)
            underline.blockSignals(False)

    def sync_alignment():
        a = editor.alignment()
        actions = (
            (left, bool(a & Qt.AlignLeft)),
            (center, bool(a & Qt.AlignHCenter)),
            (right, bool(a & Qt.AlignRight)),
            (justify, bool(a & Qt.AlignJustify)),
        )
        for action, checked in actions:
            action.blockSignals(True)
            action.setChecked(checked)
            action.blockSignals(False)

    editor.currentCharFormatChanged.connect(sync_char_format)
    editor.cursorPositionChanged.connect(sync_alignment)
    sync_char_format(editor.currentCharFormat())
    sync_alignment()

    return tb
