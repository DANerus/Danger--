import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QComboBox, QSlider, QLineEdit, QGroupBox, QGridLayout,
                            QSplitter, QFrame, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtGui import (QColor, QPainter, QPen, QFont, QLinearGradient, QGradient, 
                        QPainterPath, QGuiApplication)

# 自定义波形绘制组件
class WaveformWidget(QWidget):
    def __init__(self, parent=None, waveform_type="oscilloscope"):
        super().__init__(parent)
        self.waveform_type = waveform_type
        self.data = []
        self.channels = []
        self.time_scale = 1  # ms/div
        self.voltage_scale = [1, 2]  # V/div for channels 1 and 2
        self.setMinimumSize(400, 300)
        self.grid_color = QColor(20, 40, 60)
        self.background_color = QColor(10, 20, 30)
        
        # 初始化波形数据
        self.init_waveforms()
        
    def init_waveforms(self):
        if self.waveform_type == "oscilloscope":
            # 通道1: 正弦波
            x = np.linspace(0, 10, 1000)
            y1 = np.sin(2 * np.pi * x)
            
            # 通道2: 方波
            y2 = np.where((x % 1) < 0.5, 3, 0)
            
            self.channels = [
                {"name": "通道1", "color": QColor(0, 255, 255, 200), "data": y1},
                {"name": "通道2", "color": QColor(255, 150, 0, 200), "data": y2}
            ]
        elif self.waveform_type == "signal_generator":
            # 方波
            x = np.linspace(0, 10, 1000)
            y = np.where((x % 1) < 0.5, 1, -1)
            self.channels = [{"name": "输出", "color": QColor(0, 255, 255, 200), "data": y}]
        elif self.waveform_type == "pwm_generator":
            # PWM波形
            x = np.linspace(0, 10, 1000)
            y = np.where((x % 1) < 0.15, 1, 0)  # 15%占空比
            self.channels = [{"name": "PWM", "color": QColor(0, 255, 255, 200), "data": y}]
        elif self.waveform_type == "logic_analyzer":
            # 多通道逻辑信号
            self.channels = []
            colors = [QColor(0, 255, 255), QColor(0, 255, 0), QColor(255, 150, 0), 
                      QColor(255, 0, 0), QColor(255, 0, 255), QColor(255, 255, 0)]
            
            for i in range(6):
                freq = 1 + i * 0.5
                x = np.linspace(0, 10, 1000)
                y = np.where(np.sin(2 * np.pi * freq * x) > 0, i * 2 + 1, i * 2)
                self.channels.append({
                    "name": f"D{i+1}", 
                    "color": colors[i % len(colors)], 
                    "data": y
                })
        elif self.waveform_type == "spectrum":
            # 频谱图 - 修复了数组形状问题
            x = np.linspace(0, 25, 1000)
            y = np.random.normal(-40, 10, 1000)
            # 确保峰值索引在有效范围内
            peak_idx = min(max(int(450 / 25 * len(x)), 10), len(x)-10)
            y[peak_idx-10:peak_idx+10] = np.linspace(-40, -9.5, 20)
            self.channels = [{"name": "频谱", "color": QColor(0, 255, 255, 200), "data": y}]        
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        painter.fillRect(self.rect(), self.background_color)
        
        # 绘制网格
        self.draw_grid(painter)
        
        # 绘制波形
        self.draw_waveforms(painter)
        
        # 绘制配置信息
        if self.waveform_type in ["signal_generator", "pwm_generator"]:
            self.draw_output_config(painter)
    
    def draw_grid(self, painter):
        pen = QPen(self.grid_color, 0.5)
        painter.setPen(pen)
        
        width = self.width()
        height = self.height()
        
        # 水平网格线
        for i in range(11):
            y = i * height / 10
            painter.drawLine(0, y, width, y)
        
        # 垂直网格线
        for i in range(11):
            x = i * width / 10
            painter.drawLine(x, 0, x, height)
        
        # 中心水平线
        pen.setColor(QColor(50, 80, 120))
        pen.setWidth(1.5)
        painter.setPen(pen)
        painter.drawLine(0, height/2, width, height/2)
    
    def draw_waveforms(self, painter):
        width = self.width()
        height = self.height()
        
        for channel in self.channels:
            pen = QPen(channel["color"], 2)
            if self.waveform_type == "spectrum":
                pen.setWidth(1)
            painter.setPen(pen)
            
            path = QPainterPath()
            data = channel["data"]
            x_step = width / len(data)
            
            # 波形发光效果
            if self.waveform_type != "spectrum":
                glow_pen = QPen(channel["color"], 4, Qt.SolidLine)
                alpha = channel["color"].alpha() // 4
                glow_pen.setColor(QColor(channel["color"].red(), channel["color"].green(), 
                                        channel["color"].blue(), alpha))
                painter.setPen(glow_pen)
                
                glow_path = QPainterPath()
                for i, y_val in enumerate(data):
                    x = i * x_step
                    if self.waveform_type == "logic_analyzer":
                        # 逻辑分析仪波形 (数字信号)
                        scaled_y = height - (y_val / 12 * height + height/12)
                    else:
                        # 模拟信号
                        scaled_y = height/2 - (y_val * height/4)
                    
                    if i == 0:
                        glow_path.moveTo(x, scaled_y)
                    else:
                        glow_path.lineTo(x, scaled_y)
                
                painter.drawPath(glow_path)
                painter.setPen(pen)
            
            # 绘制主波形
            for i, y_val in enumerate(data):
                x = i * x_step
                if self.waveform_type == "logic_analyzer":
                    # 逻辑分析仪波形 (数字信号)
                    scaled_y = height - (y_val / 12 * height + height/12)
                elif self.waveform_type == "spectrum":
                    # 频谱图 (垂直绘制)
                    scaled_y = height - (y_val + 50) * height / 50  # 缩放-50dB到0dB范围
                else:
                    # 模拟信号
                    scaled_y = height/2 - (y_val * height/4)
                
                if i == 0:
                    path.moveTo(x, scaled_y)
                else:
                    path.lineTo(x, scaled_y)
            
            painter.drawPath(path)
            
            # 添加通道标签
            painter.drawText(10, 20 + self.channels.index(channel) * 20, 
                            f"{channel['name']}")
    
    def draw_output_config(self, painter):
        # 绘制右上角的输出配置信息
        config_rect = QRectF(self.width() - 200, 10, 190, 100)
        
        # 半透明背景
        painter.setBrush(QColor(20, 40, 60, 150))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(config_rect, 5, 5)
        
        # 文本
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPointSize(10)
        painter.setFont(font)
        
        if self.waveform_type == "signal_generator":
            painter.drawText(config_rect.adjusted(10, 10, 0, 0), "输出配置")
            painter.drawText(config_rect.adjusted(10, 30, 0, 0), "波形: 方波")
            painter.drawText(config_rect.adjusted(10, 50, 0, 0), "频率: 1.00 kHz")
            painter.drawText(config_rect.adjusted(10, 70, 0, 0), "幅度: 1.0 V")
            painter.drawText(config_rect.adjusted(10, 90, 0, 0), "偏移: 0.0 V")
        elif self.waveform_type == "pwm_generator":
            painter.drawText(config_rect.adjusted(10, 10, 0, 0), "PWM输出配置")
            painter.drawText(config_rect.adjusted(10, 30, 0, 0), "频率: 1.00 kHz")
            painter.drawText(config_rect.adjusted(10, 50, 0, 0), "幅度: 3.3 V")
            painter.drawText(config_rect.adjusted(10, 70, 0, 0), "占空比: 15%")

# 控制面板组件
class ControlPanel(QWidget):
    def __init__(self, parent=None, panel_type="oscilloscope"):
        super().__init__(parent)
        self.panel_type = panel_type
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        
        self.setStyleSheet("background-color: #1a2436; color: #ffffff;")
        
        if self.panel_type == "oscilloscope":
            self.create_oscilloscope_controls(layout)
        elif self.panel_type == "spectrum":
            self.create_spectrum_controls(layout)
        elif self.panel_type == "signal_generator":
            self.create_signal_generator_controls(layout)
        elif self.panel_type == "pwm_generator":
            self.create_pwm_controls(layout)
        elif self.panel_type == "logic_analyzer":
            self.create_logic_analyzer_controls(layout)
        elif self.panel_type == "power_supply":
            self.create_power_supply_controls(layout)
    
    def create_oscilloscope_controls(self, layout):
        # 通道控制
        channel_group = QGroupBox("控制")
        channel_layout = QVBoxLayout()
        
        # 通道1
        ch1_layout = QHBoxLayout()
        ch1_check = QCheckBox("启用")
        ch1_check.setChecked(True)
        ch1_label = QLabel("通道1")
        ch1_combo = QComboBox()
        ch1_combo.addItems(["1V/div", "2V/div", "5V/div"])
        ch1_combo.setCurrentText("1V/div")
        
        ch1_layout.addWidget(ch1_check)
        ch1_layout.addWidget(ch1_label)
        ch1_layout.addWidget(ch1_combo)
        channel_layout.addLayout(ch1_layout)
        
        # 通道2
        ch2_layout = QHBoxLayout()
        ch2_check = QCheckBox("启用")
        ch2_check.setChecked(True)
        ch2_label = QLabel("通道2")
        ch2_combo = QComboBox()
        ch2_combo.addItems(["1V/div", "2V/div", "5V/div"])
        ch2_combo.setCurrentText("2V/div")
        
        ch2_layout.addWidget(ch2_check)
        ch2_layout.addWidget(ch2_label)
        ch2_layout.addWidget(ch2_combo)
        channel_layout.addLayout(ch2_layout)
        
        # 时间基准
        time_layout = QHBoxLayout()
        time_label = QLabel("时间基准")
        time_combo = QComboBox()
        time_combo.addItems(["1ms/div", "2ms/div", "5ms/div", "10ms/div"])
        time_combo.setCurrentText("1ms/div")
        time_layout.addWidget(time_label)
        time_layout.addWidget(time_combo)
        channel_layout.addLayout(time_layout)
        
        # 触发
        trigger_layout = QHBoxLayout()
        trigger_label = QLabel("触发")
        trigger_combo = QComboBox()
        trigger_combo.addItems(["通道1", "通道2"])
        trigger_combo.setCurrentText("通道1")
        trigger_layout.addWidget(trigger_label)
        trigger_layout.addWidget(trigger_combo)
        channel_layout.addLayout(trigger_layout)
        
        channel_group.setLayout(channel_layout)
        layout.addWidget(channel_group)
        
        # 运行控制
        run_layout = QHBoxLayout()
        self.run_btn = QPushButton("运行")
        self.run_btn.setStyleSheet("background-color: #0078d7; border: none; padding: 8px;")
        self.single_btn = QPushButton("单次")
        self.single_btn.setStyleSheet("background-color: #2d3b55; border: none; padding: 8px;")
        self.auto_btn = QPushButton("自动缩放")
        self.auto_btn.setStyleSheet("background-color: #2d3b55; border: none; padding: 8px;")
        
        run_layout.addWidget(self.run_btn)
        run_layout.addWidget(self.single_btn)
        run_layout.addWidget(self.auto_btn)
        layout.addLayout(run_layout)
        
        # 测量结果
        measure_group = QGroupBox("测量")
        measure_layout = QVBoxLayout()
        
        freq_layout = QHBoxLayout()
        freq_label = QLabel("频率")
        freq_value = QLabel("1.00 kHz")
        freq_value.setStyleSheet("color: #00ff00;")
        freq_layout.addWidget(freq_label)
        freq_layout.addStretch()
        freq_layout.addWidget(freq_value)
        measure_layout.addLayout(freq_layout)
        
        peak_layout = QHBoxLayout()
        peak_label = QLabel("峰峰值")
        peak_value = QLabel("5.01 V")
        peak_value.setStyleSheet("color: #00ff00;")
        peak_layout.addWidget(peak_label)
        peak_layout.addStretch()
        peak_layout.addWidget(peak_value)
        measure_layout.addLayout(peak_layout)
        
        rms_layout = QHBoxLayout()
        rms_label = QLabel("RMS")
        rms_value = QLabel("2.50 V")
        rms_value.setStyleSheet("color: #00ff00;")
        rms_layout.addWidget(rms_label)
        rms_layout.addStretch()
        rms_layout.addWidget(rms_value)
        measure_layout.addLayout(rms_layout)
        
        duty_layout = QHBoxLayout()
        duty_label = QLabel("占空比")
        duty_value = QLabel("49.5 %")
        duty_value.setStyleSheet("color: #00ff00;")
        duty_layout.addWidget(duty_label)
        duty_layout.addStretch()
        duty_layout.addWidget(duty_value)
        measure_layout.addLayout(duty_layout)
        
        measure_group.setLayout(measure_layout)
        layout.addWidget(measure_group)
    
    def create_spectrum_controls(self, layout):
        # 频率范围
        freq_group = QGroupBox("频率范围 (0-25MHz)")
        freq_layout = QGridLayout()
        
        freq_layout.addWidget(QLabel("起始"), 0, 0)
        freq_layout.addWidget(QLabel("终止"), 0, 2)
        
        start_edit = QLineEdit("0")
        start_unit = QComboBox()
        start_unit.addItems(["kHz", "MHz"])
        start_unit.setCurrentText("kHz")
        
        end_edit = QLineEdit("25")
        end_unit = QComboBox()
        end_unit.addItems(["kHz", "MHz"])
        end_unit.setCurrentText("MHz")
        
        freq_layout.addWidget(start_edit, 1, 0)
        freq_layout.addWidget(start_unit, 1, 1)
        freq_layout.addWidget(end_edit, 1, 2)
        freq_layout.addWidget(end_unit, 1, 3)
        
        freq_group.setLayout(freq_layout)
        layout.addWidget(freq_group)
        
        # 分辨率带宽
        rbw_layout = QHBoxLayout()
        rbw_label = QLabel("分辨率带宽")
        rbw_combo = QComboBox()
        rbw_combo.addItems(["10kHz", "100kHz", "1MHz"])
        rbw_combo.setCurrentText("100kHz")
        
        rbw_layout.addWidget(rbw_label)
        rbw_layout.addWidget(rbw_combo)
        layout.addLayout(rbw_layout)
        
        # 参考电平
        ref_layout = QHBoxLayout()
        ref_label = QLabel("参考电平")
        ref_value = QLabel("-37 dBm")
        
        ref_slider = QSlider(Qt.Horizontal)
        ref_slider.setMinimum(-100)
        ref_slider.setMaximum(0)
        ref_slider.setValue(-37)
        
        ref_layout.addWidget(ref_label)
        ref_layout.addWidget(ref_slider)
        ref_layout.addWidget(ref_value)
        layout.addLayout(ref_layout)
        
        # 平均次数
        avg_layout = QHBoxLayout()
        avg_label = QLabel("平均次数")
        avg_combo = QComboBox()
        avg_combo.addItems(["1次", "2次", "4次", "8次", "16次"])
        avg_combo.setCurrentText("8次")
        
        avg_layout.addWidget(avg_label)
        avg_layout.addWidget(avg_combo)
        layout.addLayout(avg_layout)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        stop_btn = QPushButton("停止")
        stop_btn.setStyleSheet("background-color: #0078d7; border: none; padding: 8px;")
        mark_btn = QPushButton("标记")
        mark_btn.setStyleSheet("background-color: #2d3b55; border: none; padding: 8px;")
        
        btn_layout.addWidget(stop_btn)
        btn_layout.addWidget(mark_btn)
        layout.addLayout(btn_layout)
        
        # 测量结果
        measure_group = QGroupBox("测量")
        measure_layout = QVBoxLayout()
        
        freq_layout = QHBoxLayout()
        freq_label = QLabel("频率")
        freq_value = QLabel("1.00 kHz")
        freq_value.setStyleSheet("color: #00ff00;")
        freq_layout.addWidget(freq_label)
        freq_layout.addStretch()
        freq_layout.addWidget(freq_value)
        measure_layout.addLayout(freq_layout)
        
        peak_layout = QHBoxLayout()
        peak_label = QLabel("峰峰值")
        peak_value = QLabel("2.01 V")
        peak_value.setStyleSheet("color: #00ff00;")
        peak_layout.addWidget(peak_label)
        peak_layout.addStretch()
        peak_layout.addWidget(peak_value)
        measure_layout.addLayout(peak_layout)
        
        rms_layout = QHBoxLayout()
        rms_label = QLabel("RMS")
        rms_value = QLabel("0.71 V")
        rms_value.setStyleSheet("color: #00ff00;")
        rms_layout.addWidget(rms_label)
        rms_layout.addStretch()
        rms_layout.addWidget(rms_value)
        measure_layout.addLayout(rms_layout)
        
        duty_layout = QHBoxLayout()
        duty_label = QLabel("占空比")
        duty_value = QLabel("50.3 %")
        duty_value.setStyleSheet("color: #00ff00;")
        duty_layout.addWidget(duty_label)
        duty_layout.addStretch()
        duty_layout.addWidget(duty_value)
        measure_layout.addLayout(duty_layout)
        
        measure_group.setLayout(measure_layout)
        layout.addWidget(measure_group)
        
        # 峰值信息
        peak_info_layout = QHBoxLayout()
        
        peak_freq_layout = QVBoxLayout()
        peak_freq_label = QLabel("峰值频率:")
        peak_freq_value = QLabel("450.00 kHz")
        peak_freq_value.setStyleSheet("color: #00ff00;")
        
        peak_freq_layout.addWidget(peak_freq_label)
        peak_freq_layout.addWidget(peak_freq_value)
        
        peak_power_layout = QVBoxLayout()
        peak_power_label = QLabel("峰值功率:")
        peak_power_value = QLabel("-9.5 dBm")
        peak_power_value.setStyleSheet("color: #00ff00;")
        
        peak_power_layout.addWidget(peak_power_label)
        peak_power_layout.addWidget(peak_power_value)
        
        peak_info_layout.addLayout(peak_freq_layout)
        peak_info_layout.addStretch()
        peak_info_layout.addLayout(peak_power_layout)
        
        layout.addLayout(peak_info_layout)
    
    def create_signal_generator_controls(self, layout):
        # 波形类型
        waveform_layout = QHBoxLayout()
        waveform_layout.setSpacing(10)
        
        sine_btn = QPushButton("正弦波")
        sine_btn.setStyleSheet("background-color: #2d3b55; border: none; padding: 8px;")
        
        square_btn = QPushButton("方波")
        square_btn.setStyleSheet("background-color: #0078d7; border: none; padding: 8px;")
        
        triangle_btn = QPushButton("三角波")
        triangle_btn.setStyleSheet("background-color: #2d3b55; border: none; padding: 8px;")
        
        sawtooth_btn = QPushButton("锯齿波")
        sawtooth_btn.setStyleSheet("background-color: #2d3b55; border: none; padding: 8px;")
        
        waveform_layout.addWidget(sine_btn)
        waveform_layout.addWidget(square_btn)
        waveform_layout.addWidget(triangle_btn)
        waveform_layout.addWidget(sawtooth_btn)
        layout.addLayout(waveform_layout)
        
        # 频率控制
        freq_layout = QVBoxLayout()
        freq_label = QLabel("频率(最高10MHz)")
        
        freq_edit = QLineEdit("1")
        freq_unit = QComboBox()
        freq_unit.addItems(["Hz", "kHz", "MHz"])
        freq_unit.setCurrentText("kHz")
        
        freq_hbox = QHBoxLayout()
        freq_hbox.addWidget(freq_edit)
        freq_hbox.addWidget(freq_unit)
        
        freq_layout.addWidget(freq_label)
        freq_layout.addLayout(freq_hbox)
        layout.addLayout(freq_layout)
        
        # 幅度控制
        amp_layout = QVBoxLayout()
        amp_label = QLabel("幅度(最大8Vpp)")
        
        amp_slider = QSlider(Qt.Horizontal)
        amp_slider.setMinimum(0)
        amp_slider.setMaximum(80)
        amp_slider.setValue(10)  # 1.0V
        
        amp_value = QLabel("1.0V")
        
        amp_hbox = QHBoxLayout()
        amp_hbox.addWidget(amp_slider)
        amp_hbox.addWidget(amp_value)
        
        amp_layout.addWidget(amp_label)
        amp_layout.addLayout(amp_hbox)
        layout.addLayout(amp_layout)
        
        # 直流偏移
        offset_layout = QVBoxLayout()
        offset_label = QLabel("直流偏移(-4V+4V)")
        
        offset_slider = QSlider(Qt.Horizontal)
        offset_slider.setMinimum(-40)
        offset_slider.setMaximum(40)
        offset_slider.setValue(0)
        
        offset_value = QLabel("0.0V")
        
        offset_hbox = QHBoxLayout()
        offset_hbox.addWidget(offset_slider)
        offset_hbox.addWidget(offset_value)
        
        offset_layout.addWidget(offset_label)
        offset_layout.addLayout(offset_hbox)
        layout.addLayout(offset_layout)
        
        # 启动输出按钮
        output_btn = QPushButton("启动输出")
        output_btn.setStyleSheet("background-color: #0078d7; border: none; padding: 10px;")
        layout.addWidget(output_btn)
        
        # 测量结果
        measure_group = QGroupBox("测量")
        measure_layout = QVBoxLayout()
        
        freq_layout = QHBoxLayout()
        freq_label = QLabel("频率")
        freq_value = QLabel("1.00 kHz")
        freq_value.setStyleSheet("color: #00ff00;")
        freq_layout.addWidget(freq_label)
        freq_layout.addStretch()
        freq_layout.addWidget(freq_value)
        measure_layout.addLayout(freq_layout)
        
        peak_layout = QHBoxLayout()
        peak_label = QLabel("峰值")
        peak_value = QLabel("2.01 V")
        peak_value.setStyleSheet("color: #00ff00;")
        peak_layout.addWidget(peak_label)
        peak_layout.addStretch()
        peak_layout.addWidget(peak_value)
        measure_layout.addLayout(peak_layout)
        
        rms_layout = QHBoxLayout()
        rms_label = QLabel("RMS")
        rms_value = QLabel("1.00 V")
        rms_value.setStyleSheet("color: #00ff00;")
        rms_layout.addWidget(rms_label)
        rms_layout.addStretch()
        rms_layout.addWidget(rms_value)
        measure_layout.addLayout(rms_layout)
        
        duty_layout = QHBoxLayout()
        duty_label = QLabel("占空比")
        duty_value = QLabel("49.5 %")
        duty_value.setStyleSheet("color: #00ff00;")
        duty_layout.addWidget(duty_label)
        duty_layout.addStretch()
        duty_layout.addWidget(duty_value)
        measure_layout.addLayout(duty_layout)
        
        measure_group.setLayout(measure_layout)
        layout.addWidget(measure_group)
    
    def create_pwm_controls(self, layout):
        # 频率控制
        freq_layout = QVBoxLayout()
        freq_label = QLabel("频率(最高1MHz)")
        
        freq_edit = QLineEdit("1")
        freq_unit = QComboBox()
        freq_unit.addItems(["Hz", "kHz", "MHz"])
        freq_unit.setCurrentText("kHz")
        
        freq_hbox = QHBoxLayout()
        freq_hbox.addWidget(freq_edit)
        freq_hbox.addWidget(freq_unit)
        
        freq_layout.addWidget(freq_label)
        freq_layout.addLayout(freq_hbox)
        layout.addLayout(freq_layout)
        
        # 幅度 (固定3.3V)
        amp_layout = QVBoxLayout()
        amp_label = QLabel("幅度")
        amp_value = QLabel("3.3V (固定)")
        
        amp_layout.addWidget(amp_label)
        amp_layout.addWidget(amp_value)
        layout.addLayout(amp_layout)
        
        # 占空比
        duty_layout = QVBoxLayout()
        duty_label = QLabel("占空比")
        
        duty_slider = QSlider(Qt.Horizontal)
        duty_slider.setMinimum(0)
        duty_slider.setMaximum(100)
        duty_slider.setValue(15)
        
        duty_value = QLabel("15%")
        
        duty_hbox = QHBoxLayout()
        duty_hbox.addWidget(duty_slider)
        duty_hbox.addWidget(duty_value)
        
        duty_layout.addWidget(duty_label)
        duty_layout.addLayout(duty_hbox)
        layout.addLayout(duty_layout)
        
        # 启动输出按钮
        output_btn = QPushButton("启动输出")
        output_btn.setStyleSheet("background-color: #0078d7; border: none; padding: 10px;")
        layout.addWidget(output_btn)
        
        # 测量结果
        measure_group = QGroupBox("测量")
        measure_layout = QVBoxLayout()
        
        freq_layout = QHBoxLayout()
        freq_label = QLabel("频率")
        freq_value = QLabel("1.00 kHz")
        freq_value.setStyleSheet("color: #00ff00;")
        freq_layout.addWidget(freq_label)
        freq_layout.addStretch()
        freq_layout.addWidget(freq_value)
        measure_layout.addLayout(freq_layout)
        
        peak_layout = QHBoxLayout()
        peak_label = QLabel("峰峰值")
        peak_value = QLabel("2.01 V")
        peak_value.setStyleSheet("color: #00ff00;")
        peak_layout.addWidget(peak_label)
        peak_layout.addStretch()
        peak_layout.addWidget(peak_value)
        measure_layout.addLayout(peak_layout)
        
        rms_layout = QHBoxLayout()
        rms_label = QLabel("RMS")
        rms_value = QLabel("1.00 V")
        rms_value.setStyleSheet("color: #00ff00;")
        rms_layout.addWidget(rms_label)
        rms_layout.addStretch()
        rms_layout.addWidget(rms_value)
        measure_layout.addLayout(rms_layout)
        
        duty_layout = QHBoxLayout()
        duty_label = QLabel("占空比")
        duty_value = QLabel("49.5 %")
        duty_value.setStyleSheet("color: #00ff00;")
        duty_layout.addWidget(duty_label)
        duty_layout.addStretch()
        duty_layout.addWidget(duty_value)
        measure_layout.addLayout(duty_layout)
        
        measure_group.setLayout(measure_layout)
        layout.addWidget(measure_group)
    
    def create_logic_analyzer_controls(self, layout):
        # 通道选择
        channel_group = QGroupBox("通道选择")
        channel_layout = QHBoxLayout()
        channel_layout.setSpacing(10)
        
        channels = ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]
        for ch in channels:
            ch_check = QCheckBox(ch)
            ch_check.setChecked(True)
            channel_layout.addWidget(ch_check)
        
        channel_group.setLayout(channel_layout)
        layout.addWidget(channel_group)
        
        # 采样率
        sample_layout = QVBoxLayout()
        sample_label = QLabel("采样率")
        
        sample_combo = QComboBox()
        sample_combo.addItems(["1 MHz", "10 MHz", "25 MHz", "50 MHz"])
        sample_combo.setCurrentText("25 MHz")
        
        sample_layout.addWidget(sample_label)
        sample_layout.addWidget(sample_combo)
        layout.addLayout(sample_layout)
        
        # 采样深度
        depth_layout = QVBoxLayout()
        depth_label = QLabel("采样深度")
        
        depth_combo = QComboBox()
        depth_combo.addItems(["1K", "2K", "4K", "8K", "16K"])
        depth_combo.setCurrentText("8K")
        
        depth_layout.addWidget(depth_label)
        depth_layout.addWidget(depth_combo)
        layout.addLayout(depth_layout)
        
        # 触发模式
        trigger_layout = QVBoxLayout()
        trigger_label = QLabel("触发模式")
        
        trigger_combo = QComboBox()
        trigger_combo.addItems(["边沿触发", "电平触发", "脉冲触发"])
        trigger_combo.setCurrentText("边沿触发")
        
        trigger_layout.addWidget(trigger_label)
        trigger_layout.addWidget(trigger_combo)
        layout.addLayout(trigger_layout)
        
        # 运行按钮
        btn_layout = QHBoxLayout()
        run_btn = QPushButton("运行")
        run_btn.setStyleSheet("background-color: #0078d7; border: none; padding: 8px;")
        
        single_btn = QPushButton("单次")
        single_btn.setStyleSheet("background-color: #2d3b55; border: none; padding: 8px;")
        
        btn_layout.addWidget(run_btn)
        btn_layout.addWidget(single_btn)
        layout.addLayout(btn_layout)
    
    def create_power_supply_controls(self, layout):
        # 通道1控制
        ch1_group = QGroupBox("通道1")
        ch1_layout = QVBoxLayout()
        
        # 电压设置
        ch1_volt_layout = QVBoxLayout()
        ch1_volt_label = QLabel("电压(V)")
        
        ch1_volt_slider = QSlider(Qt.Horizontal)
        ch1_volt_slider.setMinimum(0)
        ch1_volt_slider.setMaximum(120)
        ch1_volt_slider.setValue(13)  # 1.3V
        
        ch1_volt_value = QLabel("1.30 V")
        
        ch1_volt_hbox = QHBoxLayout()
        ch1_volt_hbox.addWidget(ch1_volt_slider)
        ch1_volt_hbox.addWidget(ch1_volt_value)
        
        ch1_volt_layout.addWidget(ch1_volt_label)
        ch1_volt_layout.addLayout(ch1_volt_hbox)
        
        # 电流设置
        ch1_curr_layout = QVBoxLayout()
        ch1_curr_label = QLabel("电流限制(A)")
        
        ch1_curr_slider = QSlider(Qt.Horizontal)
        ch1_curr_slider.setMinimum(0)
        ch1_curr_slider.setMaximum(30)
        ch1_curr_slider.setValue(7)  # 0.7A
        
        ch1_curr_value = QLabel("0.70 A")
        
        ch1_curr_hbox = QHBoxLayout()
        ch1_curr_hbox.addWidget(ch1_curr_slider)
        ch1_curr_hbox.addWidget(ch1_curr_value)
        
        ch1_curr_layout.addWidget(ch1_curr_label)
        ch1_curr_layout.addLayout(ch1_curr_hbox)
        
        ch1_layout.addLayout(ch1_volt_layout)
        ch1_layout.addLayout(ch1_curr_layout)
        
        # 启用复选框
        ch1_enable = QCheckBox("启用通道1")
        ch1_layout.addWidget(ch1_enable)
        
        ch1_group.setLayout(ch1_layout)
        layout.addWidget(ch1_group)
        
        # 通道2控制
        ch2_group = QGroupBox("通道2")
        ch2_layout = QVBoxLayout()
        
        # 电压设置
        ch2_volt_layout = QVBoxLayout()
        ch2_volt_label = QLabel("电压(V)")
        
        ch2_volt_slider = QSlider(Qt.Horizontal)
        ch2_volt_slider.setMinimum(0)
        ch2_volt_slider.setMaximum(120)
        ch2_volt_slider.setValue(81)  # 8.1V
        
        ch2_volt_value = QLabel("8.10 V")
        
        ch2_volt_hbox = QHBoxLayout()
        ch2_volt_hbox.addWidget(ch2_volt_slider)
        ch2_volt_hbox.addWidget(ch2_volt_value)
        
        ch2_volt_layout.addWidget(ch2_volt_label)
        ch2_volt_layout.addLayout(ch2_volt_hbox)
        
        # 电流设置
        ch2_curr_layout = QVBoxLayout()
        ch2_curr_label = QLabel("电流限制(A)")
        
        ch2_curr_slider = QSlider(Qt.Horizontal)
        ch2_curr_slider.setMinimum(0)
        ch2_curr_slider.setMaximum(30)
        ch2_curr_slider.setValue(7)  # 0.7A
        
        ch2_curr_value = QLabel("0.70 A")
        
        ch2_curr_hbox = QHBoxLayout()
        ch2_curr_hbox.addWidget(ch2_curr_slider)
        ch2_curr_hbox.addWidget(ch2_curr_value)
        
        ch2_curr_layout.addWidget(ch2_curr_label)
        ch2_curr_layout.addLayout(ch2_curr_hbox)
        
        ch2_layout.addLayout(ch2_volt_layout)
        ch2_layout.addLayout(ch2_curr_layout)
        
        # 启用复选框
        ch2_enable = QCheckBox("启用通道2")
        ch2_layout.addWidget(ch2_enable)
        
        ch2_group.setLayout(ch2_layout)
        layout.addWidget(ch2_group)
        
        # 电压预设按钮
        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(5)
        
        presets = ["1V", "3V", "5V", "9V", "12V"]
        for preset in presets:
            btn = QPushButton(preset)
            btn.setStyleSheet("background-color: #2d3b55; border: none; padding: 5px;")
            preset_layout.addWidget(btn)
        
        layout.addLayout(preset_layout)
        
        # 输出按钮
        output_btn = QPushButton("开启")
        output_btn.setStyleSheet("background-color: #0078d7; border: none; padding: 10px;")
        layout.addWidget(output_btn)

# 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("ZooLark View")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #0a1428;")
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标题栏
        title_bar = QWidget()
        title_bar.setFixedHeight(50)
        title_bar.setStyleSheet("background-color: #162033;")
        
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 15, 0)
        
        # Logo和标题
        logo_label = QLabel("ZooLark View")
        logo_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #00ffcc;")
        title_layout.addWidget(logo_label)
        
        # 标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabBar::tab {
                background-color: #1a2436;
                color: #ffffff;
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #0078d7;
            }
            QTabWidget::pane {
                border: 1px solid #2d3b55;
                background-color: #1a2436;
            }
        """)
        
        # 添加标签页
        self.create_oscilloscope_tab()
        self.create_spectrum_tab()
        self.create_signal_generator_tab()
        self.create_pwm_generator_tab()
        self.create_logic_analyzer_tab()
        self.create_power_supply_tab()
        
        # 右侧按钮
        connect_btn = QPushButton("连接设备")
        connect_btn.setStyleSheet("background-color: #0078d7; border: none; padding: 8px 15px;")
        title_layout.addStretch()
        title_layout.addWidget(connect_btn)
        
        main_layout.addWidget(title_bar)
        main_layout.addWidget(self.tab_widget)
        
        # 状态栏信息
        status_layout = QHBoxLayout()
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        status_info = [
            ("采样率:", "45.00 MS/s"),
            ("存储深度:", "1024 samples"),
            ("模拟带宽:", "5 MHz"),
            ("连接状态:", "未连接")
        ]
        
        for label, value in status_info:
            status_label = QLabel(f"{label} {value}")
            status_label.setStyleSheet("color: #8899aa;")
            status_layout.addWidget(status_label)
            status_layout.addSpacing(20)
        
        status_widget = QWidget()
        status_widget.setStyleSheet("background-color: #162033;")
        status_widget.setLayout(status_layout)
        status_widget.setFixedHeight(30)
        
        main_layout.addWidget(status_widget)
    
    def create_oscilloscope_tab(self):
        # 创建示波器标签页
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        
        # 左侧控制面板
        control_panel = ControlPanel(panel_type="oscilloscope")
        
        # 右侧波形显示
        waveform_widget = WaveformWidget(waveform_type="oscilloscope")
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(waveform_widget)
        splitter.setSizes([300, 900])
        
        tab_layout.addWidget(splitter)
        self.tab_widget.addTab(tab_widget, "示波器")
    
    def create_spectrum_tab(self):
        # 创建频谱分析标签页
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        
        # 左侧控制面板
        control_panel = ControlPanel(panel_type="spectrum")
        
        # 右侧波形显示
        waveform_widget = WaveformWidget(waveform_type="spectrum")
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(waveform_widget)
        splitter.setSizes([300, 900])
        
        tab_layout.addWidget(splitter)
        self.tab_widget.addTab(tab_widget, "频谱分析")
    
    def create_signal_generator_tab(self):
        # 创建信号发生器标签页
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        
        # 左侧控制面板
        control_panel = ControlPanel(panel_type="signal_generator")
        
        # 右侧波形显示
        waveform_widget = WaveformWidget(waveform_type="signal_generator")
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(waveform_widget)
        splitter.setSizes([300, 900])
        
        tab_layout.addWidget(splitter)
        self.tab_widget.addTab(tab_widget, "信号发生器")
    
    def create_pwm_generator_tab(self):
        # 创建PWM发生器标签页
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        
        # 左侧控制面板
        control_panel = ControlPanel(panel_type="pwm_generator")
        
        # 右侧波形显示
        waveform_widget = WaveformWidget(waveform_type="pwm_generator")
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(waveform_widget)
        splitter.setSizes([300, 900])
        
        tab_layout.addWidget(splitter)
        self.tab_widget.addTab(tab_widget, "PWM发生器")
    
    def create_logic_analyzer_tab(self):
        # 创建逻辑分析仪标签页
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        
        # 左侧控制面板
        control_panel = ControlPanel(panel_type="logic_analyzer")
        
        # 右侧波形显示
        waveform_widget = WaveformWidget(waveform_type="logic_analyzer")
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(waveform_widget)
        splitter.setSizes([300, 900])
        
        tab_layout.addWidget(splitter)
        self.tab_widget.addTab(tab_widget, "逻辑分析仪")
    
    def create_power_supply_tab(self):
        # 创建电源标签页
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        
        # 左侧控制面板
        control_panel = ControlPanel(panel_type="power_supply")
        
        # 右侧电源输出显示
        power_display = QWidget()
        power_display.setStyleSheet("background-color: #1a2436;")
        power_layout = QVBoxLayout(power_display)
        
        # 创建两个通道的显示区域
        channels_layout = QHBoxLayout()
        
        # 通道1显示
        ch1_display = QWidget()
        ch1_display.setStyleSheet("background-color: #2d3b55; border-radius: 5px;")
        ch1_layout = QVBoxLayout(ch1_display)
        
        ch1_title = QLabel("通道1")
        ch1_title.setStyleSheet("font-weight: bold; padding: 5px;")
        
        # 测量值显示
        ch1_values = QGridLayout()
        ch1_values.addWidget(QLabel("设定电压"), 0, 0)
        ch1_values.addWidget(QLabel("设定电流"), 0, 1)
        ch1_values.addWidget(QLabel("输出电压"), 1, 0)
        ch1_values.addWidget(QLabel("输出电流"), 1, 1)
        
        # 值标签
        ch1_values.addWidget(QLabel("1.30 V"), 0, 2)
        ch1_values.addWidget(QLabel("0.000 A"), 1, 2)
        ch1_values.addWidget(QLabel("0.000 A"), 0, 3)
        ch1_values.addWidget(QLabel("0.000 W"), 1, 3)
        
        # 波形区域 (黑色)
        ch1_waveform = QWidget()
        ch1_waveform.setStyleSheet("background-color: #0a1428; border-radius: 3px; margin: 5px;")
        
        ch1_layout.addWidget(ch1_title)
        ch1_layout.addLayout(ch1_values)
        ch1_layout.addWidget(ch1_waveform)
        
        # 通道2显示
        ch2_display = QWidget()
        ch2_display.setStyleSheet("background-color: #2d3b55; border-radius: 5px;")
        ch2_layout = QVBoxLayout(ch2_display)
        
        ch2_title = QLabel("通道2")
        ch2_title.setStyleSheet("font-weight: bold; padding: 5px;")
        
        # 测量值显示
        ch2_values = QGridLayout()
        ch2_values.addWidget(QLabel("设定电压"), 0, 0)
        ch2_values.addWidget(QLabel("设定电流"), 0, 1)
        ch2_values.addWidget(QLabel("输出电压"), 1, 0)
        ch2_values.addWidget(QLabel("输出电流"), 1, 1)
        
        # 值标签
        ch2_values.addWidget(QLabel("8.10 V"), 0, 2)
        ch2_values.addWidget(QLabel("0.000 A"), 1, 2)
        ch2_values.addWidget(QLabel("0.000 A"), 0, 3)
        ch2_values.addWidget(QLabel("0.000 W"), 1, 3)
        
        # 波形区域 (黑色)
        ch2_waveform = QWidget()
        ch2_waveform.setStyleSheet("background-color: #0a1428; border-radius: 3px; margin: 5px;")
        
        ch2_layout.addWidget(ch2_title)
        ch2_layout.addLayout(ch2_values)
        ch2_layout.addWidget(ch2_waveform)
        
        channels_layout.addWidget(ch1_display)
        channels_layout.addWidget(ch2_display)
        
        power_layout.addLayout(channels_layout)
        power_layout.addStretch()
        
        # 分割器
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(control_panel)
        splitter.addWidget(power_display)
        splitter.setSizes([300, 900])
        
        tab_layout.addWidget(splitter)
        self.tab_widget.addTab(tab_widget, "电源")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle("Fusion")
    
    # 设置全局字体
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())