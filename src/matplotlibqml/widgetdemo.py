import logging
import sys
import time

from PySide6 import QtCore, QtWidgets
import numpy as np
from PySide6.QtCore import qInstallMessageHandler
from matplotlib.figure import Figure

import faulthandler

faulthandler.enable()

from .matplotlibqml import FigureCanvasQTAgg, DemoViewModel, myMessageOutput


class ApplicationWindow(QtWidgets.QMainWindow):
    def __init__(self, vm: DemoViewModel):
        super().__init__()
        self.vm=vm
        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        toolbar = QtWidgets.QHBoxLayout()

        home_btn=QtWidgets.QPushButton(text='home')
        home_btn.clicked.connect(vm.home)
        toolbar.addWidget(home_btn)

        back_btn=QtWidgets.QPushButton(text='back')
        back_btn.clicked.connect(vm.back)
        toolbar.addWidget(back_btn)

        forward_btn=QtWidgets.QPushButton(text='forward')
        forward_btn.clicked.connect(vm.forward)
        toolbar.addWidget(forward_btn)

        pan_btn=QtWidgets.QPushButton(text='pan')
        pan_btn.clicked.connect(vm.pan)
        toolbar.addWidget(pan_btn)

        zoom_btn=QtWidgets.QPushButton(text='zoom')
        zoom_btn.clicked.connect(vm.zoom)
        toolbar.addWidget(zoom_btn)

        pause_chkbtn=QtWidgets.QPushButton(text='pause')
        pause_chkbtn.setCheckable(True)
        pause_chkbtn.toggled.connect(vm.pauseChanged)
        toolbar.addWidget(pause_chkbtn)

        text=QtWidgets.QLabel()
        text.setFixedWidth(128)
        toolbar.addWidget(text)

        vm.coordinatesChanged.connect(lambda x: text.setText(x))

        layout.addLayout(toolbar)

        dynamic_canvas = FigureCanvasQTAgg(Figure(figsize=(5, 3)))
        layout.addWidget(dynamic_canvas)

        vm.updateWithCanvas(canvas=dynamic_canvas, dynamic=True)




if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    qInstallMessageHandler(myMessageOutput)

    # Check whether there is already a running QApplication (e.g., if running
    # from an IDE).
    qapp = QtWidgets.QApplication.instance()
    if not qapp:
        qapp = QtWidgets.QApplication(sys.argv)

    app = ApplicationWindow(vm=DemoViewModel())
    app.show()
    app.activateWindow()
    app.raise_()
    qapp.exec_()