import sys
import os
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5 import uic
import UARTThread
class ConnectDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ui_path = os.path.join(base, 'dialog_setting.ui')
        self.ui = uic.loadUi(ui_path, self)
        self.setWindowTitle('连接设置')
        # 设置默认值
        self.ui.target_ip.setText('192.168.1.10')
        self.ui.target_port.setText('8811')
        self.ui.loc_port.setText('8811')
        self.ui.port_box.addItems(UARTThread.UART_Thread.list_ports())
        # 连接信号与槽
        self.ui.buttonbox.accepted.connect(self.accept)
        self.ui.buttonbox.rejected.connect(self.reject)

    def get_serial_config(self): 
        #    if not self.ui.tabWidget.currentWidget() == self.ui.serial_tab:
        #        return None
           return {
               "port": self.ui.port_box.currentText(),
               "baudrate": self.ui.baudrate_box.currentText(),
               "databits": self.ui.databits_box.currentText(),
               "parity": self.ui.parity_box.currentText(),
               "stopbits": self.ui.stopbits_box.currentText()
           }
    def get_net_config(self):
        #    if not self.ui.tabWidget.currentWidget() == self.ui.net_tab:
        #        return None
           return {
               "target_ip": self.ui.target_ip.text(),
               "target_port": self.ui.target_port.text(),
               "local_port": self.ui.loc_port.text()
               
           }