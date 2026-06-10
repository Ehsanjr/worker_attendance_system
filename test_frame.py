import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import QApplication, QLabel, QMainWindow
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap

class TestThread(QThread):
    frame_ready = pyqtSignal(QImage)

    def run(self):
        cap = cv2.VideoCapture("data/videos/1.mp4")  # مسیر ویدیوت رو بذار
        while True:
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resized = cv2.resize(rgb, (640, 480))
            resized = np.ascontiguousarray(resized)
            h, w, ch = resized.shape
            qt_img = QImage(resized.data, w, h, ch * w, QImage.Format_RGB888).copy()
            self.frame_ready.emit(qt_img)
            self.msleep(33)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.label = QLabel()
        self.setCentralWidget(self.label)
        self.resize(640, 480)

        self.thread = TestThread()
        self.thread.frame_ready.connect(self.update_image, Qt.QueuedConnection)
        self.thread.start()

    def update_image(self, qt_img):
        self.label.setPixmap(QPixmap.fromImage(qt_img))

app = QApplication(sys.argv)
w = MainWindow()
w.show()
sys.exit(app.exec_())