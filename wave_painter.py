import sys
from PyQt5.QtWidgets import (QApplication, QWidget, QSizePolicy, QPushButton)  # 添加 QPushButton
from PyQt5.QtGui import (QPainter, QPen)
from PyQt5.QtCore import Qt

class wavepainter(QWidget):
    def __init__(self, parent=None, width=400, height=300):
        # 支持作为嵌入控件：接收 parent，不弹独立窗口
        super(wavepainter, self).__init__(parent)
        # 让布局控制大小，同时设置一个合理的最小尺寸
        self.setMinimumSize(width, height)
        sp = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setSizePolicy(sp)
        # 不需要移动或设置窗口标题（由父窗口管理）
        self.setMouseTracking(False)
        self.pos_xy = []

        # 一键清除按钮
        self.clear_btn = QPushButton("清除", self)
        self.clear_btn.setFixedSize(60, 24)
        self.clear_btn.clicked.connect(self.clear)  # 绑定清除方法
        self.clear_btn.setStyleSheet("color: #00D4FF;")
        font = self.clear_btn.font()
        font.setFamily("宋体")
        font.setPointSize(11)
        self.clear_btn.setFont(font)

        # 初始定位，resizeEvent 中会保持位置
        self.clear_btn.move(self.width() - self.clear_btn.width() - 6, 6)

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        pen = QPen(Qt.red, 2, Qt.SolidLine)
        painter.setPen(pen)
        if len(self.pos_xy) > 1:
            point_start = self.pos_xy[0]
            for pos_tmp in self.pos_xy:
                point_end = pos_tmp

                if point_end == (-1, -1):
                    point_start = (-1, -1)
                    continue
                if point_start == (-1, -1):
                    point_start = point_end
                    continue

                painter.drawLine(point_start[0], point_start[1], point_end[0], point_end[1])
                point_start = point_end
        painter.end()

    def mouseMoveEvent(self, event):

        #中间变量pos_tmp提取当前点
        pos_tmp = (event.pos().x(), event.pos().y())
        #pos_tmp添加到self.pos_xy中
        self.pos_xy.append(pos_tmp)

        self.update()

    def mouseReleaseEvent(self, event):
        pos_test = (-1, -1)
        self.pos_xy.append(pos_test)

        self.update()

    def resizeEvent(self, event):
        """在大小变更时保持清除按钮位于右上角"""
        super(wavepainter, self).resizeEvent(event)
        self.clear_btn.move(self.width() - self.clear_btn.width() - 6, 6)

    def clear(self):
        """一键清除：清空轨迹并刷新画布（可从外部调用）"""
        self.pos_xy.clear()
        self.update()
        


