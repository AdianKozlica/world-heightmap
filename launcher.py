#!/usr/bin/python3

from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QVBoxLayout
from PyQt6.QtCore import Qt
from widgets.upscale import UpscaleDialog
from widgets.world_heightmap import HeightmapDialog

import sys


class MainWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__init_ui()

    def __init_ui(self):
        vbox = QVBoxLayout()

        heightmap_button = QPushButton("Heightmap Generator")
        heightmap_button.clicked.connect(lambda: HeightmapDialog(self).exec())

        upscale_button = QPushButton("Upscale")
        upscale_button.clicked.connect(lambda: UpscaleDialog(self).exec())

        label = QLabel("Welcome")
        label.setStyleSheet("QLabel { font-weight: bold; font-size: 20px; } ")

        vbox.addWidget(label, alignment=Qt.AlignmentFlag.AlignHCenter)
        vbox.addWidget(heightmap_button)
        vbox.addWidget(upscale_button)

        self.setLayout(vbox)
        self.setFixedSize(250, 150)
        self.setWindowTitle("Heightmap toolbox")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_widget = MainWidget()
    main_widget.show()
    exit(app.exec())
