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
NORMALMAP_STRENGTH = 5


def clip(west: str, south: str, east: str, north: str, path: str):
    src = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)

    subprocess.call(
        [
            "rio",
            "clip",
            path,
            src.name,
            "--overwrite",
            "--geographic",
            "--bounds",
            f"{west} {south} {east} {north}",
        ]
    )

    return src.name

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


def to_normalmap(img: Image.Image):
    with img.convert("L") as heightmap:
        height_array = np.array(heightmap).astype(np.float32) / 255.0

        width, height = heightmap.size
        normal_array = np.zeros((height, width, 3), dtype=np.float32)

        for y in range(1, height - 1):
            for x in range(1, width - 1):
                left = height_array[y, x - 1]
                right = height_array[y, x + 1]
                down = height_array[y + 1, x]
                up = height_array[y - 1, x]

                normal_x = (left - right) * NORMALMAP_STRENGTH
                normal_y = (down - up) * NORMALMAP_STRENGTH

                normal_z = 1.0

                normal = np.array([normal_x, normal_y, normal_z])
                normal = normal / np.linalg.norm(normal)  # Normalize

                normal_array[y, x] = (normal * 0.5 + 0.5) * 255

        return Image.fromarray(normal_array.astype(np.uint8))

def transform_without_water_mask(src_path: str, out: str, is_normalmap=False, min_elevation=float("-inf")):
    with rasterio.open(src_path) as src:
        data = src.read(1)
        max_elevation = np.nanmax(data)

        with Image.new('RGB', (src.width, src.height)) as img:
            pixels = img.load()
            
            for y in range(src.height):
                for x in range(src.width):
                    elev = max(int(data[y, x]), min_elevation)

                    elev = int(255 * (elev / max_elevation))
                    pixels[x, y] = (elev, elev, elev)
            
            if is_normalmap:
                to_normalmap(img).save(out)
            else:
                img.save(out)
    
    os.remove(src_path)

def transform_with_water_mask(
    src_path: str,
    water_path: str,
    river_path: str | None,
    out: str,
    make_water_elevation_always_zero=False,
    include_rivers=False,
    is_normalmap=False,
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

            out_img = img

            if make_water_elevation_always_zero and include_rivers:
                with rasterio.open(river_path) as river_src:
                    river_data = river_src.read(1)

                    upscaled = upscale_func(img, 2).resize(
                        (river_src.width, river_src.height)
                    )

                    upscaled_pixels = upscaled.load()

                    for y in range(river_src.height):
                        for x in range(river_src.width):
                            if river_data[y, x] != 0:
                                upscaled_pixels[x, y] = (0, 0, 0)

                    out_img = upscaled

            if is_normalmap:
                out_img = to_normalmap(out_img)

            out_img.save(out)

    os.remove(src_path)
    os.remove(water_path)
    
    if river_path is not None:
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

        src = clip(west, south, east, north, ETOPO1_PATH)

        if not self.__make_water_elevation_always_zero.isChecked():
            transform_without_water_mask(src, file_path, self.__is_normalmap.isChecked(), min_elevation)
            QMessageBox.information(self, "Success!", "Heightmap has been generated.")
            return

        water = clip(west, south, east, north, WATER_MASK_PATH)
        river = clip(west, south, east, north, RIVERS_PATH) if self.__include_rivers.isChecked() else None

        transform_with_water_mask(
            src,
            water,
            river,
            file_path,
            self.__make_water_elevation_always_zero.isChecked(),
            self.__include_rivers.isChecked(),
            self.__is_normalmap.isChecked(),
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
        self.__is_normalmap = QCheckBox("Is normal mapped")

        generate_btn = QPushButton("Generate")
        generate_btn.clicked.connect(self.__generate_heightmap)

        self.__min_elevation = QLineEdit()
        self.__min_elevation.setPlaceholderText("Min elevation: ")
        self.__min_elevation.setValidator(QIntValidator())

        vbox.addWidget(self.__make_water_elevation_always_zero)
        vbox.addWidget(self.__include_rivers)
        vbox.addWidget(self.__min_elevation)
        vbox.addWidget(self.__is_normalmap)
        vbox.addWidget(generate_btn)

        hbox.addLayout(vbox)

        self.setLayout(hbox)
        self.setFixedSize(700, 350)
        self.setWindowTitle("World heightmap")
