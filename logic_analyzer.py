from PyQt5 import QtWidgets, QtCore, QtGui
from pyqtgraph import ViewBox
import numpy as np
import pyqtgraph as pg

# 性能参数：可根据需要调整
# 减少默认采样率/时长，避免一次性生成过多点
# max_plot_points 控制绘图时最多点数（下采样目标）
DEFAULT_SAMPLE_RATE = 200_000.0   # 200kHz
DEFAULT_DURATION = 0.02           # 20 ms
MAX_PLOT_POINTS = 2000
DEFAULT_UPDATE_MS = 50            # 50 ms 刷新一次（约 20 FPS）

class ChannelHeader(QtWidgets.QWidget):
    """自定义通道标题控件（显示通道号和颜色标识）"""
    def __init__(self, channel_num, color, parent=None):
        super().__init__(parent)
        self.color = color
        self.channel_num = channel_num
        self.setFixedHeight(30)
        self.setFixedWidth(80)
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 绘制深色背景
        painter.fillRect(event.rect(), QtGui.QColor(40, 40, 40))
        
        # 绘制彩色标识点（与通道颜色一致）
        painter.setBrush(QtGui.QColor(*self.color))
        painter.setPen(QtGui.QColor(200, 200, 200))
        painter.drawEllipse(10, 10, 10, 10)
        
        # 绘制通道号（白色粗体，微软雅黑11号）
        font = QtGui.QFont("微软雅黑", 11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QtGui.QColor(255, 255, 255))
        painter.drawText(30, 20, f"CH {self.channel_num+1}")  # 通道号从1开始


class LogicAnalyzerWidget(QtWidgets.QWidget):
    """增强版逻辑分析仪控件（带协议分组同步）"""
    data_updated = QtCore.pyqtSignal(int, np.ndarray, np.ndarray)  # 通道号, 时间数据, 通道数据
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化数据参数（使用较小默认值以避免卡顿）
        self.sample_rate = DEFAULT_SAMPLE_RATE
        self.duration = DEFAULT_DURATION
        self.time = np.linspace(0, self.duration, int(self.sample_rate * self.duration))
        self.channel_data = np.zeros((8, len(self.time)))
       # 绘图/性能控制
        self.max_plot_points = MAX_PLOT_POINTS
        self.update_interval_ms = DEFAULT_UPDATE_MS
        self._timer = None
        self._start_progress_timer = None
        self._start_progress_active = False
        self.curves = [None] * 8
        self.channel_colors = [(200,50,50), (50,200,50), (50,50,200), (200,200,50),
                               (200,50,200), (50,200,200), (150,150,50), (100,100,200)]
        # 协议/解析相关初始值（必须在 setup_protocol_sync 前定义）
        # 协议分组：根据通道号分配（示例：I2C 使用 0/1，SPI 使用 2/3/4/5，UART 使用 6/7）
        self.protocol_groups = {
            "i2c": [0, 1],
            "spi": [2, 3, 4, 5],
            "uart": [6, 7]
        }
        # 协议名称显示用
        self.protocol_names = {"i2c": "I2C", "spi": "SPI", "uart": "UART"}
        # 解析器映射（指向类方法）
        self.parsers = {
            "i2c": self._parse_i2c,
            "spi": self._parse_spi,
            "uart": self._parse_uart
        }
        # 运行状态标志
        self.is_running = False

        # 仅打印一次解码结果标志
        self._decoded_printed = False

        # 外部可设置的可见性掩码（长度8，True/False）；默认全部可见
        self.visibility_mask = [True] * 8

        # 预生成一次信号，避免在每次定时器回调中重复生成
        # self.generate_custom_signals()  # moved to start()
 
        # 设置UI
        self.setup_ui()
        
    def setup_ui(self):
        """设置UI布局（包含波形显示和解码区域）"""
        # 主布局（垂直）
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 波形显示区域（滚动）
        waveform_frame = QtWidgets.QWidget()
        waveform_layout = QtWidgets.QVBoxLayout(waveform_frame)
        waveform_layout.setContentsMargins(0, 0, 0, 0)
        waveform_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: #121212; border: none;")
        scroll_widget = QtWidgets.QWidget()
        scroll_widget.setStyleSheet("background-color: #121212;")
        scroll.setWidget(scroll_widget)
        waveform_layout.addWidget(scroll)
        
        # 启动时的进度条（默认隐藏），在 start() 被调用后显示 2 秒钟再真正显示波形/解码内容
        self.start_progress = QtWidgets.QProgressBar()
        self.start_progress.setRange(0, 100)
        self.start_progress.setValue(0)
        self.start_progress.setFixedHeight(18)
        self.start_progress.setTextVisible(True)
        self.start_progress.setFormat("启动中... %p%")
        self.start_progress.setVisible(False)
        waveform_layout.addWidget(self.start_progress)
        
        # 波形布局（垂直排列8个通道）
        self.plot_layout = QtWidgets.QVBoxLayout(scroll_widget)
        self.plot_layout.setSpacing(0)
        
        # 通道颜色定义
        self.channel_colors = [
            (255, 0, 0),      # 通道1：红色
            (255, 255, 0),    # 通道2：黄色
            (0, 255, 0),      # 通道3：绿色
            (0, 255, 255),    # 通道4：青色
            (255, 0, 255),    # 通道5：品红
            (255, 165, 0),    # 通道6：橙色
            (0, 0, 255),      # 通道7：蓝色
            (128, 0, 128)     # 通道8：紫色
        ]
        
        # 创建8个通道的波形显示区域
        self.viewboxes = []
        self.curves = []
        self.channel_containers = []
        
        for i in range(8):
            # 通道容器（包含标题和波形）
            container = QtWidgets.QWidget()
            container.setStyleSheet("background-color: #1E1E1E;")
            container_layout = QtWidgets.QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            
            # 通道标题（显示通道号和颜色）
            header = ChannelHeader(i, self.channel_colors[i])
            container_layout.addWidget(header)
            
            # 波形图（PyQtGraph控件）
            plot = pg.PlotWidget()
            plot.setBackground("#1E1E1E")
            plot.setStyleSheet("border: none;")
            
            # 配置坐标轴（隐藏标签，浅灰色刻度）
            plot.getAxis('left').setPen(pg.mkPen(color='#777777'))
            plot.getAxis('bottom').setPen(pg.mkPen(color='#777777'))
            plot.showLabel('left', False)
            plot.showLabel('bottom', False)
            plot.showAxis('bottom', show=(i==7))  # 仅最后一个通道显示X轴
            
            # 配置ViewBox（固定Y范围，禁用Y缩放）
            vb = plot.getViewBox()
            vb.setYRange(-0.2, 1.2)
            vb.setXRange(0, self.duration)  # 使用self.duration设置初始X轴范围
            vb.setMouseEnabled(y=False)
            
            # 创建波形曲线（颜色与通道一致）
            # 提供初始占位数据以满足 stepMode 的 len(X)=len(Y)+1 要求，
            # 后续 update_waveforms 会使用真实长度的数据替换。
            x_init = np.array([0.0, self.duration])  # len=2
            y_init = np.array([0.0])                # len=1 -> len(x)=len(y)+1
            curve = pg.PlotCurveItem(x=x_init, y=y_init, pen=pg.mkPen(color=self.channel_colors[i], width=2), stepMode=True)
            plot.addItem(curve)
            
            # 保存控件引用
            self.viewboxes.append(vb)
            self.curves.append(curve)
            self.channel_containers.append(container)
            
            # 添加到容器布局
            container_layout.addWidget(plot, 1)
            
            # 添加到主布局
            self.plot_layout.addWidget(container)
        
        waveform_layout.addWidget(scroll)
        main_layout.addWidget(waveform_frame, 7)  # 70%高度
        
        # 解码显示区域（30%高度）
        decoder_frame = QtWidgets.QFrame()
        decoder_frame.setStyleSheet("background-color: #1E1E1E; border-top: 1px solid #444;")
        decoder_layout = QtWidgets.QVBoxLayout(decoder_frame)
        decoder_layout.setContentsMargins(10, 10, 10, 10)
        decoder_layout.setSpacing(5)
        
        # 解码标题
        decoder_label = QtWidgets.QLabel("协议解码结果")
        decoder_label.setStyleSheet("""
            QLabel {
                color: #4FC3F7;
                font-family: 微软雅黑;
                font-size: 14px;
                font-weight: bold;
                padding-bottom: 5px;
            }
        """)
        decoder_layout.addWidget(decoder_label)
        
        # 解码结果选项卡
        self.decoder_tabs = QtWidgets.QTabWidget()
        self.decoder_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #1E1E1E;
                font-family: 微软雅黑;
            }
            QTabBar::tab {
                background: #333;
                color: #EEE;
                padding: 8px 15px;
                border: 1px solid #444;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-family: 微软雅黑;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #0078D7;
                color: white;
            }
        """)
        
        # I2C解码结果
        self.i2c_decoder = QtWidgets.QTextEdit()
        self.i2c_decoder.setStyleSheet("""
            QTextEdit {
                background: #252525;
                color: #CCCCCC;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: 微软雅黑;
                font-size: 11px;
            }
        """)
        self.i2c_decoder.setReadOnly(True)
        self.decoder_tabs.addTab(self.i2c_decoder, "I2C")
        
        # SPI解码结果
        self.spi_decoder = QtWidgets.QTextEdit()
        self.spi_decoder.setStyleSheet("""
            QTextEdit {
                background: #252525;
                color: #CCCCCC;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: 微软雅黑;
                font-size: 11px;
            }
        """)
        self.spi_decoder.setReadOnly(True)
        self.decoder_tabs.addTab(self.spi_decoder, "SPI")
        
        # UART解码结果
        self.uart_decoder = QtWidgets.QTextEdit()
        self.uart_decoder.setStyleSheet("""
            QTextEdit {
                background: #252525;
                color: #CCCCCC;
                border: 1px solid #444;
                border-radius: 4px;
                font-family: 微软雅黑;
                font-size: 11px;
            }
        """)
        self.uart_decoder.setReadOnly(True)
        self.decoder_tabs.addTab(self.uart_decoder, "UART")
        
        decoder_layout.addWidget(self.decoder_tabs, 1)
        main_layout.addWidget(decoder_frame, 3)  # 30%高度)
        
        # 设置协议分组同步
        self.setup_protocol_sync()

        # 初始界面不显示任何波形或解码结果，直到用户点击“开始采集”调用 start()
        for c in self.channel_containers:
            c.setVisible(False)
        # 清空解码区
        try:
            self.i2c_decoder.setText("")
            self.spi_decoder.setText("")
            self.uart_decoder.setText("")
        except Exception:
            pass
    
    def setup_protocol_sync(self):
        """设置协议分组同步功能"""
        # 创建lambda工厂函数，确保正确捕获参数
        def make_sync_lambda(protocol):
            return lambda vb, r: self.sync_protocol_group(protocol, vb)
        
        # 为每个协议组创建同步机制
        for protocol, channels in self.protocol_groups.items():
            # 为组内的每个通道连接信号
            for channel in channels:
                vb = self.viewboxes[channel]
                # 使用部分函数应用确保参数正确传递
                vb.sigXRangeChanged.connect(
                    make_sync_lambda(protocol)
                )

    def set_visibility_mask(self, mask):
        """外部接口：传入长度8的布尔列表，设置通道显示掩码（下次 start 时生效并立即应用）"""
        if not isinstance(mask, (list, tuple)) or len(mask) != 8:
            raise ValueError("visibility mask must be a list/tuple of 8 booleans")
        self.visibility_mask = [bool(x) for x in mask]
        # 如果当前正在运行，立即应用
        if self.is_running:
            for idx, vis in enumerate(self.visibility_mask):
                self.set_channel_visible(idx, vis)

    def sync_protocol_group(self, protocol, source_vb):
        """同步协议组内的所有通道"""
        # 获取当前协议组的通道列表
        channels = self.protocol_groups[protocol]
        
        # 获取源通道的当前视图范围
        x_range = source_vb.viewRange()[0]
        
        # 同步组内所有其他通道
        for channel in channels:
            if self.viewboxes[channel] != source_vb:  # 不是源通道才同步
                vb = self.viewboxes[channel]
                # 临时禁用信号防止递归同步
                vb.blockSignals(True)
                vb.setXRange(x_range[0], x_range[1], padding=0)
                vb.blockSignals(False)
    
    def generate_custom_signals(self):
        """生成更真实的 I2C / SPI / UART 数字波形，0/1 阶梯，长度与 self.time 对齐。
        这里扩展了每种协议的数据量（更多字节）以便解码器有更多样本。"""
        t = self.time
        N = t.size
        sr = self.sample_rate

        def square_wave(freq):
            if freq <= 0:
                return np.ones(N)
            period = sr / freq
            idx = (np.arange(N) % int(max(1, period))) < (int(max(1, period)) // 2)
            return idx.astype(float)

        # I2C: SCL + SDA with start/stop and bytes (SCL freq)
        scl_freq = 1000.0
        bit_period_samples = max(1, int(sr / scl_freq))
        scl = square_wave(scl_freq)
        # build SDA: idle high, generate start + bytes + stop
        sda = np.ones(N)
        def gen_i2c_sda(bytes_list):
            ptr = 0
            # start: SDA goes低 while SCL high -> set a cell to 0
            if ptr + bit_period_samples < N:
                sda[ptr:ptr+bit_period_samples] = 1  # pre-start idle
                ptr += bit_period_samples//2
                sda[ptr:ptr+bit_period_samples] = 0
                ptr += bit_period_samples
            for b in bytes_list:
                for bit in range(8):
                    if ptr + bit_period_samples >= N:
                        return
                    sda[ptr:ptr+bit_period_samples] = ((b >> (7-bit)) & 1)
                    ptr += bit_period_samples
                # ACK bit (pull low)
                if ptr + bit_period_samples < N:
                    sda[ptr:ptr+bit_period_samples] = 0
                    ptr += bit_period_samples
            # stop: SDA goes high while SCL high
            if ptr + bit_period_samples < N:
                sda[ptr:ptr+bit_period_samples] = 1

        # 生成更多字节的数据流（例如 256 字节），增加解码样本
        i2c_bytes = [(0x50 + (i & 0xFF)) for i in range(256)]
        gen_i2c_sda(i2c_bytes)

        # SPI: SCK, MOSI aligned to SCK edges, CS pulses low during transfers
        sck_freq = 5000.0
        sck = square_wave(sck_freq)
        samples_per_sck = max(1, int(sr / sck_freq))
        def gen_spi_mosi(byte_seq):
            mosi = np.ones(N)
            ptr = 0
            # CS low for burst
            cs = np.ones(N)
            # 支持多个传输块：每块开始时 CS 拉低，结束后拉高
            gap = samples_per_sck * 2
            block_size = 8  # 每次传输以 8 字节为一块（可调整）
            seq_idx = 0
            while ptr < N and seq_idx < len(byte_seq):
                block_bytes = byte_seq[seq_idx: seq_idx + block_size]
                cs_block = int(samples_per_sck * 8 * len(block_bytes))
                end = min(N, ptr + cs_block)
                # CS 拉低直到 end
                cs[ptr:end] = 0.0
                # place bits aligned to sck samples
                p = ptr
                for b in block_bytes:
                    for bit in range(8):
                        if p + samples_per_sck > N:
                            break
                        mosi[p:p+samples_per_sck] = ((b >> (7-bit)) & 1)
                        p += samples_per_sck
                # after block, advance ptr with a small gap and CS goes high (cs is already ones outside [ptr:end])
                ptr = end + gap
                seq_idx += block_size
            return mosi, cs

        # SPI 生成更多传输块（例如 128 字节），以便解码器能看到多次 CS 脉冲
        spi_bytes = [(0x33 + (i & 0xFF)) for i in range(128)]
        mosi, cs = gen_spi_mosi(spi_bytes)
        miso = np.ones(N)  # idle high

        # UART: 8N1 LSB-first, baud rate
        baud = 115200.0
        spb = max(1, int(sr / baud))  # samples per bit
        def gen_uart(byte_seq):
            tx = np.ones(N)
            ptr = 0
            for b in byte_seq:
                # start bit
                if ptr + spb >= N: break
                tx[ptr:ptr+spb] = 0
                ptr += spb
                # data bits LSB first
                for bit in range(8):
                    if ptr + spb >= N: break
                    tx[ptr:ptr+spb] = ((b >> bit) & 1)
                    ptr += spb
                # stop bit
                if ptr + spb >= N: break
                tx[ptr:ptr+spb] = 1
                ptr += spb
                # small inter-frame gap
                ptr += spb // 2
            return tx

        # UART 生成更多帧（例如 128 字节），包含可打印和不可打印混合
        uart_seq = [0x55, 0x41, 0x42, 0x43, 0x0A, 0x7E] + [i & 0xFF for i in range(0x20, 0x20 + 122)]
        uart_tx = gen_uart(uart_seq)

        # assign to channels (0-based)
        self.channel_data[0] = scl
        self.channel_data[1] = sda
        self.channel_data[2] = sck
        self.channel_data[3] = mosi
        self.channel_data[4] = miso
        self.channel_data[5] = cs
        self.channel_data[6] = uart_tx
        self.channel_data[7] = np.ones(N)  # RX idle

        return

    def update_waveforms(self):
        # 下采样策略：将每通道数据限制为 self.max_plot_points 点
        for i in range(8):
            y = self.channel_data[i]
            if y is None or y.size == 0:
                continue
            n = y.size
            if n > self.max_plot_points:
                factor = int(np.ceil(n / self.max_plot_points))
                y_ds = y[::factor]
                x_ds = self.time[::factor]
            else:
                y_ds = y
                x_ds = self.time

            # 如果曲线是 stepMode，需要 len(x) == len(y)+1
            if getattr(self.curves[i], 'stepMode', True):
                # 为阶梯模式补充一个额外 x 点（重复最后一个）
                if x_ds.size >= 1 and y_ds.size >= 1:
                    x_plot = np.concatenate([x_ds, [x_ds[-1]]])
                else:
                    continue
            else:
                x_plot = x_ds

            # 最小化主线程开销：一次性 setData（pyqtgraph 已做下采样优化）
            try:
                self.curves[i].setData(x_plot, y_ds)
            except Exception:
                # 保护性跳过异常（例如长度不匹配）
                pass

        # 更新解码显示
        # 解码结果写入 UI（只写一次），update_decoder_display 内会检查 _decoded_printed
        self.update_decoder_display()
    
    def update_decoder_display(self):
        """对已生成/捕获的数字信号进行简单协议解析并只打印一次结果（写入 UI 对应文本区）"""
        if self._decoded_printed:
            return

        results = {}
        for proto, chans in self.protocol_groups.items():
            # gather channel arrays
            arrs = [self.channel_data[c].astype(np.int8) for c in chans if c < self.channel_data.shape[0]]
            try:
                parsed = self.parsers.get(proto, lambda a, c: [])(arrs, chans)
            except Exception as e:
                parsed = [f"parse error: {e}"]
            results[proto] = parsed

        # 写入 UI 对应解码区（只写一次）
        try:
            self.i2c_decoder.setPlainText("\n".join(results.get("i2c", ["I2C no data"])))
            self.spi_decoder.setPlainText("\n".join(results.get("spi", ["SPI no data"])))
            self.uart_decoder.setPlainText("\n".join(results.get("uart", ["UART no data"])))
        except Exception:
            # 退回到控制台输出（兼容性保护）
            print("=== Logic Analyzer decode (once) ===")
            for proto, parsed in results.items():
                print(f"[{self.protocol_names.get(proto, proto)}]")
                for line in parsed[:200]:
                    print("  " + line)
            print("=== End decode ===")

        self._decoded_printed = True
        return
    # ================== 公共控制接口 ==================
    def start(self, interval=10):     
        # 每次调用 start 都显示 2 秒启动进度条（如果已有进行中的启动进度则不重复触发）
        self._decoded_printed = False
        if self._start_progress_active:
            # 已有启动进度在进行中，不重复触发
            return

        # 隐藏通道区域，直到进度条完成再显示（无论当前是否已在运行）
        for c in self.channel_containers:
            c.setVisible(False)

        # 重置并显示进度条
        self.start_progress.setValue(0)
        self.start_progress.setVisible(True)
        self._start_progress_active = True

        # 进度总时长 2000ms，分若干步更新
        total_ms = 2000
        step_ms = 50
        step_count = max(1, int(total_ms / step_ms))
        self._start_progress_value = 0.0

        # 定时器周期更新进度
        if self._start_progress_timer is None:
            self._start_progress_timer = QtCore.QTimer(self)
            # 使用 lambda 捕获当前 step_count/step_ms
            self._start_progress_timer.timeout.connect(lambda: self._start_progress_tick(step_count, step_ms))
        self._start_progress_timer.start(step_ms)
        return

    def stop(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        return

    def set_channel_visible(self, channel, visible):
        """设置通道可见性（channel：0-7）"""
        if 0 <= channel < 8:
            self.channel_containers[channel].setVisible(visible)
            # 如果正在运行，立即更新显示
            if self.is_running:
                self.update_waveforms()
    
    def reset_signals(self):
        """重新生成信号（保留100个周期的特性）"""
        self.generate_custom_signals()
        if self.is_running:
            self.update_waveforms()
    
    def _start_progress_tick(self, step_count, interval_ms):
        """进度条定时更新槽（由 QTimer 驱动）"""
        if not hasattr(self, "_start_progress_value"):
            self._start_progress_value = 0.0
        # 增量更新
        try:
            self._start_progress_value += 100.0 / float(step_count)
        except Exception:
            self._start_progress_value = 100.0
        v = int(min(100, self._start_progress_value))
        try:
            self.start_progress.setValue(v)
        except Exception:
            pass
        if v >= 100:
            # 停止进度定时器并隐藏进度条
            if self._start_progress_timer is not None:
                try:
                    self._start_progress_timer.stop()
                except Exception:
                    pass
                self._start_progress_timer = None
            try:
                self.start_progress.setVisible(False)
            except Exception:
                pass
            self._start_progress_active = False
            # 完成真正的启动流程
            self._finalize_start()

    def _finalize_start(self):
        """在进度完成后执行的真正 start 流程（生成信号、显示通道、启动定时器）"""
        # 生成信号（防护）
        try:
            self.generate_custom_signals()
        except Exception:
            pass

        # 应用可见性掩码（外部可通过 set_visibility_mask 提供）
        for idx, vis in enumerate(self.visibility_mask):
            if 0 <= idx < len(self.channel_containers):
                try:
                    self.channel_containers[idx].setVisible(bool(vis))
                except Exception:
                    pass

        self.is_running = True

        # 启动或重启定时器
        if self._timer is None:
            self._timer = QtCore.QTimer(self)
            self._timer.timeout.connect(self.update_waveforms)
            self._timer.start(self.update_interval_ms)

        # 立即执行一次绘制/解码
        try:
            self.update_waveforms()
        except Exception:
            pass

    # ================== 协议解析方法 ==================
    def _parse_i2c(self, arrs, chans):
        """简易 I2C 解析：检测起始、提取字节（在 SCL 的上升中间采样）"""
        if len(arrs) < 2:
            return ["I2C channels missing"]
        scl = arrs[0]
        sda = arrs[1]
        sr = self.sample_rate
        # detect SCL rising edges
        edges = np.where(np.diff(scl.astype(int)) == 1)[0] + 1
        if edges.size == 0:
            return ["No SCL edges"]
        # sample points slightly after edge to read SDA
        samples = edges + max(1, int(sr / (1000.0 * 10)))  # small offset
        samples = samples[samples < sda.size]
        bits = []
        for idx in samples:
            bits.append(int(sda[idx]))
        # group into bytes (MSB-first as generation used)
        bytes_out = []
        for i in range(0, len(bits), 9):  # 8 data + ack
            if i + 8 <= len(bits):
                byte_bits = bits[i:i+8]
                val = 0
                for b in byte_bits:
                    val = (val << 1) | b
                bytes_out.append(val)
        if not bytes_out:
            return ["I2C no bytes decoded"]
        return [f"Byte[{i}]=0x{v:02X}" for i, v in enumerate(bytes_out[:20])]

    def _parse_spi(self, arrs, chans):
        """简易 SPI 解析：在 SCK 上下降沿采样 MOSI，按 8-bit 分组"""
        if len(arrs) < 2:
            return ["SPI channels missing"]
        sck = arrs[0]
        mosi = arrs[1]
        # detect SCK falling edges
        edges = np.where(np.diff(sck.astype(int)) == -1)[0] + 1
        if edges.size == 0:
            return ["No SCK edges"]
        samples = edges  # sample at edge index
        bits = [int(mosi[i]) for i in samples if i < mosi.size]
        bytes_out = []
        for i in range(0, len(bits), 8):
            if i + 8 <= len(bits):
                val = 0
                for bit in bits[i:i+8]:
                    val = (val << 1) | bit
                bytes_out.append(val)
        if not bytes_out:
            return ["SPI no bytes"]
        return [f"Byte[{i}]=0x{v:02X}" for i, v in enumerate(bytes_out[:20])]

    def _parse_uart(self, arrs, chans):
        """简易 UART 解析：检测 start bit (1->0), 按 samples_per_bit 中点采样 8 数据位"""
        if len(arrs) < 1:
            return ["UART channel missing"]
        tx = arrs[0]
        sr = self.sample_rate
        baud = 115200.0
        spb = max(1, int(sr / baud))
        edges = np.where(np.diff(tx.astype(int)) == -1)[0] + 1  # high->low start
        if edges.size == 0:
            return ["No UART frames"]
        bytes_out = []
        for start in edges:
            mid = start + spb//2
            bits = []
            ok = True
            for bit in range(8):
                idx = mid + bit*spb
                if idx >= tx.size:
                    ok = False
                    break
                bits.append(int(tx[idx]))
            if not ok:
                continue
            # LSB first
            val = 0
            for i, b in enumerate(bits):
                val |= (b & 1) << i
            bytes_out.append(val)
            if len(bytes_out) >= 50:
                break
        if not bytes_out:
            return ["UART no bytes"]
        return [f"Byte[{i}]=0x{v:02X} ('{(v if 32<=v<127 else '.')})'" for i, v in enumerate(bytes_out[:20])]