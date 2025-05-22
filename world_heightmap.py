from PyQt6.QtWidgets import (
    QApplication,
    QPushButton,
    QLabel,
    QCheckBox,
    QWidget,
    QLineEdit,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtGui import QDoubleValidator, QIntValidator
from PyQt6.QtCore import QLocale
from pathlib import Path
from pyproj import CRS
from PIL import Image

import os
import subprocess
import rasterio
import tempfile
import numpy as np

ROOT = Path(__file__).parent
ETOPO1_PATH = str(ROOT / "data/etopo1.tif")
WATER_MASK_PATH = str(ROOT / "data/gshhs_land_water_mask_3km_i.tif")


def clip(west: str, south: str, east: str, north: str):
    src_tmp_file = tempfile.NamedTemporaryFile(
        suffix=".tif", delete=False, delete_on_close=False
    )
    water_mask_tmp_file = tempfile.NamedTemporaryFile(
        suffix=".tif", delete=False, delete_on_close=False
    )

    subprocess.call(
        [
            "rio",
            "clip",
            ETOPO1_PATH,
            src_tmp_file.name,
            "--overwrite",
            "--geographic",
            "--bounds",
            f"{west} {south} {east} {north}",
        ]
    )
    subprocess.call(
        [
            "rio",
            "clip",
            WATER_MASK_PATH,
            water_mask_tmp_file.name,
            "--overwrite",
            "--geographic",
            "--bounds",
            f"{west} {south} {east} {north}",
        ]
    )

    return src_tmp_file.name, water_mask_tmp_file.name


def xy_to_lat_lon(x: int, y: int, src):
    src_crs = src.crs

    dst_crs = CRS.from_epsg(4326)  # WGS84
    transform = src.transform

    x_coord, y_coord = transform * (x, y)

    if src_crs != dst_crs:
        lon, lat = transform(src_crs, dst_crs, [x_coord], [y_coord])
        lon, lat = lon[0], lat[0]
    else:
        lon, lat = x_coord, y_coord

    return lat, lon


def transform(
    src_path: str,
    water_path: str,
    out: str,
    make_water_elevation_always_zero=False,
    min_elevation=float("-inf"),
):
    with rasterio.open(src_path) as src, rasterio.open(water_path) as water_mask:
        data = src.read(1)
        water_data = water_mask.read(1)
        max_elevation = np.nanmax(data)

        with Image.new("RGB", (water_mask.width, water_mask.height)) as img:
            pixels = img.load()

            for y in range(water_mask.height):
                for x in range(water_mask.width):
                    lat, lon = xy_to_lat_lon(x, y, water_mask)
                    row, col = src.index(lon, lat)
                    elev = max(int(data[row, col]), min_elevation)

                    if make_water_elevation_always_zero:
                        if water_data[y, x] == 0:
                            elev = 0

                    elev = int(255 * (elev / max_elevation))
                    pixels[x, y] = (elev, elev, elev)

            img.save(out)

    os.remove(src_path)
    os.remove(water_path)


class MainWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__init_ui()

    def __generate_heightmap(self):
        west = self.__west.text()
        south = self.__south.text()
        east = self.__east.text()
        north = self.__north.text()

        if west == "" or south == "" or east == "" or north == "":
            QMessageBox.critical(
                self, "Error!", "All fields must be set in bounding box!"
            )
            return

        min_elevation = self.__min_elevation.text()

        if min_elevation == "":
            min_elevation = float("-inf")
        else:
            min_elevation = int(min_elevation)

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save JPEG File",
            "",
            "JPEG Images (*.jpg *.jpeg)",
        )

        if file_path is None:
            return

        src, water = clip(west, south, east, north)
        transform(
            src,
            water,
            file_path,
            self.__make_water_elevation_always_zero.isChecked(),
            min_elevation,
        )
        QMessageBox.information(self, "Success!", "Heightmap has been generated.")

    def __init_ui(self):
        hbox = QHBoxLayout()
        vbox1 = QVBoxLayout()

        lo = QLocale("C")
        lo.setNumberOptions(QLocale.NumberOption.RejectGroupSeparator)

        validator = QDoubleValidator()
        validator.setLocale(lo)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.__west = QLineEdit()
        self.__south = QLineEdit()
        self.__east = QLineEdit()
        self.__north = QLineEdit()

        self.__west.setPlaceholderText("West:")
        self.__west.setValidator(validator)

        self.__south.setPlaceholderText("South:")
        self.__south.setValidator(validator)

        self.__east.setPlaceholderText("East:")
        self.__east.setValidator(validator)

        self.__north.setPlaceholderText("North:")
        self.__north.setValidator(validator)

        vbox1.addWidget(QLabel("Bounding box:"))
        vbox1.addWidget(self.__west)
        vbox1.addWidget(self.__south)
        vbox1.addWidget(self.__east)
        vbox1.addWidget(self.__north)

        hbox.addLayout(vbox1)

        vbox2 = QVBoxLayout()

        self.__make_water_elevation_always_zero = QCheckBox(
            "Make water elevation always zero"
        )

        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.__generate_heightmap)

        self.__min_elevation = QLineEdit()
        self.__min_elevation.setPlaceholderText("Min elevation: ")
        self.__min_elevation.setValidator(QIntValidator())

        vbox2.addWidget(self.__make_water_elevation_always_zero)
        vbox2.addWidget(self.__min_elevation)
        vbox2.addWidget(submit_btn)

        hbox.addLayout(vbox2)

        self.setLayout(hbox)
        self.setFixedSize(400, 150)
        self.setWindowTitle("World heightmap")


if __name__ == "__main__":
    app = QApplication([])
    main_widget = MainWidget()
    main_widget.show()
    exit(app.exec())
