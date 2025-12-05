import sys
from PyQt5.QtWidgets import QApplication
from MainWindow import mainwindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = mainwindow()
    win.show() 
    sys.exit(app.exec_())   