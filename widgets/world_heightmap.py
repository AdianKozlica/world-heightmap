from PyQt6.QtWidgets import (
    QPushButton,
    QCheckBox,
    QDialog,
    QLineEdit,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWebEngineWidgets import QWebEngineView
from pathlib import Path
from pyproj import CRS
from PIL import Image
from .upscale import upscale_func

import os
import subprocess
import json
import rasterio
import tempfile
import numpy as np

ROOT = Path(__file__).parent.parent
LEAFLET_HTML_PATH = str(ROOT / "leaflet/leaflet.html")
ETOPO1_PATH = str(ROOT / "data/etopo1.tif")
WATER_MASK_PATH = str(ROOT / "data/gshhs_land_water_mask_3km_i.tif")
RIVERS_PATH = str(ROOT / "data/rivers.tif")


def clip(west: str, south: str, east: str, north: str):
    src_tmp_file = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    water_mask_tmp_file = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)

    rivers_tmp_file = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)

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

    subprocess.call(
        [
            "rio",
            "clip",
            RIVERS_PATH,
            rivers_tmp_file.name,
            "--overwrite",
            "--geographic",
            "--bounds",
            f"{west} {south} {east} {north}",
        ]
    )

    return src_tmp_file.name, water_mask_tmp_file.name, rivers_tmp_file.name


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
    river_path: str,
    out: str,
    make_water_elevation_always_zero=False,
    include_rivers=False,
    min_elevation=float("-inf"),
):
    with (
        rasterio.open(src_path) as src,
        rasterio.open(water_path) as water_mask,
        rasterio.open(river_path) as river_src,
    ):
        data = src.read(1)
        water_data = water_mask.read(1)
        river_data = river_src.read(1)
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

            if make_water_elevation_always_zero and include_rivers:
                upscaled = upscale_func(img, 2).resize((river_src.width, river_src.height))
                upscaled_pixels = upscaled.load()

                for y in range(river_src.height):
                    for x in range(river_src.width):
                        if river_data[y, x] != 0:
                            upscaled_pixels[x, y] = (0, 0, 0)

                upscaled.save(out)
            else:
                img.save(out)

    os.remove(src_path)
    os.remove(water_path)
    os.remove(river_path)


class HeightmapDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__init_ui()

    def __handle_js(self, result: str):
        loaded = json.loads(result)

        west = loaded["_southWest"]["lng"]
        south = loaded["_southWest"]["lat"]
        east = loaded["_northEast"]["lng"]
        north = loaded["_northEast"]["lat"]

        min_elevation = self.__min_elevation.text()

        if min_elevation == "":
            min_elevation = float("-inf")
        else:
            min_elevation = int(min_elevation)

        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save BMP File",
            "",
            "BMP Images (*.bmp)",
        )

        if file_path is None:
            return

        if not file_path.endswith(".bmp"):
            file_path += ".bmp"

        src, water, river = clip(west, south, east, north)
        transform(
            src,
            water,
            river,
            file_path,
            self.__make_water_elevation_always_zero.isChecked(),
            self.__include_rivers.isChecked(),
            min_elevation,
        )

        QMessageBox.information(self, "Success!", "Heightmap has been generated.")

    def __generate_heightmap(self):
        self._web_view.page().runJavaScript(
            "JSON.stringify(map.getBounds());", self.__handle_js
        )

    def __init_ui(self):
        hbox = QHBoxLayout()
        hbox.setSpacing(15)

        self._web_view = QWebEngineView()

        with open(LEAFLET_HTML_PATH, "r") as html:
            code = html.read()

        self._web_view.setHtml(code)
        hbox.addWidget(self._web_view)

        vbox = QVBoxLayout()

        self.__make_water_elevation_always_zero = QCheckBox(
            "Make water elevation always zero"
        )

        self.__include_rivers = QCheckBox("Include rivers")

        generate_btn = QPushButton("Generate")
        generate_btn.clicked.connect(self.__generate_heightmap)

        self.__min_elevation = QLineEdit()
        self.__min_elevation.setPlaceholderText("Min elevation: ")
        self.__min_elevation.setValidator(QIntValidator())

        vbox.addWidget(self.__make_water_elevation_always_zero)
        vbox.addWidget(self.__include_rivers)
        vbox.addWidget(self.__min_elevation)
        vbox.addWidget(generate_btn)

        hbox.addLayout(vbox)

        self.setLayout(hbox)
        self.setFixedSize(700, 350)
        self.setWindowTitle("World heightmap")
