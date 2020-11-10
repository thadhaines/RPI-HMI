from PySide import QtGui
from ui.mainwindow_012 import MainWindow    # place to update mainwindow code

if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    #QCleanlooksStyle
    app.setStyle("Plastique")
    ui = MainWindow()
    ui.showMaximized()
    sys.exit(app.exec_())

