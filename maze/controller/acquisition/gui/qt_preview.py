from __future__ import annotations

try:
    from PySide6.QtGui import QImage, QPixmap

    HAS_QT = True
except ImportError:
    HAS_QT = False
    QImage = None  # type: ignore[assignment]
    QPixmap = None  # type: ignore[assignment]

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def frame_to_pixmap(img):
    """Convert an OpenCV frame into a detached ``QPixmap`` for preview display."""
    if not HAS_QT or not HAS_CV2 or img is None:
        return None
    if img.ndim == 2:
        h, w = img.shape
        qimg = QImage(img.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
    else:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, c = rgb.shape
        qimg = QImage(rgb.data, w, h, w * c, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)
