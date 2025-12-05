# ...existing code...
from PyQt5.QtCore import QThread, pyqtSignal
import serial
import serial.tools.list_ports
import threading
import time

class UART_Thread(QThread):
    """
    基本串口类（基于 pyserial + QThread）。
    信号:
      - data_received(bytes)
      - error(str)
      - opened()
      - closed()
    用法:
      uart = UARTThread()
      uart.open_port('COM3', 115200)
      uart.data_received.connect(handler)
      uart.write(b'hello')
      uart.close_port()
    """
    data_received = pyqtSignal(bytes)
    error = pyqtSignal(str)
    opened = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self,serial_config=None):
        super().__init__()
        self.serial = None
        self._is_running = False
        self._lock = threading.Lock()
        self.config=serial_config
        self._read_sleep = 0.01  # 空闲读间隔

    @staticmethod
    def list_ports():
        """返回可用串口列表: ['COM1', 'COM2', ...]"""
        return [p.device for p in serial.tools.list_ports.comports()]

    def open_port(self,timeout=0.1):
        """打开串口并启动读取线程"""
        with self._lock:
            try:
                if self.serial and self.serial.is_open:
                    self.serial.close()
                self.serial = serial.Serial(port=self.config.get("port"), baudrate=self.config.get("baudrate"), timeout=timeout)
                self._is_running = True
                if not self.isRunning():
                    self.start()
                self.opened.emit()
            except Exception as e:
                self.error.emit(f"打开串口失败: {e}")

    def close_port(self):
        """停止读取并关闭串口"""
        with self._lock:
            self._is_running = False
            try:
                if self.serial:
                    try:
                        self.serial.flush()
                    except Exception:
                        pass
                    try:
                        self.serial.close()
                    except Exception:
                        pass
                    self.serial = None
                self.closed.emit()
            except Exception as e:
                self.error.emit(f"关闭串口失败: {e}")

    def write(self, data: bytes):
        """向串口写入 bytes"""
        with self._lock:
            if not self.serial or not self.serial.is_open:
                self.error.emit("写入失败：串口未打开")
                print("写入失败：串口未打开")
                return
            try:
                self.serial.write(data)
                print(f"写入串口数据: {data.hex()}")
                self.serial.flush()
            except Exception as e:
                self.error.emit(f"写入串口失败: {e}")

    def run(self):
        """线程读取循环，读取到数据后通过 data_received 发射"""
        while True:
            with self._lock:
                if not self._is_running:
                    break
                ser = self.serial
            if not ser or not ser.is_open:
                time.sleep(self._read_sleep)
                continue
            try:
                # 先检查缓冲区
                n = ser.in_waiting if hasattr(ser, 'in_waiting') else 0
                if n:
                    data = ser.read(n)
                else:
                    # 读取 1 字节（阻塞时间受 timeout 控制）
                    data = ser.read(1)
                if data:
                    self.data_received.emit(data)
                else:
                    time.sleep(self._read_sleep)
            except Exception as e:
                self.error.emit(f"读取串口异常: {e}")
                # 出错后短暂休眠避免忙循环
                time.sleep(0.1)
        # 线程退出时确保串口已关闭
        with self._lock:
            try:
                if self.serial and self.serial.is_open:
                    self.serial.close()
                    self.serial = None
            except Exception:
                pass

    def stop(self):
        """外部停止线程（等同于 close_port，但不触发 closed 信号重复）"""
        with self._lock:
            self._is_running = False
        # 等待线程结束
        if self.isRunning():
            self.quit()
            self.wait()