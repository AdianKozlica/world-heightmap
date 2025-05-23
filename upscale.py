from PyQt6.QtWidgets import QApplication, QWidget, QFileDialog, QPushButton, QLineEdit, QVBoxLayout, QMessageBox
from PyQt6.QtGui import QIntValidator
from PIL import Image, ImageDraw

def upscale(img_path: str, out_path: str, times: int):
    with Image.open(img_path) as orig:
        w, h = orig.size
        pixels = orig.load()
        with Image.new('RGB', (w * times, h * times)) as new:
            draw = ImageDraw.Draw(new)

            for y in range(h):
                for x in range(w):
                    color = pixels[x, y]
                    draw.rectangle((x * times, y * times, x * times + (times - 1), y * times + (times - 1)), fill=color, width=0)
            
            new.save(out_path)

class MainWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.__filename = None
        self.__init_ui()
    
    def __select_file(self):
        options = QFileDialog.Option.ReadOnly
        file_filter = "BMP Images (*.bmp)"
        
        self.__filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select BMP Image File",
            "",
            file_filter,
            options=options
        )

    def __upscale_file(self):
        if self.__filename is None:
            QMessageBox.critical(
                self, "Error!", "You must select a filename!"
            )
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save BMP File",
            "",
            "BMP Images (*.bmp)",
        )

        if file_path is None:
            return
        
        if not file_path.endswith('.bmp'):
            file_path += '.bmp'

        upscale(self.__filename, file_path, int(self.__upscale_factor.text()))
        QMessageBox.information(self, "Success!", "Image has been upscaled!")

    def __init_ui(self):
        vbox = QVBoxLayout()

        select_file = QPushButton('Select File')
        select_file.clicked.connect(self.__select_file)

        run_upscale = QPushButton('Run')
        run_upscale.clicked.connect(self.__upscale_file)

        self.__upscale_factor = QLineEdit()
        self.__upscale_factor.setValidator(QIntValidator())
        self.__upscale_factor.setPlaceholderText('Upscale factor: e.g. 2')

        vbox.addWidget(select_file)
        vbox.addWidget(self.__upscale_factor)
        vbox.addWidget(run_upscale)

        self.setWindowTitle('Upscale')
        self.setFixedSize(200, 100)
        self.setLayout(vbox)

if __name__ == '__main__':
    app = QApplication([])
    main_widget = MainWidget()
    main_widget.show()
    exit(app.exec())

