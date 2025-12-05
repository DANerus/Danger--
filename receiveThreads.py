from PyQt5.QtCore import QThread, pyqtSignal
import socket
import struct
import numpy as np
from scipy.signal import find_peaks, resample, resample_poly
from math import gcd
import time
class UdpReceiverThread(QThread):
    data_received = pyqtSignal(list)

    def __init__(self, udp_config):
        super().__init__()
        self.config = udp_config
        self.acquiring = False
        # 仅保留通道选择配置（UI 侧将去掉采样点数、分频等）
        self.parsing_config = {
            "channels": [False, False]
        }
        # 平滑滤波配置：可由 udp_config 中的 'smoothing' 覆盖
        # 示例: {'method':'moving_average','window':5} 或 {'method':'savitzky_golay','window':7,'poly':2}
        if self.config and isinstance(self.config, dict):
            self.smoothing_config = self.config.get('smoothing', {'method': 'moving_average', 'window': 5})
        else:
            self.smoothing_config = {'method': 'moving_average', 'window': 5}

        self.socket = None
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.is_running = True
        # --- ADC 位宽相关（8位有符号） ---
        self.ADC_DATA_WIDTH = 8
        self.VOL_RANGE = 5.0
        self.LSB = (self.VOL_RANGE * 2) / (2 ** self.ADC_DATA_WIDTH)
        self.SIGN_THRESHOLD = 2 ** (self.ADC_DATA_WIDTH - 1)
        self.FULL_RANGE = 2 ** self.ADC_DATA_WIDTH
        self.voltage_ch1=[]
        self.voltage_ch2=[]
    def build_channel_config_command(self):
        chans = self.parsing_config.get("channels", [False, False])
        mask = 0
        for i, en in enumerate(chans):
            if en:
                mask |= (1 << i)
        cmd = b'CHCFG' + bytes([mask])
        # 仅打印/返回占位字节，具体协议由用户替换
        print(f"准备发送 通道配置 指令: {cmd.hex()}")
        return cmd

    # def build_start_command(self):
    #     """
    #     构造开始采集指令（占位），请根据下位机协议替换实现。
    #     """
    #     cmd = b'\x07'
    #     print(f"准备发送 开始采集 指令: {cmd.hex()}")
    #     return cmd

    def send_command(self, cmd_bytes):
        """
        通过 UDP 发送指令到下位机。依赖 self.config 中的 device_ip/device_port。
        若未提供，则打印警告。
        """
        ip = self.config.get('target_ip')
        port = int(self.config.get('target_port') or 0)
        if not ip or port == 0:
            print("警告：目标ip 或 目标端口 未配置，无法发送指令。")
            return
        try:
            self.send_socket.sendto(cmd_bytes, (ip, port))
            # print(f"已发送指令到 {ip}:{port} -> {cmd_bytes.hex()}")
        except Exception as e:
            print(f"发送指令失败: {e}")

    def start_acquisition(self, parsing_config=None):
        """
        由 UI 调用以开始处理下位机持续发送的数据，并发送通道配置 + 开始指令。
        parsing_config 可选，用于在调用时覆盖当前 self.parsing_config。
        """
        # 如果调用时传入新的通道配置，则先更新
        if parsing_config:
            self.parsing_config = parsing_config

        # # 发送通道配置指令（占位）
        # ch_cmd = self.build_channel_config_command()
        # self.send_command(ch_cmd)

        # 发送开始采集指令（占位）
        # start_cmd = b'\x01'
        # self.send_command(start_cmd)
        # time.sleep(2)
        # start_cmd = b'\x07'
        # self.send_command(start_cmd)        
        # 设置标志，允许 run() 开始处理接收到的数据
        self.acquiring = True
        print("采集标志已设置: acquiring = True")
        
    def stop_acquisition(self):
        """
        # 由 UI 调用以停止处理数据（线程仍可继续运行监听或被 stop() 停止）。
        # 停止采集由 acquiring 控制且会发送停止指令。
        # """
        # # 发送停止指令（占位）
        # stop_cmd = b'\x00'
        # self.send_command(stop_cmd)

        # 清除采集标志，run() 将停止处理数据
        self.acquiring = False
        print("采集标志已清除: acquiring = False")
    def send_trigger_config(self,trig_config):
        #self.trig_config=trig_config
        voltage = struct.pack('!I', int(trig_config.get("voltage", 0)) & 0xFFFFFFFF)
        edge = struct.pack('!I', int(trig_config.get("edge", 0)) & 0xFFFFFFFF)
        header = bytes.fromhex('09aabbcc00000000')
        tail= bytes.fromhex('09ddeeff')
        cmd = header + voltage + edge + tail
        #print(f"准备发送 触发配置 指令: {cmd.hex()}")
        self.send_command(cmd)
    def smooth_raw_codes(self, raw_codes):
        """
        对原始码值列表做平滑处理，返回 float 列表。
        支持方法: moving_average, median, savitzky_golay, none
        """
        if not raw_codes:
            return []

        cfg = self.smoothing_config or {}
        method = cfg.get('method', 'moving_average')
        try:
            win = int(cfg.get('window', 5))
        except Exception:
            win = 5
        if win <= 1 or method == 'none':
            return list(raw_codes)

        arr = np.asarray(raw_codes, dtype=float)

        if method == 'moving_average':
            kernel = np.ones(win) / win
            sm = np.convolve(arr, kernel, mode='same')
            return sm.tolist()
        elif method == 'median':
            try:
                from scipy.signal import medfilt
                k = win if win % 2 == 1 else win + 1
                sm = medfilt(arr, kernel_size=k)
                return sm.tolist()
            except Exception:
                kernel = np.ones(win) / win
                sm = np.convolve(arr, kernel, mode='same')
                return sm.tolist()
        elif method == 'savitzky_golay':
            try:
                from scipy.signal import savgol_filter
                poly = int(cfg.get('poly', 2))
                window = win if win % 2 == 1 else win + 1
                if window <= poly:
                    window = poly + 1 if (poly + 1) % 2 == 1 else poly + 2
                sm = savgol_filter(arr, window_length=window, polyorder=poly)
                return sm.tolist()
            except Exception:
                kernel = np.ones(win) / win
                sm = np.convolve(arr, kernel, mode='same')
                return sm.tolist()
        else:
            return list(raw_codes)
    def run(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_port = int(self.config.get('local_port', 0) or 0)
            if local_port == 0:
                print("错误：local_port 未配置，线程无法绑定。")
                return
            self.socket.bind(('', local_port))
            self.socket.settimeout(1.0)
            print(f"UDP线程启动，正在监听端口: {local_port}")
        except Exception as e:
            print(f"错误：无法绑定到端口 {self.config.get('local_port')}. {e}")
            return

        while self.is_running:
            try:
                data_bytes, addr = self.socket.recvfrom(8192)  # 解包：取出 bytes 部分
                #print(f"接收到 波形包，数据点数: {data_bytes}")
                if not data_bytes:
                    continue
                # 由 self.acquiring 决定是否处理数据
                if not self.acquiring:
                    # 丢弃数据并继续循环，保持线程监听状态
                    continue
                #波形数据包
                if (data_bytes[0]==0x01):
                    payload = data_bytes[8:-40]
                    raw_codes =[b -120 for b in payload]
                    # 对 raw_codes 做平滑处理
                    try:
                        smoothed_codes = self.smooth_raw_codes(raw_codes)
                    except Exception as e:
                        print(f"平滑处理失败，使用原始数据: {e}")
                        smoothed_codes = raw_codes
                    self.LSB = (self.VOL_RANGE * 2) / (2 ** self.ADC_DATA_WIDTH)
                    #self.voltages_raw = [code * self.LSB for code in raw_codes]
                    self.voltages_smoothed = [code * self.LSB for code in smoothed_codes]
                    print(f"接收到 波形包 {self.voltages_smoothed}")
                    self.voltage_ch1.clear()
                    self.voltage_ch2.clear()
                    # for i in range(len(self.voltages_smoothed)):
                    #     if i%2==0:
                    #         self.voltage_ch1.append(self.voltages_raw[i])
                    #     else:
                    #         self.voltage_ch2.append(self.voltages_raw[i])
                    rawcodes_2=[b for b in payload]
                    smoothed_codes = self.smooth_raw_codes(rawcodes_2)
                    self.voltages_smoothed_2 = [code * self.LSB for code in smoothed_codes]
                    # 发射解码后的数据
                    #self.data_received.emit(['wave', self.voltage_ch1,self.voltage_ch2])
                    self.data_received.emit(['wave', self.voltages_smoothed*20,self.voltages_smoothed_2*20])
                    continue
                # 状态数据包
                if (len(data_bytes)>=6 
                    and data_bytes[0]==0x03 
                    and data_bytes[-1]==0xFF):
                    try:
                        duty=data_bytes[3] if len(data_bytes)>=4 else 0 
                        high_time = int.from_bytes(data_bytes[4:7], 'big') if len(data_bytes) >= 7 else 0
                        low_time = int.from_bytes(data_bytes[7:10], 'big') if len(data_bytes) >= 10 else 0
                        frequency = data_bytes[10] if len(data_bytes) >= 11 else 0
                        status = [ duty, high_time, low_time, frequency]
                        self.data_received.emit(['status', status])
                        print(f"接收到 状态包: {data_bytes}")
                    except Exception:
                        print("解析状态失败")
                    continue        
            except socket.timeout:
                continue
            except Exception as e:
                print(f"接收或解码数据时出错: {e}")
    def stop(self):
        """停止线程并关闭 socket"""
        self.is_running = False
        # 在完全停止线程前确保已停止采集
        if self.acquiring:
            try:
                self.stop_acquisition()
            except Exception:
                pass

        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        if self.send_socket:
            try:
                self.send_socket.close()
            except Exception:
                pass
        self.quit()
        self.wait()