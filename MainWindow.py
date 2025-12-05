from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys
import os
from PyQt5 import uic
from dialog_setting import ConnectDialog
from receiveThreads import UdpReceiverThread
import socket
import struct
import resources
from wave_painter import wavepainter
import pyqtgraph as pg
from UARTThread import UART_Thread
from fft_thread import FFTThread
import numpy as np
from scipy.signal import find_peaks
from logic_analyzer import LogicAnalyzerWidget
class mainwindow(QMainWindow):
    def __init__(self):
        super().__init__()
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ui_path = os.path.join(base, 'MainWindow.ui')
        self.ui = uic.loadUi(ui_path, self)
        self.setWindowTitle('多功能协议调试器')
        # self.ui.waveplot.setDownsampling(mode='peak')  # 自动下采样
        # self.ui.waveplot.setClipToView(True)  # 只渲染可见区域
        #添加控件及其参数
        self.logic_analyzer = LogicAnalyzerWidget(parent=self)
        #self.logic_analyzer.start(1000)
        self.ui.gridLayout_10.addWidget(self.logic_analyzer, 1, 2)
        self.wp = wavepainter(parent=self)  
        self.ui.gridLayout_6.addWidget(self.wp, 1, 3)
        self.PWM_VIEW=pg.GraphicsLayoutWidget(parent=self)
        self.PWM_VIEW.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.vb1 = self.PWM_VIEW.addViewBox(row=0, col=0)
        self.vb2 = self.PWM_VIEW.addViewBox(row=1, col=0)
        self.vb3 = self.PWM_VIEW.addViewBox(row=2, col=0)
        self.vb4 = self.PWM_VIEW.addViewBox(row=3, col=0)              
        self.ui.gridLayout_15.addWidget(self.PWM_VIEW,1,2)
        self.vb1.setMouseEnabled(x=True, y=False)
        self.vb2.setMouseEnabled(x=True, y=False)
        self.vb3.setMouseEnabled(x=True, y=False)
        self.vb4.setMouseEnabled(x=True, y=False) 
        self.vb1.setBorder(color='#650098', width=2)
        self.vb1.setBorder(color='#650098', width=2) 
        self.vb2.setBorder(color='#650098', width=2) 
        self.vb3.setBorder(color='#650098', width=2) 
        self.vb4.setBorder(color='#650098', width=2) 
        self.movable_line = pg.InfiniteLine(
            angle=0,
            pos=5.5,
            pen=pg.mkPen(color=(170, 0, 255), width=3, style=Qt.DashLine),
            movable=True  # 允许拖拽
        )
        self.ui.waveplot.addItem(self.movable_line)
        self.line_timer = QTimer(self)
        self.plot_Spectrum = pg.GraphicsLayoutWidget(parent=self)
        self.ui.gridLayout_3.addWidget(self.plot_Spectrum, 2, 2, 3, 5)
        self.plot_Spectrum.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_Spectrum.setVisible(False)
        self.pb1 = self.plot_Spectrum.addViewBox(row=0, col=0)
        self.pb1.setMouseEnabled(x=True, y=False)
        self.pb1.setBorder(color='#650098', width=2)
        self.pb2 = self.plot_Spectrum.addViewBox(row=1, col=0)
        self.pb2.setMouseEnabled(x=True, y=False)
        self.pb2.setBorder(color='#650098', width=2)
        # 频谱绘图项（分别用于通道1/通道2）
        self.spec_curve1 = pg.PlotCurveItem(pen=pg.mkPen((0,200,0), width=1), fillLevel=0, brush=(0,200,0,60))
        self.spec_curve2 = pg.PlotCurveItem(pen=pg.mkPen((200,50,50), width=1), fillLevel=0, brush=(200,50,50,60))
        self.pb1.addItem(self.spec_curve1)
        self.pb2.addItem(self.spec_curve2)
        # 用于存放谐波 TextItem，便于后续清理
        self.harmonic_labels1 = []
        self.harmonic_labels2 = []
        # 可配置：标签垂直偏移占谱峰高度的比例
        self.harmonic_label_offset = 0.05
        # 接口配置信息
        self.serial_config=None
        self.net_config=None
        self.usb_config=None
        #示波器配置
        self.channel_config={"channels": [False, False]}  
        self.trig_config={"channel":0,"edge":0,"voltage":0}
        self.ch1_osc_measure_result={"ch1":{"vpp":0,"fre":0,"bio":0},"ch2":{"vpp":0,"fre":0,"bio":0}}
        self.ui.ch1_osc_fre_num_label.setText(self.ch1_osc_measure_result["ch1"]["fre"].__str__())
        self.ui.ch1_osc_vpp_num_label.setText(self.ch1_osc_measure_result["ch1"]["vpp"].__str__())
        self.ui.ch1_osc_bio_num_label.setText(self.ch1_osc_measure_result["ch1"]["bio"].__str__())
        self.ui.ch2_osc_fre_num_label.setText(self.ch1_osc_measure_result["ch2"]["fre"].__str__())
        self.ui.ch2_osc_vpp_num_label.setText(self.ch1_osc_measure_result["ch2"]["vpp"].__str__())
        self.ui.ch2_osc_bio_num_label.setText(self.ch1_osc_measure_result["ch2"]["bio"].__str__())

        #数字信号测量
        #self.digital_measure_result={"fre":0,"duty":0,"ht":0,"lt":0}
        self.logic_channel_visible=[False,False,False,False,False,False,False,False]
        #UDP线程 串口线程
        self.receive_thread=None 
        self.uart_thread=None
        self.fft_thread = FFTThread()
        #pwm配置
        self.pwm_config=[
            {"channel":False,"frequency":0,"duty":50,"phase":0},
            {"channel":False,"frequency":0,"duty":50,"phase":0},
            {"channel":False,"frequency":0,"duty":50,"phase":0},
            {"channel":False,"frequency":0,"duty":50,"phase":0}
        ]
        self.pwm_display_config = {
            'frequency': 100000,
            'duty': 50,
            'phases': [0, 0, 0, 0],
            'visible': [False, False, False, False]
        }
        self._pwm_curves = []
        # 示波器绘图相关
        #self.plot_data = []  # 存储绘图数据的列表
        self.ch1_plot_curve_real = self.ui.waveplot.plot()# 获取 PlotWidget 的绘图主体曲线对象
        self.ch1_plot_curve_glow = self.ui.waveplot.plot()# 获取 PlotWidget 的绘图发光曲线对象
        self.ch2_plot_curve_real = self.ui.waveplot.plot()# 获取 PlotWidget 的绘图主体曲线对象
        self.ch2_plot_curve_glow = self.ui.waveplot.plot()# 获取 PlotWidget 的绘图发光曲线对象      
        self.ui.waveplot.setBackground('k')
        self.ui.waveplot.showGrid(x=True, y=True, alpha=1)
        self.ui.waveplot.setLabel('left', '幅度', units='V')
        self.ui.waveplot.setLabel('bottom', '时间', units='s')
        self.ui.waveplot.setYRange(-7, 7)
        self.ui.waveplot.setXRange(-6, 6)
        self.view_box1=self.ui.waveplot.getViewBox()
        self.view_box1.setMouseEnabled(x=True, y=False)  # 只允许X轴交互
        self.VOL_RANGE_ch1=5
        self.VOL_RANGE_ch2=5
        self.ch1_plot_curve_glow.setVisible(False)
        self.ch2_plot_curve_glow.setVisible(False)
        self.ch1_plot_curve_real.setVisible(False)
        self.ch2_plot_curve_real.setVisible(False)
        #信号发生器配置
        self.wave_emiter={
            "type":0,
            "frequency":0,
            "scale":{"Hz":1,"kHz":1000,"MHz":1000000},
            "amplitude":0,
            "offset":0,
            "duty_cycle":50
        }
        # 连接信号与槽      
        self.ui.connect_btn.clicked.connect(self.connect_device)
        self.ui.open_btn.clicked.connect(self.start_or_stop__receive)
        self.ui.ch1_checkbox.stateChanged.connect(self.update_channel_config)
        self.ui.ch2_checkbox.stateChanged.connect(self.update_channel_config)
        self.ui.sine_btn.toggled.connect(lambda: self.wave_cs("sine"))
        self.ui.square_btn.toggled.connect(lambda: self.wave_cs("square"))
        self.ui.triangle_btn.toggled.connect(lambda: self.wave_cs("triangle"))
        self.ui.saw_btn.toggled.connect(lambda: self.wave_cs("saw"))
        self.ui.bread_btn.toggled.connect(lambda: self.wave_cs("bread"))
        self.ui.fre_edit.textChanged.connect(lambda:self.wave_parameter_change("num"))
        self.ui.fre_scale.currentIndexChanged.connect(lambda:self.wave_parameter_change("scale"))
        self.ui.emit_btn.clicked.connect(lambda: self.wave_cs("renyiboxing"))
        self.ui.emit_btn.clicked.connect(self.send_wave_command)
        self.ui.trans_btn.clicked.connect(self.get_send)
        self.line_timer.timeout.connect(self.on_line_moved)  # 定时调用目标函数
        self.line_timer.start(50)  # 启动定时器，间隔100ms（0.1秒）
        self.ui.output_btn.clicked.connect(lambda: (self.output_pwm()))
        self.ui.ch2_amp_dial.valueChanged.connect(self.ch2_amp_changed)
        self.ui.ch1_amp_dial.valueChanged.connect(self.ch1_amp_changed)
        self.ui.spectrum_btn.toggled.connect(self.spectrum_visible)
        self.ui.cum_output_btn.clicked.connect(self.cum_output)
        self.ui.ch1_checkbox.stateChanged.connect(lambda: self.set_wave_visible(1))
        self.ui.ch2_checkbox.stateChanged.connect(lambda: self.set_wave_visible(2))
        self.ui.sample_btn.clicked.connect(lambda: self.logic_analyzer.start(1))
        self.ui.sample_btn.clicked.connect(self.on_sample_clicked)
        self.ui.d1_checkBox.stateChanged.connect(lambda: self.set_digital_visible(1))
        self.ui.d2_checkBox.stateChanged.connect(lambda: self.set_digital_visible(2))
        self.ui.d3_checkBox.stateChanged.connect(lambda: self.set_digital_visible(3))
        self.ui.d4_checkBox.stateChanged.connect(lambda: self.set_digital_visible(4))
        self.ui.d5_checkBox.stateChanged.connect(lambda: self.set_digital_visible(5))
        self.ui.d6_checkBox.stateChanged.connect(lambda: self.set_digital_visible(6))
        self.ui.d7_checkBox.stateChanged.connect(lambda: self.set_digital_visible(7))
        self.ui.d8_checkBox.stateChanged.connect(lambda: self.set_digital_visible(8))
            
        # 用于峰点绘制的 ScatterItems（复用，避免重复创建）
        self._spec_peaks1 = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(255,200,0), pen=pg.mkPen(200,120,0))
        self._spec_peaks2 = pg.ScatterPlotItem(size=8, brush=pg.mkBrush(255,100,100), pen=pg.mkPen(160,30,30))
        self.pb1.addItem(self._spec_peaks1)
        self.pb2.addItem(self._spec_peaks2)
        # 复用峰值文本列表
        self._peak_texts1 = []
        self._peak_texts2 = []


    #不会用海象运算符的无奈之举  
    def ch2_amp_changed(self, vol):
        # separate slot to set current_amp (avoids assignment expression in lambda)
        self.VOL_RANGE_ch2 = vol
        print(f"接收线程 VOL_RANGE 更新为: {self.VOL_RANGE_ch2}")
    def ch1_amp_changed(self, vol):
        # separate slot to set current_amp (avoids assignment expression in lambda)
        self.VOL_RANGE_ch1 = vol
        print(f"接收线程 VOL_RANGE 更新为: {self.VOL_RANGE_ch1}")
    #打开设备，开启线程    
    def connect_device(self):
        dialog=ConnectDialog()
        if dialog.exec_() == QDialog.Accepted:
            # 配置部分
            self.serial_config=dialog.get_serial_config()
            self.net_config=dialog.get_net_config()
            if self.serial_config:
                 print("串口配置更新:", self.serial_config)
                 self.uart_thread=UART_Thread(self.serial_config)
                 self.uart_thread.open_port()
                 self.ui.connect_status_label.setText("已连接")
                 
            if self.net_config:
                 print("网络配置更新:", self.net_config)
                 self.receive_thread=UdpReceiverThread(self.net_config)
                 self.receive_thread.data_received.connect(self.update_osc_data)
                 self.receive_thread.start()   
                 self.ui.connect_status_label.setText("已连接")
                 self.fft_thread = FFTThread()
                 self.fft_thread.result_ready.connect(self.on_result)
                 self.fft_thread.error.connect(self.on_error )
                 self.fft_thread.start()
    #开始/停止接收数据              
    def start_or_stop__receive(self):
        if self.net_config:
            if not self.receive_thread.acquiring:
                 self.receive_thread.acquiring=True
                 self.receive_thread.start_acquisition(self.channel_config)#开始采集
                 self.ui.open_btn.setText("停止⏸")
                 print("开始接收数据")
            else:
                 self.receive_thread.acquiring=False
                 self.ui.open_btn.setText("开始▶")
                 self.receive_thread.stop_acquisition()#停止采集
                 print("停止接收数据")
        else:
            # 未配置连接警告
             QApplication.instance().setStyleSheet("QMessageBox * { color:red; }")
             QMessageBox.warning(self, "提示", "请先配置连接方式！") 
    #更新示波器通道配置         
    def update_channel_config(self):
        chans = [
             self.ui.ch1_checkbox.isChecked(),
             self.ui.ch2_checkbox.isChecked()
        ]
        self.channel_config = {
             "channels": chans
        }
        print("通道配置更新:", self.channel_config) 
                    
    @pyqtSlot(list)
    #更新绘图槽
    def update_osc_data(self, new_data,color_ch2=(0, 255, 255),color_ch1=(255, 255, 0),glow_width=8, main_width=2, glow_alpha=100):
        """
        更新绘图的槽函数。
        当接收到一帧完整的数据时，直接用它来更新整个波形图。
        """
        glow_pen_ch2 = pg.mkPen(
            color=(*color_ch2, glow_alpha),  # 带透明度的颜色
            width=glow_width,
            style=pg.QtCore.Qt.SolidLine
        )
        main_pen_ch2 = pg.mkPen(
            color=color_ch2,  # 实色
            width=main_width,
            style=pg.QtCore.Qt.SolidLine
        )
        glow_pen_ch1 = pg.mkPen(
            color=(*color_ch1, glow_alpha),  # 带透明度的颜色
            width=glow_width,
            style=pg.QtCore.Qt.SolidLine
        )
        main_pen_ch1 = pg.mkPen(
            color=color_ch1,  # 实色
            width=main_width,
            style=pg.QtCore.Qt.SolidLine
        )
        if new_data[0] == "wave":
            #print(f"接收到波形数据: {new_data}")
            self.ch2_plot_curve_real.setData([x * self.VOL_RANGE_ch2/5 for x in new_data[1]])
            self.ch2_plot_curve_real.setPen(main_pen_ch2)
            self.ch2_plot_curve_glow.setData([x * self.VOL_RANGE_ch2/5 for x in new_data[1]])
            self.ch2_plot_curve_glow.setPen(glow_pen_ch2)
            self.ch1_plot_curve_real.setData([x * self.VOL_RANGE_ch1/5 for x in new_data[2]])
            self.ch1_plot_curve_real.setPen(main_pen_ch1)
            self.ch1_plot_curve_glow.setData([x * self.VOL_RANGE_ch1/5 for x in new_data[2]])
            self.ch1_plot_curve_glow.setPen(glow_pen_ch1)
            self.fft_thread.set_input(ch1=new_data[1],ch2=new_data[2],sample_rate=5000000)
            #print(f"FFT输入数据：f{self.receive_thread.voltage_raw}")
        elif new_data[0]== "status":
            pass
            #print(f"接收到状态数据: {self.digital_measure_result}")
    #选择波形类型               
    def wave_cs(self, wave_type):
        if self.net_config:
            
            if self.ui.sine_btn.isChecked() and wave_type == "sine":
                self.ui.square_btn.setChecked(False)
                self.ui.triangle_btn.setChecked(False)
                self.ui.saw_btn.setChecked(False)
                self.ui.bread_btn.setChecked(False)
                cmd = 0
                self.wave_emiter["type"] = cmd
            elif self.ui.square_btn.isChecked() and wave_type == "square":
                self.ui.sine_btn.setChecked(False)
                self.ui.triangle_btn.setChecked(False)
                self.ui.saw_btn.setChecked(False)
                self.ui.bread_btn.setChecked(False)
                cmd = 1
                self.wave_emiter["type"] = cmd
            elif self.ui.triangle_btn.isChecked() and wave_type == "triangle":
                self.ui.sine_btn.setChecked(False)
                self.ui.square_btn.setChecked(False)
                self.ui.saw_btn.setChecked(False)
                self.ui.bread_btn.setChecked(False)
                cmd = 2
                self.wave_emiter["type"] = cmd
            elif self.ui.saw_btn.isChecked() and wave_type == "saw":
                self.ui.sine_btn.setChecked(False)
                self.ui.square_btn.setChecked(False)
                self.ui.triangle_btn.setChecked(False)
                self.ui.bread_btn.setChecked(False)
                cmd = 3
                self.wave_emiter["type"] = cmd
            elif (self.ui.saw_btn.isChecked() or self.ui.triangle_btn.isChecked() or self.ui.square_btn.isChecked() or self.ui.sine_btn.isChecked() or self.ui.bread_btn.isChecked())==False and wave_type == "renyiboxing":
                #print(f"坐标是{self.wp.pos_xy}")
                cmd=5
                self.wave_emiter["type"] = cmd
            elif(self.ui.bread_btn.isChecked()) and wave_type == "bread":
                self.ui.sine_btn.setChecked(False)
                self.ui.square_btn.setChecked(False)
                self.ui.triangle_btn.setChecked(False)
                self.ui.saw_btn.setChecked(False)
                cmd = 4
                self.wave_emiter["type"] = cmd
            print(f"波形类型选择: {self.wave_emiter['type']}")
        else:
             QApplication.instance().setStyleSheet("QMessageBox * { color:red; }")
             QMessageBox.warning(self, "提示", "请先配置连接方式！")  
    #修改发送波形的参数
    def wave_parameter_change(self, param_type):
        if self.net_config:
            if param_type == "num":
                self.wave_emiter['frequency'] = int(self.ui.fre_edit.text())
            elif param_type == "scale":
                self.wave_emiter['scale'] = (self.ui.fre_scale.currentText())
            print(f"波形参数更新: {self.wave_emiter}")
        else:
             QApplication.instance().setStyleSheet("QMessageBox * { color:red; }")
             QMessageBox.warning(self, "提示", "请先配置连接方式！")
    #发送波形命令
    def send_wave_command(self):
        if not self.net_config:
            QApplication.instance().setStyleSheet("QMessageBox * { color:red; }")
            QMessageBox.warning(self, "提示", "请先配置连接方式！")
            return

        # 读取频率（用户输入）与量纲（UI 选择）
        try:
            freq_num = float(self.ui.fre_edit.text() or 0)
        except Exception:
            QMessageBox.warning(self, "提示", "频率输入不合法！")
            return

        # 解析量纲：优先尝试从 UI 当前文本获取常用映射
        scale_text = self.ui.fre_scale.currentText() if hasattr(self.ui.fre_scale, 'currentText') else None
        scale_map = {"Hz": 1, "kHz": 1_000, "MHz": 1_000_000}
        if self.wave_emiter.get('type') != 5:
            if isinstance(self.wave_emiter.get('scale'), (int, float)):
                scale_factor = self.wave_emiter['scale']
            elif isinstance(self.wave_emiter.get('scale'), dict):
                # 如果还保留映射字典，优先使用 UI 上的选择
                scale_factor = scale_map.get(scale_text, 1)
            else:
                # 波动情况下再从 UI 文本解析
                scale_factor = scale_map.get(scale_text, 1)

            frequency_hz = int(freq_num * scale_factor)
            # DDS 参考时钟（可通过 net_config 覆盖），默认 125 MHz
            dds_ref_clk = float(self.net_config.get('dds_ref_clk', 125_000_000))
            # 计算 32-bit DDS 频率字（FTW）
            ftw = int((frequency_hz * (1 << 32)) / dds_ref_clk) & 0xFFFFFFFF
            # 波形类型（用 32-bit 发送）
            wave_type = int(self.wave_emiter.get('type', 0)) & 0xFFFFFFFF
            # 包头 / 包尾 — 占位常量，按需替换为实际协议内容
            # 示例来自你的描述： header = 00aabbcc00000000 , tail = 08ddeeff
            try:
                header = bytes.fromhex(self.net_config.get('packet_header_hex', '08aabbcc00000000'))
            except Exception:
                header = bytes.fromhex('08aabbcc00000000')
            try:
                tail = bytes.fromhex(self.net_config.get('packet_tail_hex', '08ddeeff'))
            except Exception:
                tail = bytes.fromhex('08ddeeff')
            # middle: 4 字节 freq_word + 4 字节 wave_type，使用网络字节序（big-endian）
            middle = struct.pack('!I', ftw) + struct.pack('!I', wave_type)
            packet = header + middle + tail
            # 发送 UDP 包
            try:
                udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                target_ip = self.net_config['target_ip']
                target_port = int(self.net_config['target_port'])
                udp_socket.sendto(packet, (target_ip, target_port))
                udp_socket.close()
                print(f"发送波形包 -> target={target_ip}:{target_port} freq={frequency_hz}Hz ftw=0x{ftw:08X} type={wave_type}")
                print(f"包(hex): {packet.hex()}")
            except Exception as e:
                QMessageBox.warning(self, "发送失败", f"发送失败: {e}")
        else :
            try:
                header = bytes.fromhex(self.net_config.get('packet_header_hex', '06aabbcc'))
            except Exception:
                header = bytes.fromhex('06aabbcc')
            try:
                tail = bytes.fromhex(self.net_config.get('packet_tail_hex', '06ddeeff'))
            except Exception:
                tail = bytes.fromhex('06ddeeff')
            # 去除哨兵并线性缩放 y 到 0-255（按画布高度映射）
            wave_points = [p for p in self.wp.pos_xy if p != (-1, -1)]
            wave_num = self.resample_to_1024(wave_points, 1024)
            print(f"{wave_num}")
            middle = b''.join(struct.pack('!B', int(num) & 0xFF) for num in wave_num)
            packet = header + middle + tail
            try:
                udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                target_ip = self.net_config['target_ip']
                target_port = int(self.net_config['target_port'])
                udp_socket.sendto(packet, (target_ip, target_port))
                udp_socket.close()
                print(f"发送任意波形包 -> target={target_ip}:{target_port} 点数={len(wave_num)}")
                print(f"包(hex): {packet.hex()}")
            except Exception as e:
                QMessageBox.warning(self, "发送失败", f"发送失败: {e}")
    #手绘波形输出            
    def resample_to_1024(self, wave_points, target_len=1024):
        # 过滤哨兵并取 y 值
        pts = [p for p in wave_points if p != (-1, -1)]
        ys = []
        for p in pts:
            if isinstance(p, (tuple, list)) and len(p) >= 2:
                ys.append(float(p[1]))
            else:
                ys.append(float(p))

        n = len(ys)
        if n == 0:
            return [0] * target_len

        # 若输入看起来是像素（最大值明显大于1），按画布高度归一化到 [0,1]
        if max(ys) > 1.5:
            h = max(1, self.wp.height() - 1)
            ys = [max(0.0, min(1.0, y / h)) for y in ys]

        # downsample：均匀选取索引（位置映射并四舍五入）
        if n >= target_len:
            out = []
            for i in range(target_len):
                pos = i * (n - 1) / (target_len - 1) if target_len > 1 else 0.0
                idx = int(round(pos))
                idx = max(0, min(n - 1, idx))
                out.append(ys[idx])
        else:
            # upsample：临界保持（重复点）
            base = target_len // n
            rem = target_len % n
            out = []
            for i, v in enumerate(ys):
                reps = base + (1 if i < rem else 0)
                out.extend([v] * reps)

        # 映射到 0..255 整数并裁剪
        res = [min(255, max(0, int(round(v * 255)))) for v in out]
        return res
    def on_line_moved(self, *args):
        # 尽量兼容不同 pyqtgraph 版本，优先使用 value()，其次尝试 pos()
        if self.receive_thread:    
            pos = None
            try:
                pos = self.movable_line.value()
            except Exception:
                try:
                    pos = self.movable_line.pos()
                except Exception:
                    pass
            if pos is not None:
                pos_num=pos*127/5+127
                self.trig_config["voltage"]=int(pos_num)
                self.trig_config["edge"]=self.ui.edge_comboBox.currentIndex()
                #print("触发配置:", self.trig_config)
                self.receive_thread.send_trigger_config(self.trig_config)
    def get_send(self):
        if self.uart_thread:
                if self.ui.encode_box.currentIndex()==0:
                    cmd=bytes.fromhex(self.ui.uart_edit.toPlainText())
                    print(f"准备发送 串口数据: {cmd.hex()}")
                    self.uart_thread.open_port()
                    self.uart_thread.write(cmd)
                else:    
                    cmd=self.ui.uart_edit.toPlainText().encode('utf-8')
                    print(f"准备发送 串口数据: {cmd.hex()}")
                    self.uart_thread.open_port()
                    self.uart_thread.write(cmd)
        else:
                QApplication.instance().setStyleSheet("QMessageBox * { color:red; }")
                QMessageBox.warning(self, "提示", "请先连接串口设备！")
    def output_pwm(self):
        # 点击输出：UI -> self.pwm_config（保持原发送逻辑），注意前面 lambda 已先调用 _apply_pwm_ui_to_cfg/_update_pwm_curves
        if self.uart_thread:
            self.pwm_config[0]['frequency'] = int(self.ui.all_fre_edit.text())
            self.pwm_config[0]['duty'] = int(self.ui.duty_edit.text())
            self.pwm_config[0]['phase'] = int(self.ui.ch1_pha_edit.text())
            self.pwm_config[0]['visible'] = self.ui.ch1_check.isChecked()
            self.pwm_config[1]['frequency'] = int(self.ui.all_fre_edit.text())
            self.pwm_config[1]['phase'] = int(self.ui.ch2_pha_edit.text())
            self.pwm_config[2]['phase'] = int(self.ui.ch3_pha_edit.text())
            self.pwm_config[3]['phase'] = int(self.ui.ch4_pha_edit.text())
            print(f"PWM配置: {self.pwm_config}")
            header=bytes.fromhex('06ab0000')
            data=self.pwm_command_build()
            packet=header+data
            print(f"准备发送 PWM 配置包: {packet.hex()}")
            self.uart_thread.open_port()
            self.uart_thread.write(packet)
            self.plot_pwm_waveforms()
        else:
            QApplication.instance().setStyleSheet("QMessageBox * { color:red; }")
            QMessageBox.warning(self, "提示", "请先连接串口设备！")
            
    # 构建 PWM 配置命令包数据部分
    def pwm_command_build(self):
        fre=struct.pack('!I', int(round(50000000/self.pwm_config[0]["frequency"])))
        duty=struct.pack('!I', int(round(50000000/self.pwm_config[0]["frequency"]) * (self.pwm_config[0]["duty"]/100)))
        print(f"占空比计算结果{int(round(50000000/self.pwm_config[0]['frequency'])) *(self.pwm_config[0]['duty']/100)}")
        phase1=struct.pack('!H', int(self.pwm_config[0]["phase"]/360*int(round(50000000/self.pwm_config[0]["frequency"]))))
        phase2=struct.pack('!H', int(self.pwm_config[1]["phase"]/360*int(round(50000000/self.pwm_config[0]["frequency"]))))
        phase3=struct.pack('!H', int(self.pwm_config[2]["phase"]/360*int(round(50000000/self.pwm_config[0]["frequency"]))))
        phase4=struct.pack('!H', int(self.pwm_config[3]["phase"]/360*int(round(50000000/self.pwm_config[0]["frequency"]))))
        
        
        print(self.pwm_config[1]["phase"])
        return fre+duty+phase1+phase2+phase3+phase4

    # ----------------- PWM 辅助方法 -----------------
    def plot_pwm_waveforms(self):
        # 占空比（来自 ch1_duty_edit 控制所有）
        duty = int(self.ui.duty_edit.text())
        # 相位列表
        phases = []
        phases.append(int(self.ui.ch1_pha_edit.text()))
        phases.append(int(self.ui.ch2_pha_edit.text()))
        phases.append(int(self.ui.ch3_pha_edit.text()))
        phases.append(int(self.ui.ch4_pha_edit.text()))
        # 可见性
        visibles = []
        visibles.append(self.ui.ch1_check.isChecked())
        visibles.append(self.ui.ch2_check.isChecked())
        visibles.append(self.ui.ch3_check.isChecked())
        visibles.append(self.ui.ch4_check.isChecked())
        for i, phase in enumerate(phases):
            t,wave=self.generate_square_wave(duty=duty/100,phase=phase/360)
            plot=pg.PlotCurveItem(t, wave, pen=pg.mkPen((100,150,255), width=1.5))
            if i==0:
                self.vb1.clear()
                self.vb1.addItem(plot)
            elif i==1:
                self.vb2.clear()
                self.vb2.addItem(plot)
            elif i==2:
                self.vb3.clear() 
                self.vb3.addItem(plot)
            elif i==3:
                self.vb4.clear()
                self.vb4.addItem(plot)
        for i,visible in enumerate(visibles):
            if i==0:
                self.vb1.setVisible(visible)
            elif i==1:
                self.vb2.setVisible(visible)
            elif i==2:
                self.vb3.setVisible(visible)
            elif i==3:
                self.vb4.setVisible(visible)

    def generate_square_wave(self, num_cycles=10, duty=0.5, phase=0, samples_per_cycle=100):
        """生成方波信号"""
        total_samples = num_cycles * samples_per_cycle
        t = np.linspace(0, num_cycles, total_samples)
        
        # 应用相位偏移 (转换为周期比例)
        phase_offset = phase % 1  # 确保相位在0-1之间
        t_shifted = t + phase_offset
        
        # 生成方波
        square_wave = np.where(np.modf(t_shifted)[0] < duty, 1, 0)
        
        return t, square_wave
    def spectrum_visible(self,checked):
        if checked:
            self.plot_Spectrum.setVisible(True)
            self.ui.spectrum_btn.setText("关闭")
            self.ui.waveplot.setVisible(False)
        else:
            self.plot_Spectrum.setVisible(False)   
            self.ui.spectrum_btn.setText("打开")
            self.ui.waveplot.setVisible(True)
    #FFT线程结果处理        
    def on_result(self, res):
        """
        改进后的频谱绘制：
        - 平滑（可配置的简单移动平均）
        - 线条 + 填充
        - 峰值检测并用 Scatter + TextItem 标注（只标前若干个高峰）
        - 使用线程返回的 harmonics 绘制谐波标签（优先）
        """
        # 先把数值更新（保持之前逻辑）
        try:
            self.ui.ch1_osc_fre_num_label.setText(f"{res['freq1']:.2f}")
            self.ui.ch2_osc_fre_num_label.setText(f"{res['freq2']:.2f}")
            self.ui.ch1_osc_vpp_num_label.setText(f"{res['ptp1']:.2f}")
            self.ui.ch2_osc_vpp_num_label.setText(f"{res['ptp2']:.2f}")
            self.ui.ch1_osc_bio_num_label.setText(f"{res['dc1']:.2f}")
            self.ui.ch2_osc_bio_num_label.setText(f"{res['dc2']:.2f}")
            self.ui.fre_num_label.setText(f"{res['freq1']:.2f}")
            self.ui.duty_num_label.setText(f"{res['duty1']*100:.2f}")
            ht = 1/res['freq1'] * res['duty1']
            lt= 1/res['freq1'] * (1 - res['duty1'])
            self.ui.ht_num_label.setText(f"{ht:.11f}")
            self.ui.lt_num_label.setText(f"{lt:.11f}")
        except Exception:
            pass
        if res.get('alias_warning'):
            print("警告：检测到主频超出 Nyquist，可能发生混叠")

        f = res.get('f')
        mag1 = res.get('mag1')
        mag2 = res.get('mag2')

        if f is None or mag1 is None:
            return

        # 简单平滑（移动平均），避免过度平滑，窗口可调
        def smooth(y, window_len=3):
            if y is None or len(y) < 3:
                return y
            win = np.ones(window_len) / window_len
            ypad = np.pad(y, (window_len//2, window_len//2), mode='edge')
            return np.convolve(ypad, win, mode='valid')[:len(y)]

        mag1_s = smooth(np.asarray(mag1), window_len=3)
        mag2_s = smooth(np.asarray(mag2), window_len=3) if mag2 is not None else None

        # 更新曲线（复用已有 PlotCurveItem）
        try:
            self.spec_curve1.setData(f, mag1_s)
        except Exception:
            try:
                self.pb1.removeItem(self.spec_curve1)
            except Exception:
                pass
            self.spec_curve1 = pg.PlotCurveItem(f, mag1_s, pen=pg.mkPen((0,200,0), width=1), fillLevel=0, brush=(0,200,0,60))
            self.pb1.addItem(self.spec_curve1)

        if mag2_s is not None:
            try:
                self.spec_curve2.setData(f, mag2_s)
            except Exception:
                try:
                    self.pb2.removeItem(self.spec_curve2)
                except Exception:
                    pass
                self.spec_curve2 = pg.PlotCurveItem(f, mag2_s, pen=pg.mkPen((200,50,50), width=1), fillLevel=0, brush=(200,50,50,60))
                self.pb2.addItem(self.spec_curve2)
        else:
            self.spec_curve2.setData([], [])

        # 自动设置 x 范围到 Nyquist 或数据末端
        fs_used = res.get('fs_used', res.get('fs', None))
        try:
            if fs_used:
                nyq = fs_used / 2.0
                maxx = min(nyq, float(f[-1]))
                self.pb1.setRange(xRange=(0, maxx), padding=0.02)
                self.pb2.setRange(xRange=(0, maxx), padding=0.02)
        except Exception:
            pass

        # ---------- 峰值检测并标注 ----------
        # 参数：只标前 top_k 个峰
        top_k = 6
        # 基于高度阈值与最小间距寻找峰
        def detect_peaks(freqs, mags, height_frac=0.12, min_dist_hz=None):
            if mags is None or len(mags) == 0:
                return np.array([], dtype=int)
            height = np.max(mags) * height_frac
            if min_dist_hz is None:
                min_dist_bins = 1
            else:
                df = freqs[1] - freqs[0]
                min_dist_bins = max(1, int(round(min_dist_hz / df)))
            peaks, props = find_peaks(mags, height=height, distance=min_dist_bins)
            # 按高度排序并取前 K
            if len(peaks) > 0:
                idxs = np.argsort(props['peak_heights'])[::-1]
                peaks = peaks[idxs][:top_k]
            return peaks

        # 清除旧文本标注（复用 TextItem 列表）
        for t in self._peak_texts1:
            try:
                self.pb1.removeItem(t)
            except Exception:
                pass
        self._peak_texts1.clear()
        for t in self._peak_texts2:
            try:
                self.pb2.removeItem(t)
            except Exception:
                pass
        self._peak_texts2.clear()

        # 通道1 峰值
        peaks1 = detect_peaks(f, mag1_s, height_frac=0.07, min_dist_hz= (f[-1]/100.0))
        if len(peaks1) > 0:
            pts = [{'pos': (f[i], mag1_s[i])} for i in peaks1]
            self._spec_peaks1.setData([f[i] for i in peaks1], [mag1_s[i] for i in peaks1])
            for i in peaks1:
                txt = pg.TextItem(text=f"{f[i]:.1f}Hz\n{mag1_s[i]:.2f}", color=(255,220,0), anchor=(0.5, -0.2))
                self.pb1.addItem(txt)
                txt.setPos(f[i], mag1_s[i] + (np.max(mag1_s) * 0.03))
                self._peak_texts1.append(txt)
        else:
            self._spec_peaks1.setData([], [])

        # 通道2 峰值
        if mag2_s is not None:
            peaks2 = detect_peaks(f, mag2_s, height_frac=0.07, min_dist_hz=(f[-1]/100.0))
            if len(peaks2) > 0:
                self._spec_peaks2.setData([f[i] for i in peaks2], [mag2_s[i] for i in peaks2])
                for i in peaks2:
                    txt = pg.TextItem(text=f"{f[i]:.1f}Hz\n{mag2_s[i]:.2f}", color=(255,120,120), anchor=(0.5, -0.2))
                    self.pb2.addItem(txt)
                    txt.setPos(f[i], mag2_s[i] + (np.max(mag2_s) * 0.03))
                    self._peak_texts2.append(txt)
            else:
                self._spec_peaks2.setData([], [])

        # ---------- 谐波标签（使用线程返回的 harmonics） ----------
        # 先清除旧谐波标签（你的代码已有 self.harmonic_labels1/2）
        for it in self.harmonic_labels1:
            try: self.pb1.removeItem(it)
            except Exception: pass
        self.harmonic_labels1.clear()
        for it in self.harmonic_labels2:
            try: self.pb2.removeItem(it)
            except Exception: pass
        self.harmonic_labels2.clear()

        harmonics = res.get('harmonics', [])
        max_amp1 = float(np.max(mag1_s)) if mag1_s is not None and len(mag1_s) > 0 else 1.0
        max_amp2 = float(np.max(mag2_s)) if mag2_s is not None and len(mag2_s) > 0 else 1.0

        for h in harmonics:
            try:
                n, hf, amp = h
            except Exception:
                continue
            if hf > f[-1]:
                continue
            # 通道1 标签
            lab1 = pg.TextItem(text=f"{int(n)}×\n{hf:.1f}Hz",
                               color=(255, 100, 100) if int(n) % 2 == 1 else (160,160,160),
                               anchor=(0.5, 0))
            self.pb1.addItem(lab1)
            lab1.setPos(hf, amp + max_amp1 * self.harmonic_label_offset)
            self.harmonic_labels1.append(lab1)
            # 通道2
            if mag2_s is not None:
                idx2 = int(np.argmin(np.abs(f - hf)))
                amp2 = float(mag2_s[idx2]) if idx2 < len(mag2_s) else 0.0
                lab2 = pg.TextItem(text=f"{int(n)}×\n{hf:.1f}Hz",
                                   color=(200, 50, 50) if int(n) % 2 == 1 else (120,120,120),
                                   anchor=(0.5, 0))
                self.pb2.addItem(lab2)
                lab2.setPos(hf, amp2 + max_amp2 * self.harmonic_label_offset)
                self.harmonic_labels2.append(lab2)

    def on_error(self, msg):
        """接收 FFTThread.error 信号的简单处理，避免 AttributeError"""
        int("FFT 线程错误:", msg)
    def cum_output(self): 
        if self.net_config:
            header=bytes.fromhex('02aabbcc')+bytes.fromhex('00000000')
            ch1_binary_str = self.ui.ch1_customlist_edit.text()  # 获取二进制字符串，例如 "10101"
            ch1_decimal_num = int(ch1_binary_str, 2)  # 将二进制字符串转换为十进制整数
            ch2_binary_str = self.ui.ch2_customlist_edit.text()  # 获取二进制字符串，例如 "10101"
            ch2_decimal_num = int(ch2_binary_str, 2)  # 将二进制字符串转换为十进制整数
            ch3_binary_str = self.ui.ch3_customlist_edit.text()  # 获取二进制字符串，例如 "10101"
            ch3_decimal_num = int(ch3_binary_str, 2)  # 将二进制字符串转换为十进制整数
            ch4_binary_str = self.ui.ch4_customlist_edit.text()  # 获取二进制字符串，例如 "10101"
            ch4_decimal_num = int(ch4_binary_str, 2)  # 将二进制字符串转换为十进制整数
            decimal_num=ch1_decimal_num+ch2_decimal_num*256+ch3_decimal_num*65536+ch4_decimal_num*16777216
            customlist = struct.pack('!I', decimal_num)
            fre=struct.pack('!I', int(5000000/int(self.ui.cum_fre_edit.text())))
            tail=bytes.fromhex('02ddeeff')
            packet=header+customlist+fre+tail
            try:
                udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                target_ip = self.net_config['target_ip']
                target_port = int(self.net_config['target_port'])
                udp_socket.sendto(packet, (target_ip, target_port))
                udp_socket.close()
                #print(f"发送序列数据 -> target={target_ip}:{target_port} customlist={self.ui.customlist_edit.text()}")
                print(f"包(hex): {packet.hex()}")
            except Exception as e:
                QMessageBox.warning(self, "发送失败", f"发送失败: {e}")
        else:
                QApplication.instance().setStyleSheet("QMessageBox * { color:red; }")
                QMessageBox.warning(self, "提示", "请先连接网络设备！")
    def set_wave_visible(self,wave_type):
        if wave_type == 1:
            if self.ui.ch1_checkbox.isChecked():
                self.ch1_plot_curve_real.setVisible(True)
                self.ch1_plot_curve_glow.setVisible(True)
            else:
                self.ch1_plot_curve_real.setVisible(False)
                self.ch1_plot_curve_glow.setVisible(False)
        elif wave_type == 2:
            if self.ui.ch2_checkbox.isChecked():
                self.ch2_plot_curve_real.setVisible(True)
                self.ch2_plot_curve_glow.setVisible(True)
            else:
                self.ch2_plot_curve_real.setVisible(False)
                self.ch2_plot_curve_glow.setVisible(False)
    def set_digital_visible(self, channel):
        if channel==1:
            if self.ui.d1_checkBox.isChecked():
                self.logic_channel_visible[0]=True
            else:
                self.logic_channel_visible[0]=False
        elif channel==2:
            if self.ui.d2_checkBox.isChecked():
                self.logic_channel_visible[1]=True
            else:
                self.logic_channel_visible[1]=False
        elif channel==3:
            if self.ui.d3_checkBox.isChecked():
                self.logic_channel_visible[2]=True
            else:
                self.logic_channel_visible[2]=False
        elif channel==4:
            if self.ui.d4_checkBox.isChecked():
                self.logic_channel_visible[3]=True
            else:
                self.logic_channel_visible[3]=False
        elif channel==5:
            if self.ui.d5_checkBox.isChecked():
                self.logic_channel_visible[4]=True
            else:
                self.logic_channel_visible[4]=False
        elif channel==6:
            if self.ui.d6_checkBox.isChecked():
                self.logic_channel_visible[5]=True
            else:
                self.logic_channel_visible[5]=False
        elif channel==7:
            if self.ui.d7_checkBox.isChecked():
                self.logic_channel_visible[6]=True
            else:
                self.logic_channel_visible[6]=False
        elif channel==8:
            if self.ui.d8_checkBox.isChecked():
                self.logic_channel_visible[7]=True
            else:
                self.logic_channel_visible[7]=False
    def on_sample_clicked(self):

        self.logic_analyzer.set_visibility_mask(self.logic_channel_visible)

       
