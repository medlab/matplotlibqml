import logging
import operator
import os
import sys
import time
import traceback
from pathlib import Path

import matplotlib
import matplotlib as mpl
import numpy as np
from PySide6 import QtCore, QtGui, QtQuick, QtWidgets
from PySide6.QtCore import Qt, qInstallMessageHandler, QMessageLogContext, QtMsgType

from matplotlib import cbook, _api
from matplotlib.backend_bases import FigureCanvasBase, NavigationToolbar2, MouseButton, TimerBase
from matplotlib.backend_tools import cursors
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.transforms import Bbox

class TimerQT(TimerBase):
    """Subclass of `.TimerBase` using QTimer events."""

    def __init__(self, *args, **kwargs):
        # Create a new timer and connect the timeout() signal to the
        # _on_timer method.
        self._timer = QtCore.QTimer()
        self._timer.timeout.connect(self._on_timer)
        super().__init__(*args, **kwargs)

    def __del__(self):
        # The check for deletedness is needed to avoid an error at animation
        # shutdown with PySide2.
        # if not _isdeleted(self._timer):
        #    self._timer_stop()
        self._timer_stop()

    def _timer_set_single_shot(self):
        self._timer.setSingleShot(self._single)

    def _timer_set_interval(self):
        self._timer.setInterval(self._interval)

    def _timer_start(self):
        self._timer.start()

    def _timer_stop(self):
        self._timer.stop()

SPECIAL_KEYS = {
        QtCore.Qt.Key.Key_Escape: "escape",
        QtCore.Qt.Key.Key_Tab: "tab",
        QtCore.Qt.Key.Key_Backspace: "backspace",
        QtCore.Qt.Key.Key_Return: "enter",
        QtCore.Qt.Key.Key_Enter: "enter",
        QtCore.Qt.Key.Key_Insert: "insert",
        QtCore.Qt.Key.Key_Delete: "delete",
        QtCore.Qt.Key.Key_Pause: "pause",
        QtCore.Qt.Key.Key_SysReq: "sysreq",
        QtCore.Qt.Key.Key_Clear: "clear",
        QtCore.Qt.Key.Key_Home: "home",
        QtCore.Qt.Key.Key_End: "end",
        QtCore.Qt.Key.Key_Left: "left",
        QtCore.Qt.Key.Key_Up: "up",
        QtCore.Qt.Key.Key_Right: "right",
        QtCore.Qt.Key.Key_Down: "down",
        QtCore.Qt.Key.Key_PageUp: "pageup",
        QtCore.Qt.Key.Key_PageDown: "pagedown",
        QtCore.Qt.Key.Key_Shift: "shift",
        # In OSX, the control and super (aka cmd/apple) keys are switched.
        QtCore.Qt.Key.Key_Control: "control" if sys.platform != "darwin" else "cmd",
        QtCore.Qt.Key.Key_Meta: "meta" if sys.platform != "darwin" else "control",
        QtCore.Qt.Key.Key_Alt: "alt",
        QtCore.Qt.Key.Key_CapsLock: "caps_lock",
        QtCore.Qt.Key.Key_F1: "f1",
        QtCore.Qt.Key.Key_F2: "f2",
        QtCore.Qt.Key.Key_F3: "f3",
        QtCore.Qt.Key.Key_F4: "f4",
        QtCore.Qt.Key.Key_F5: "f5",
        QtCore.Qt.Key.Key_F6: "f6",
        QtCore.Qt.Key.Key_F7: "f7",
        QtCore.Qt.Key.Key_F8: "f8",
        QtCore.Qt.Key.Key_F9: "f9",
        QtCore.Qt.Key.Key_F10: "f10",
        QtCore.Qt.Key.Key_F10: "f11",
        QtCore.Qt.Key.Key_F12: "f12",
        QtCore.Qt.Key.Key_Super_L: "super",
        QtCore.Qt.Key.Key_Super_R: "super",
}

# SPECIAL_KEYS are Qt::Key that do *not* return their unicode name
# instead they have manually specified names.
MODIFIER_KEYS=[
    ("control" if sys.platform != "darwin" else "cmd",  Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_Control),
    ("alt" ,                                            Qt.KeyboardModifier.AltModifier,     Qt.Key.Key_Alt),
    ("shift",                                           Qt.KeyboardModifier.ShiftModifier,   Qt.Key.Key_Shift),
    ("meta" if sys.platform != "darwin" else "control", Qt.KeyboardModifier.MetaModifier,    Qt.Key.Key_Meta)
]

cursord = {
        cursors.MOVE:QtCore.Qt.CursorShape.SizeAllCursor,
        cursors.HAND:QtCore.Qt.CursorShape.PointingHandCursor,
        cursors.POINTER:QtCore.Qt.CursorShape.ArrowCursor,
        cursors.SELECT_REGION:QtCore.Qt.CursorShape.CrossCursor,
        cursors.WAIT:QtCore.Qt.CursorShape.WaitCursor,
}

# map Qt button codes to MouseEvent's ones:
buttond = {QtCore.Qt.LeftButton: MouseButton.LEFT,
           QtCore.Qt.MiddleButton: MouseButton.MIDDLE,
           QtCore.Qt.RightButton: MouseButton.RIGHT,
           QtCore.Qt.XButton1: MouseButton.BACK,
           QtCore.Qt.XButton2: MouseButton.FORWARD,
           }

_getSaveFileName = QtWidgets.QFileDialog.getSaveFileName


def _exec(obj):
    # exec on PyQt6, exec_ elsewhere.
    obj.exec() if hasattr(obj, "exec") else obj.exec_()


def _devicePixelRatioF(obj):
    """
    Return obj.devicePixelRatioF() with graceful fallback for older Qt.

    This can be replaced by the direct call when we require Qt>=5.6.
    """
    try:
        # Not available on Qt<5.6
        return obj.devicePixelRatioF() or 1
    except AttributeError:
        pass
    try:
        # Not available on Qt4 or some older Qt5.
        # self.devicePixelRatio() returns 0 in rare cases
        return obj.devicePixelRatio() or 1
    except AttributeError:
        return 1


def _setDevicePixelRatio(obj, val):
    """
    Call obj.setDevicePixelRatio(val) with graceful fallback for older Qt.

    This can be replaced by the direct call when we require Qt>=5.6.
    """
    if hasattr(obj, 'setDevicePixelRatio'):
        # Not available on Qt4 or some older Qt5.
        obj.setDevicePixelRatio(val)


class MatplotlibIconProvider(QtQuick.QQuickImageProvider):
    """ This class provide the matplotlib icons for the navigation toolbar.
    """

    def __init__(self, img_type=QtQuick.QQuickImageProvider.Image):
        self.basedir = os.path.join(matplotlib.rcParams['datapath'], 'images')
        QtQuick.QQuickImageProvider.__init__(self, img_type)

    def requestImage(self, ids, size, reqSize):
        img = QtGui.QImage(os.path.join(self.basedir, ids + '.png'))
        size.setWidth(img.width())
        size.setHeight(img.height())
        return img


class NavigationToolbar2QtQuick(QtCore.QObject, NavigationToolbar2):
    """ NavigationToolbar2 customized for QtQuick
    """

    messageChanged = QtCore.Signal(str)

    leftChanged = QtCore.Signal()
    rightChanged = QtCore.Signal()
    topChanged = QtCore.Signal()
    bottomChanged = QtCore.Signal()
    wspaceChanged = QtCore.Signal()
    hspaceChanged = QtCore.Signal()

    def __init__(self, canvas, parent=None):

        # I think this is needed due to a bug in PySide2
        # if QT_API == QT_API_PYSIDE2:
        #     QtCore.QObject.__init__(self, parent)
        #     NavigationToolbar2.__init__(self, canvas)
        # else:
        #     super().__init__(canvas=canvas, parent=parent)
        QtCore.QObject.__init__(self, parent)
        NavigationToolbar2.__init__(self, canvas)

        self._message = ""

        #
        # Store margin
        #
        self._defaults = {}
        for attr in ('left', 'bottom', 'right', 'top', 'wspace', 'hspace', ):
            val = getattr(self.canvas.figure.subplotpars, attr)
            self._defaults[attr] = val
            setattr(self, attr, val)

    def _init_toolbar(self):
        """ don't actually build the widgets here, build them in QML
        """
        pass

    # Define a few properties.
    def getMessage(self):
        return self._message

    def setMessage(self, msg):
        if msg != self._message:
            self._message = msg
            self.messageChanged.emit(msg)

    message = QtCore.Property(str, getMessage, setMessage,
                              notify=messageChanged)

    def getLeft(self):
        return self.canvas.figure.subplotpars.left

    def setLeft(self, value):
        if value != self.canvas.figure.subplotpars.left:
            self.canvas.figure.subplots_adjust(left=value)
            self.leftChanged.emit()

            self.canvas.draw_idle()

    left = QtCore.Property(float, getLeft, setLeft, notify=leftChanged)

    def getRight(self):
        return self.canvas.figure.subplotpars.right

    def setRight(self, value):
        if value != self.canvas.figure.subplotpars.right:
            self.canvas.figure.subplots_adjust(right=value)
            self.rightChanged.emit()

            self.canvas.draw_idle()

    right = QtCore.Property(float, getRight, setRight, notify=rightChanged)

    def getTop(self):
        return self.canvas.figure.subplotpars.top

    def setTop(self, value):
        if value != self.canvas.figure.subplotpars.top:
            self.canvas.figure.subplots_adjust(top=value)
            self.topChanged.emit()

            self.canvas.draw_idle()

    top = QtCore.Property(float, getTop, setTop, notify=topChanged)

    def getBottom(self):
        return self.canvas.figure.subplotpars.bottom

    def setBottom(self, value):
        if value != self.canvas.figure.subplotpars.bottom:
            self.canvas.figure.subplots_adjust(bottom=value)
            self.bottomChanged.emit()

            self.canvas.draw_idle()

    bottom = QtCore.Property(float, getBottom, setBottom, notify=bottomChanged)

    def getHspace(self):
        return self.canvas.figure.subplotpars.hspace

    def setHspace(self, value):
        if value != self.canvas.figure.subplotpars.hspace:
            self.canvas.figure.subplots_adjust(hspace=value)
            self.hspaceChanged.emit()

            self.canvas.draw_idle()

    hspace = QtCore.Property(float, getHspace, setHspace, notify=hspaceChanged)

    def getWspace(self):
        return self.canvas.figure.subplotpars.wspace

    def setWspace(self, value):
        if value != self.canvas.figure.subplotpars.wspace:
            self.canvas.figure.subplots_adjust(wspace=value)
            self.wspaceChanged.emit()

            self.canvas.draw_idle()

    wspace = QtCore.Property(float, getWspace, setWspace, notify=wspaceChanged)

    def set_history_buttons(self):
        """Enable or disable back/forward button"""
        pass

    def set_cursor(self, cursor):
        """
        Set the current cursor to one of the :class:`Cursors`
        enums values
        """
        self.canvas.setCursor(cursord[cursor])

    def draw_with_locators_update(self):
        """Redraw the canvases, update the locators"""
        for a in self.canvas.figure.get_axes():
            xaxis = getattr(a, 'xaxis', None)
            yaxis = getattr(a, 'yaxis', None)
            locators = []
            if xaxis is not None:
                locators.append(xaxis.get_major_locator())
                locators.append(xaxis.get_minor_locator())
            if yaxis is not None:
                locators.append(yaxis.get_major_locator())
                locators.append(yaxis.get_minor_locator())

            for loc in locators:
                loc.refresh()
        self.canvas.draw_idle()

    def draw_rubberband(self, event, x0, y0, x1, y1):
        """Draw a rectangle rubberband to indicate zoom limits"""
        height = self.canvas.figure.bbox.height
        y1 = height - y1
        y0 = height - y0

        w = abs(x1 - x0)
        h = abs(y1 - y0)

        rect = [int(val)for val in (min(x0, x1), min(y0, y1), w, h)]
        self.canvas.drawRectangle(rect)

    def remove_rubberband(self):
        """Remove the rubberband"""
        self.canvas.drawRectangle(None)

    def tight_layout(self):
        self.canvas.figure.tight_layout()
        # self._setSliderPositions()
        self.canvas.draw_idle()

    def reset_margin(self):
        self.canvas.figure.subplots_adjust(**self._defaults)
        # self._setSliderPositions()
        self.canvas.draw_idle()

    def print_figure(self, fname, *args, **kwargs):
        if fname:
            fname = QtCore.QUrl(fname).toLocalFile()
            # save dir for next time
            matplotlib.rcParams['savefig.directory'] = os.path.dirname(fname)
        NavigationToolbar2.print_figure(self, fname, *args, **kwargs)
        self.canvas.draw_idle()

    def save_figure(self, *args):
        raise NotImplementedError("save_figure is not yet implemented")

class FigureCanvasQtQuick(QtQuick.QQuickPaintedItem, FigureCanvasBase):
    """ This class creates a QtQuick Item encapsulating a Matplotlib
        Figure and all the functions to interact with the 'standard'
        Matplotlib navigation toolbar.
    """

    dpi_ratio_changed = QtCore.Signal()



    def __init__(self, figure=None, parent=None):
        if figure is None:
            figure = Figure((6.0, 4.0))

        # It seems like Qt doesn't implement cooperative inheritance
        QtQuick.QQuickPaintedItem.__init__(self, parent=parent)
        FigureCanvasBase.__init__(self, figure=figure)

        # The dpi ratio (property without leading _)
        self._dpi_ratio = 1

        # Activate hover events and mouse press events
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(QtCore.Qt.AllButtons)
        self.setAntialiasing(True)
        # We don't want to scale up the figure DPI more than once.
        # Note, we don't handle a signal for changing DPI yet.
        figure._original_dpi = figure.dpi
        self._update_figure_dpi()
        # In cases with mixed resolution displays, we need to be careful if the
        # dpi_ratio changes - in this case we need to resize the canvas
        # accordingly. We could watch for screenChanged events from Qt, but
        # the issue is that we can't guarantee this will be emitted *before*
        # the first paintEvent for the canvas, so instead we keep track of the
        # dpi_ratio value here and in paintEvent we resize the canvas if
        # needed.

        self._draw_pending = False
        self._is_drawing = False
        self._draw_rect_callback = lambda painter: None

        self.resize(*self.get_width_height())

    def _update_figure_dpi(self):
        dpi = self.dpi_ratio * self.figure._original_dpi
        self.figure._set_dpi(dpi, forward=False)

    # property exposed to Qt
    def get_dpi_ratio(self):
        return self._dpi_ratio

    def boundingRect(self):
        return QtCore.QRectF(0, 0, self.width(), self.height())

    def set_dpi_ratio(self, new_ratio):
        # As described in __init__ above, we need to be careful in cases with
        # mixed resolution displays if dpi_ratio is changing between painting
        # events.
        # Return whether we triggered a resizeEvent (and thus a paintEvent)
        # from within this function.
        if new_ratio != self._dpi_ratio:
            self._dpi_ratio = new_ratio
            # We need to update the figure DPI.
            self._update_figure_dpi()
            # The easiest way to resize the canvas is to emit a resizeEvent
            # since we implement all the logic for resizing the canvas for
            # that event.
            self.geometryChanged(self.boundingRect(), self.boundingRect())
            # resizeEvent triggers a paintEvent itself, so we exit this one
            # (after making sure that the event is immediately handled).

    dpi_ratio = QtCore.Property(float,
                                get_dpi_ratio,
                                set_dpi_ratio,
                                notify=dpi_ratio_changed)

    def get_width_height(self):
        w, h = FigureCanvasBase.get_width_height(self)
        return int(w / self.dpi_ratio), int(h / self.dpi_ratio)

    def drawRectangle(self, rect):
        # Draw the zoom rectangle to the QPainter.  _draw_rect_callback needs
        # to be called at the end of paintEvent.
        if rect is not None:
            def _draw_rect_callback(painter):
                pen = QtGui.QPen(QtCore.Qt.black, 1 / self.dpi_ratio,
                                 QtCore.Qt.DotLine)
                painter.setPen(pen)
                painter.drawRect(*(pt / self.dpi_ratio for pt in rect))
        else:
            def _draw_rect_callback(painter):
                return
        self._draw_rect_callback = _draw_rect_callback
        self.update()

    def draw(self):
        """Render the figure, and queue a request for a Qt draw.
        """
        # The renderer draw is done here; delaying causes problems with code
        # that uses the result of the draw() to update plot elements.
        if self._is_drawing:
            return
        with cbook._setattr_cm(self, _is_drawing=True):
            super().draw()
        self.update()

    def draw_idle(self):
        """
        Queue redraw of the Agg buffer and request Qt paintEvent.
        """
        # The Agg draw needs to be handled by the same thread matplotlib
        # modifies the scene graph from. Post Agg draw request to the
        # current event loop in order to ensure thread affinity and to
        # accumulate multiple draw requests from event handling.
        # TODO: queued signal connection might be safer than singleShot
        if not (getattr(self, '_draw_pending', False) or
                getattr(self, '_is_drawing', False)):
            self._draw_pending = True
            QtCore.QTimer.singleShot(0, self._draw_idle)

    def _draw_idle(self):
        with self._idle_draw_cntx():
            if not self._draw_pending:
                return
            self._draw_pending = False
            if self.height() < 0 or self.width() < 0:
                return
            try:
                self.draw()
            except Exception:
                # Uncaught exceptions are fatal for PyQt5, so catch them.
                traceback.print_exc()

    def geometryChanged(self, new_geometry, old_geometry):
        w = new_geometry.width() * self.dpi_ratio
        h = new_geometry.height() * self.dpi_ratio

        if (w <= 0.0) or (h <= 0.0):
            return

        dpival = self.figure.dpi
        winch = w / dpival
        hinch = h / dpival
        self.figure.set_size_inches(winch, hinch, forward=False)
        FigureCanvasBase.resize_event(self)
        self.draw_idle()
        QtQuick.QQuickPaintedItem.geometryChanged(self,
                                                  new_geometry,
                                                  old_geometry)

    def sizeHint(self):
        w, h = self.get_width_height()
        return QtCore.QSize(w, h)

    def minumumSizeHint(self):
        return QtCore.QSize(10, 10)

    def hoverEnterEvent(self, event):
        try:
            x, y = self.mouseEventCoords(event.pos())
        except AttributeError:
            # the event from PyQt4 does not include the position
            x = y = None
        FigureCanvasBase.enter_notify_event(self, guiEvent=event, xy=(x, y))

    def hoverLeaveEvent(self, event):
        QtWidgets.QApplication.restoreOverrideCursor()
        FigureCanvasBase.leave_notify_event(self, guiEvent=event)

    def mouseEventCoords(self, pos):
        """Calculate mouse coordinates in physical pixels

        Qt5 use logical pixels, but the figure is scaled to physical
        pixels for rendering.   Transform to physical pixels so that
        all of the down-stream transforms work as expected.

        Also, the origin is different and needs to be corrected.

        """
        dpi_ratio = self.dpi_ratio
        x = pos.x()
        # flip y so y=0 is bottom of canvas
        y = self.figure.bbox.height / dpi_ratio - pos.y()
        return x * dpi_ratio, y * dpi_ratio

    def hoverMoveEvent(self, event):
        x, y = self.mouseEventCoords(event.pos())
        FigureCanvasBase.motion_notify_event(self, x, y, guiEvent=event)

    # hoverMoveEvent kicks in when no mouse buttons are pressed
    # otherwise mouseMoveEvent are emitted
    def mouseMoveEvent(self, event):
        x, y = self.mouseEventCoords(event.pos())
        FigureCanvasBase.motion_notify_event(self, x, y, guiEvent=event)

    def mousePressEvent(self, event):
        x, y = self.mouseEventCoords(event.pos())
        button =buttond.get(event.button())
        if button is not None:
            FigureCanvasBase.button_press_event(self, x, y, button,
                                                guiEvent=event)

    def mouseReleaseEvent(self, event):
        x, y = self.mouseEventCoords(event.pos())
        button =buttond.get(event.button())
        if button is not None:
            FigureCanvasBase.button_release_event(self, x, y, button,
                                                  guiEvent=event)

    def mouseDoubleClickEvent(self, event):
        x, y = self.mouseEventCoords(event.pos())
        button =buttond.get(event.button())
        if button is not None:
            FigureCanvasBase.button_press_event(self, x, y,
                                                button, dblclick=True,
                                                guiEvent=event)

    #TODO
    def wheelEvent(self, event):
        x, y = self.mouseEventCoords(event.pos())
        # from QWheelEvent::delta doc
        if event.pixelDelta().x() == 0 and event.pixelDelta().y() == 0:
            steps = event.angleDelta().y() / 120
        else:
            steps = event.pixelDelta().y()
        if steps:
            FigureCanvasBase.scroll_event(self, x, y, steps, guiEvent=event)

    def keyPressEvent(self, event):
        key = self._get_key(event)
        if key is not None:
            FigureCanvasBase.key_press_event(self, key, guiEvent=event)

    def keyReleaseEvent(self, event):
        key = self._get_key(event)
        if key is not None:
            FigureCanvasBase.key_release_event(self, key, guiEvent=event)

    def _get_key(self, event):
        # if event.isAutoRepeat():
        #     return None

        event_key = event.key()
        event_mods = int(event.modifiers())  # actually a bitmask

        # get names of the pressed modifier keys
        # bit twiddling to pick out modifier keys from event_mods bitmask,
        # if event_key is a MODIFIER, it should not be duplicated in mods
        mods = [name for name, mod_key, qt_key in MODIFIER_KEYS
                if event_key != qt_key and (event_mods & mod_key) == mod_key]
        try:
            # for certain keys (enter, left, backspace, etc) use a word for the
            # key, rather than unicode
            key = SPECIAL_KEYS[event_key]
        except KeyError:
            # unicode defines code points up to 0x0010ffff
            # QT will use Key_Codes larger than that for keyboard keys that are
            # are not unicode characters (like multimedia keys)
            # skip these
            # if you really want them, you should add them to SPECIAL_KEYS
            MAX_UNICODE = 0x10ffff
            if event_key > MAX_UNICODE:
                return None

            key = chr(event_key)
            # qt delivers capitalized letters.  fix capitalization
            # note that capslock is ignored
            if 'shift' in mods:
                mods.remove('shift')
            else:
                key = key.lower()

        mods.reverse()
        return '+'.join(mods + [key])

    def new_timer(self, *args, **kwargs):
        """
        Creates a new backend-specific subclass of
        :class:`backend_bases.Timer`.  This is useful for getting
        periodic events through the backend's native event
        loop. Implemented only for backends with GUIs.

        optional arguments:

        *interval*
            Timer interval in milliseconds

        *callbacks*
            Sequence of (func, args, kwargs) where func(*args, **kwargs)
            will be executed by the timer every *interval*.
        """
        return TimerQT(*args, **kwargs)

    def flush_events(self):
        global qApp
        qApp.processEvents()

class FigureCanvasQtQuickAgg(FigureCanvasAgg, FigureCanvasQtQuick):
    """ This class customizes the FigureCanvasQtQuick for Agg
    """
    def __init__(self, figure=None, parent=None):
        super().__init__(figure=figure, parent=parent)
        self.blitbox = None

    def paint(self, p):
        """
        Copy the image from the Agg canvas to the qt.drawable.
        In Qt, all drawing should be done inside of here when a widget is
        shown onscreen.
        """
        self._draw_idle()  # Only does something if a draw is pending.

        # if the canvas does not have a renderer, then give up and wait for
        # FigureCanvasAgg.draw(self) to be called
        if not hasattr(self, 'renderer'):
            return

        if self.blitbox is None:
            # matplotlib is in rgba byte order.  QImage wants to put the bytes
            # into argb format and is in a 4 byte unsigned int.  Little endian
            # system is LSB first and expects the bytes in reverse order
            # (bgra).
            if QtCore.QSysInfo.ByteOrder == QtCore.QSysInfo.LittleEndian:
                # stringBuffer = self.renderer._renderer.tostring_bgra()
                #   tostring_xxx do not exist anymore in _renderer

                # patch
                #  Change QImage format to RGBA8888
                #    now no conversion needed
                #    And with bigendian?
                stringBuffer = np.asarray(self.renderer._renderer).tobytes()
            else:
                stringBuffer = self.renderer.tostring_argb()

            # convert the Agg rendered image -> qImage
            qImage = QtGui.QImage(stringBuffer, self.renderer.width,
                                  self.renderer.height,
                                  QtGui.QImage.Format_RGBA8888)
            if hasattr(qImage, 'setDevicePixelRatio'):
                # Not available on Qt4 or some older Qt5.
                qImage.setDevicePixelRatio(self.dpi_ratio)
            # get the rectangle for the image
            rect = qImage.rect()
            # p = QtGui.QPainter(self)
            # reset the image area of the canvas to be the back-ground color
            p.eraseRect(rect)
            # draw the rendered image on to the canvas
            p.drawPixmap(QtCore.QPoint(0, 0), QtGui.QPixmap.fromImage(qImage))

            # draw the zoom rectangle to the QPainter
            self._draw_rect_callback(p)

        else:
            bbox = self.blitbox
            # repaint uses logical pixels, not physical pixels like the renderer.
            l, b, w, h = [pt / self._dpi_ratio for pt in bbox.bounds]
            t = b + h
            reg = self.copy_from_bbox(bbox)
            stringBuffer = reg.to_string_argb()
            qImage = QtGui.QImage(stringBuffer, w, h,
                                  QtGui.QImage.Format_RGBA8888)

            if hasattr(qImage, 'setDevicePixelRatio'):
                # Not available on Qt4 or some older Qt5.
                qImage.setDevicePixelRatio(self.dpi_ratio)
            pixmap = QtGui.QPixmap.fromImage(qImage)

            p.drawPixmap(QtCore.QPoint(l, self.renderer.height-t), pixmap)

            # draw the zoom rectangle to the QPainter
            self._draw_rect_callback(p)

            self.blitbox = None

    def blit(self, bbox=None):
        """
        Blit the region in bbox
        """
        # If bbox is None, blit the entire canvas. Otherwise
        # blit only the area defined by the bbox.
        if bbox is None and self.figure:
            bbox = self.figure.bbox

        self.blitbox = bbox
        # repaint uses logical pixels, not physical pixels like the renderer.
        l, b, w, h = [pt / self._dpi_ratio for pt in bbox.bounds]
        t = b + h
        self.repaint(l, self.renderer.height-t, w, h)

    def print_figure(self, *args, **kwargs):
        super().print_figure(*args, **kwargs)
        self.draw()


class NavigationToolbar2QT(NavigationToolbar2, QtWidgets.QToolBar):
    message = QtCore.Signal(str)

    toolitems = [*NavigationToolbar2.toolitems]

    #TODO too many stuf be involve here
    # toolitems.insert(
    #     # Add 'customize' action after 'subplots'
    #     [name for name, *_ in toolitems].index("Subplots") + 1,
    #     ("Customize", "Edit axis, curve and image parameters",
    #      "qt4_editor_options", "edit_parameters"))

    def __init__(self, canvas, parent, coordinates=True):
        """coordinates: should we show the coordinates on the right?"""
        QtWidgets.QToolBar.__init__(self, parent)
        self.setAllowedAreas(
            QtCore.Qt.ToolBarArea_Mask.TopToolBarArea
            | QtCore.Qt.ToolBarArea_Mask.TopToolBarArea)

        self.coordinates = coordinates
        self._actions = {}  # mapping of toolitem method names to QActions.

        for text, tooltip_text, image_file, callback in self.toolitems:
            if text is None:
                self.addSeparator()
            else:
                a = self.addAction(self._icon(image_file + '.png'),
                                   text, getattr(self, callback))
                self._actions[callback] = a
                if callback in ['zoom', 'pan']:
                    a.setCheckable(True)
                if tooltip_text is not None:
                    a.setToolTip(tooltip_text)

        # Add the (x, y) location widget at the right side of the toolbar
        # The stretch factor is 1 which means any resizing of the toolbar
        # will resize this label instead of the buttons.
        if self.coordinates:
            self.locLabel = QtWidgets.QLabel("", self)
            self.locLabel.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight
                | QtCore.Qt.AlignmentFlag.AlignVCenter)
            self.locLabel.setSizePolicy(QtWidgets.QSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Ignored,
            ))
            labelAction = self.addWidget(self.locLabel)
            labelAction.setVisible(True)

        NavigationToolbar2.__init__(self, canvas)

    @_api.deprecated("3.3", alternative="self.canvas.parent()")
    @property
    def parent(self):
        return self.canvas.parent()

    @_api.deprecated("3.3", alternative="self.canvas.setParent()")
    @parent.setter
    def parent(self, value):
        pass

    @_api.deprecated(
        "3.3", alternative="os.path.join(mpl.get_data_path(), 'images')")
    @property
    def basedir(self):
        return str(cbook._get_data_path('images'))

    def _icon(self, name):
        """
        Construct a `.QIcon` from an image file *name*, including the extension
        and relative to Matplotlib's "images" data directory.
        """
        if QtCore.qVersion() >= '5.':
            name = name.replace('.png', '_large.png')
        pm = QtGui.QPixmap(str(cbook._get_data_path('images', name)))
        _setDevicePixelRatio(pm, _devicePixelRatioF(self))
        if self.palette().color(self.backgroundRole()).value() < 128:
            icon_color = self.palette().color(self.foregroundRole())
            mask = pm.createMaskFromColor(
                QtGui.QColor('black'),
                QtCore.Qt.MaskMode.MaskOutColor)
            pm.fill(icon_color)
            pm.setMask(mask)
        return QtGui.QIcon(pm)

    #TODO fix in the future
    # def edit_parameters(self):
    #     axes = self.canvas.figure.get_axes()
    #     if not axes:
    #         QtWidgets.QMessageBox.warning(
    #             self.canvas.parent(), "Error", "There are no axes to edit.")
    #         return
    #     elif len(axes) == 1:
    #         ax, = axes
    #     else:
    #         titles = [
    #             ax.get_label() or
    #             ax.get_title() or
    #             " - ".join(filter(None, [ax.get_xlabel(), ax.get_ylabel()])) or
    #             f"<anonymous {type(ax).__name__}>"
    #             for ax in axes]
    #         duplicate_titles = [
    #             title for title in titles if titles.count(title) > 1]
    #         for i, ax in enumerate(axes):
    #             if titles[i] in duplicate_titles:
    #                 titles[i] += f" (id: {id(ax):#x})"  # Deduplicate titles.
    #         item, ok = QtWidgets.QInputDialog.getItem(
    #             self.canvas.parent(),
    #             'Customize', 'Select axes:', titles, 0, False)
    #         if not ok:
    #             return
    #         ax = axes[titles.index(item)]
    #     figureoptions.figure_edit(ax, self)

    def _update_buttons_checked(self):
        # sync button checkstates to match active mode
        if 'pan' in self._actions:
            self._actions['pan'].setChecked(self.mode.name == 'PAN')
        if 'zoom' in self._actions:
            self._actions['zoom'].setChecked(self.mode.name == 'ZOOM')

    def pan(self, *args):
        super().pan(*args)
        self._update_buttons_checked()

    def zoom(self, *args):
        super().zoom(*args)
        self._update_buttons_checked()

    def set_message(self, s):
        self.message.emit(s)
        if self.coordinates:
            self.locLabel.setText(s)

    def set_cursor(self, cursor):
        self.canvas.setCursor(cursord[cursor])

    def draw_rubberband(self, event, x0, y0, x1, y1):
        height = self.canvas.figure.bbox.height
        y1 = height - y1
        y0 = height - y0
        rect = [int(val) for val in (x0, y0, x1 - x0, y1 - y0)]
        self.canvas.drawRectangle(rect)

    def remove_rubberband(self):
        self.canvas.drawRectangle(None)

    #TODO fix in the future
    # def configure_subplots(self):
    #     image = str(cbook._get_data_path('images/matplotlib.png'))
    #     dia = SubplotToolQt(self.canvas.figure, self.canvas.parent())
    #     dia.setWindowIcon(QtGui.QIcon(image))
    #     qt_compat._exec(dia)

    def save_figure(self, *args):
        filetypes = self.canvas.get_supported_filetypes_grouped()
        sorted_filetypes = sorted(filetypes.items())
        default_filetype = self.canvas.get_default_filetype()

        startpath = os.path.expanduser(mpl.rcParams['savefig.directory'])
        start = os.path.join(startpath, self.canvas.get_default_filename())
        filters = []
        selectedFilter = None
        for name, exts in sorted_filetypes:
            exts_list = " ".join(['*.%s' % ext for ext in exts])
            filter = '%s (%s)' % (name, exts_list)
            if default_filetype in exts:
                selectedFilter = filter
            filters.append(filter)
        filters = ';;'.join(filters)

        fname, filter = _getSaveFileName(
            self.canvas.parent(), "Choose a filename to save to", start,
            filters, selectedFilter)
        if fname:
            # Save dir for next time, unless empty str (i.e., use cwd).
            if startpath != "":
                mpl.rcParams['savefig.directory'] = os.path.dirname(fname)
            try:
                self.canvas.figure.savefig(fname)
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error saving file", str(e),
                    QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.NoButton)

    def set_history_buttons(self):
        can_backward = self._nav_stack._pos > 0
        can_forward = self._nav_stack._pos < len(self._nav_stack._elements) - 1
        if 'back' in self._actions:
            self._actions['back'].setEnabled(can_backward)
        if 'forward' in self._actions:
            self._actions['forward'].setEnabled(can_forward)

#TODO may crash sometime
class FigureCanvasQT(QtWidgets.QWidget, FigureCanvasBase):
    required_interactive_framework = "qt"
    _timer_cls = TimerQT

    def __init__(self, figure=None, parent=None):
        #TODO? how to init QWidget?
        #super().__init__(figure=figure)
        QtWidgets.QWidget.__init__(self, parent=parent)
        FigureCanvasBase.__init__(self, figure=figure)


        # We don't want to scale up the figure DPI more than once.
        # Note, we don't handle a signal for changing DPI yet.
        self.figure._original_dpi = self.figure.dpi
        self._update_figure_dpi()
        # In cases with mixed resolution displays, we need to be careful if the
        # dpi_ratio changes - in this case we need to resize the canvas
        # accordingly.
        self._dpi_ratio_prev = self._dpi_ratio

        self._draw_pending = False
        self._is_drawing = False
        self._draw_rect_callback = lambda painter: None

        self.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMouseTracking(True)
        self.resize(*self.get_width_height())

        palette = QtGui.QPalette(QtGui.QColor("white"))
        self.setPalette(palette)

    def _update_figure_dpi(self):
        dpi = self._dpi_ratio * self.figure._original_dpi
        self.figure._set_dpi(dpi, forward=False)

    @property
    def _dpi_ratio(self):
        #return _devicePixelRatioF(self)
        return self.devicePixelRatioF() or 1

    def _update_pixel_ratio(self):
        # We need to be careful in cases with mixed resolution displays if
        # dpi_ratio changes.
        if self._dpi_ratio != self._dpi_ratio_prev:
            # We need to update the figure DPI.
            self._update_figure_dpi()
            self._dpi_ratio_prev = self._dpi_ratio
            # The easiest way to resize the canvas is to emit a resizeEvent
            # since we implement all the logic for resizing the canvas for
            # that event.
            event = QtGui.QResizeEvent(self.size(), self.size())
            self.resizeEvent(event)
            # resizeEvent triggers a paintEvent itself, so we exit this one
            # (after making sure that the event is immediately handled).

    def _update_screen(self, screen):
        # Handler for changes to a window's attached screen.
        self._update_pixel_ratio()
        if screen is not None:
            screen.physicalDotsPerInchChanged.connect(self._update_pixel_ratio)
            screen.logicalDotsPerInchChanged.connect(self._update_pixel_ratio)

    def showEvent(self, event):
        # Set up correct pixel ratio, and connect to any signal changes for it,
        # once the window is shown (and thus has these attributes).
        window = self.window().windowHandle()
        window.screenChanged.connect(self._update_screen)
        self._update_screen(window.screen())

    def get_width_height(self):
        w, h = FigureCanvasBase.get_width_height(self)
        return int(w / self._dpi_ratio), int(h / self._dpi_ratio)

    def enterEvent(self, event):
        try:
            x, y = self.mouseEventCoords(self._get_position(event))
        except AttributeError:
            # the event from PyQt4 does not include the position
            x = y = None
        FigureCanvasBase.enter_notify_event(self, guiEvent=event, xy=(x, y))

    def leaveEvent(self, event):
        QtWidgets.QApplication.restoreOverrideCursor()
        FigureCanvasBase.leave_notify_event(self, guiEvent=event)

    #_get_position = operator.methodcaller(
    #    "position" if QT_API in ["PyQt6", "PySide6"] else "pos")


    _get_position = operator.methodcaller(
        "position")

    def mouseEventCoords(self, pos):
        """
        Calculate mouse coordinates in physical pixels.

        Qt use logical pixels, but the figure is scaled to physical
        pixels for rendering.  Transform to physical pixels so that
        all of the down-stream transforms work as expected.

        Also, the origin is different and needs to be corrected.
        """
        dpi_ratio = self._dpi_ratio
        x = pos.x()
        # flip y so y=0 is bottom of canvas
        y = self.figure.bbox.height / dpi_ratio - pos.y()
        return x * dpi_ratio, y * dpi_ratio

    def mousePressEvent(self, event):
        x, y = self.mouseEventCoords(self._get_position(event))
        button =buttond.get(event.button())
        if button is not None:
            FigureCanvasBase.button_press_event(self, x, y, button,
                                                guiEvent=event)

    def mouseDoubleClickEvent(self, event):
        x, y = self.mouseEventCoords(self._get_position(event))
        button =buttond.get(event.button())
        if button is not None:
            FigureCanvasBase.button_press_event(self, x, y,
                                                button, dblclick=True,
                                                guiEvent=event)

    def mouseMoveEvent(self, event):
        x, y = self.mouseEventCoords(self._get_position(event))
        FigureCanvasBase.motion_notify_event(self, x, y, guiEvent=event)

    def mouseReleaseEvent(self, event):
        x, y = self.mouseEventCoords(self._get_position(event))
        button =buttond.get(event.button())
        if button is not None:
            FigureCanvasBase.button_release_event(self, x, y, button,
                                                  guiEvent=event)


    def wheelEvent(self, event):
        x, y = self.mouseEventCoords(self._get_position(event))
        # from QWheelEvent::delta doc
        if event.pixelDelta().x() == 0 and event.pixelDelta().y() == 0:
            steps = event.angleDelta().y() / 120
        else:
            steps = event.pixelDelta().y()
        if steps:
            FigureCanvasBase.scroll_event(
                self, x, y, steps, guiEvent=event)

    def keyPressEvent(self, event):
        key = self._get_key(event)
        if key is not None:
            FigureCanvasBase.key_press_event(self, key, guiEvent=event)

    def keyReleaseEvent(self, event):
        key = self._get_key(event)
        if key is not None:
            FigureCanvasBase.key_release_event(self, key, guiEvent=event)

    def resizeEvent(self, event):
        frame = sys._getframe()
        if frame.f_code is frame.f_back.f_code:  # Prevent PyQt6 recursion.
            return
        w = event.size().width() * self._dpi_ratio
        h = event.size().height() * self._dpi_ratio
        dpival = self.figure.dpi
        winch = w / dpival
        hinch = h / dpival
        self.figure.set_size_inches(winch, hinch, forward=False)
        # pass back into Qt to let it finish
        QtWidgets.QWidget.resizeEvent(self, event)
        # emit our resize events
        FigureCanvasBase.resize_event(self)

    def sizeHint(self):
        w, h = self.get_width_height()
        return QtCore.QSize(w, h)

    def minumumSizeHint(self):
        return QtCore.QSize(10, 10)

    def _get_key(self, event):
        event_key = event.key()
        #event_mods = _to_int(event.modifiers())  # actually a bitmask
        event_mods = int(event.modifiers())  # actually a bitmask


        # get names of the pressed modifier keys
        # 'control' is named 'control' when a standalone key, but 'ctrl' when a
        # modifier
        # bit twiddling to pick out modifier keys from event_mods bitmask,
        # if event_key is a MODIFIER, it should not be duplicated in mods
        mods = [SPECIAL_KEYS[key].replace('control', 'ctrl')
                for _, mod, key in MODIFIER_KEYS
                if event_key != key and event_mods & mod]
        try:
            # for certain keys (enter, left, backspace, etc) use a word for the
            # key, rather than unicode
            key = SPECIAL_KEYS[event_key]
        except KeyError:
            # unicode defines code points up to 0x10ffff (sys.maxunicode)
            # QT will use Key_Codes larger than that for keyboard keys that are
            # are not unicode characters (like multimedia keys)
            # skip these
            # if you really want them, you should add them to SPECIAL_KEYS
            if event_key > sys.maxunicode:
                return None

            key = chr(event_key)
            # qt delivers capitalized letters.  fix capitalization
            # note that capslock is ignored
            if 'shift' in mods:
                mods.remove('shift')
            else:
                key = key.lower()

        return '+'.join(mods + [key])

    def flush_events(self):
        # docstring inherited
        qApp.processEvents()

    def start_event_loop(self, timeout=0):
        # docstring inherited
        if hasattr(self, "_event_loop") and self._event_loop.isRunning():
            raise RuntimeError("Event loop already running")
        self._event_loop = event_loop = QtCore.QEventLoop()
        if timeout > 0:
            timer = QtCore.QTimer.singleShot(int(timeout * 1000),
                                             event_loop.quit)
        #qt_compat._exec(event_loop)
        event_loop.exec_()

    def stop_event_loop(self, event=None):
        # docstring inherited
        if hasattr(self, "_event_loop"):
            self._event_loop.quit()

    def draw(self):
        """Render the figure, and queue a request for a Qt draw."""
        # The renderer draw is done here; delaying causes problems with code
        # that uses the result of the draw() to update plot elements.
        if self._is_drawing:
            return
        with cbook._setattr_cm(self, _is_drawing=True):
            super().draw()
        self.update()

    def draw_idle(self):
        """Queue redraw of the Agg buffer and request Qt paintEvent."""
        # The Agg draw needs to be handled by the same thread Matplotlib
        # modifies the scene graph from. Post Agg draw request to the
        # current event loop in order to ensure thread affinity and to
        # accumulate multiple draw requests from event handling.
        # TODO: queued signal connection might be safer than singleShot
        if not (getattr(self, '_draw_pending', False) or
                getattr(self, '_is_drawing', False)):
            self._draw_pending = True
            QtCore.QTimer.singleShot(0, self._draw_idle)

    def blit(self, bbox=None):
        # docstring inherited
        if bbox is None and self.figure:
            bbox = self.figure.bbox  # Blit the entire canvas if bbox is None.
        # repaint uses logical pixels, not physical pixels like the renderer.
        l, b, w, h = [int(pt / self._dpi_ratio) for pt in bbox.bounds]
        t = b + h
        self.repaint(l, self.rect().height() - t, w, h)

    def _draw_idle(self):
        with self._idle_draw_cntx():
            if not self._draw_pending:
                return
            self._draw_pending = False
            if self.height() < 0 or self.width() < 0:
                return
            try:
                self.draw()
            except Exception:
                # Uncaught exceptions are fatal for PyQt5, so catch them.
                traceback.print_exc()

    def drawRectangle(self, rect):
        # Draw the zoom rectangle to the QPainter.  _draw_rect_callback needs
        # to be called at the end of paintEvent.
        if rect is not None:
            x0, y0, w, h = [int(pt / self._dpi_ratio) for pt in rect]
            x1 = x0 + w
            y1 = y0 + h
            def _draw_rect_callback(painter):
                pen = QtGui.QPen(QtGui.QColor("black"), 1 / self._dpi_ratio)
                pen.setDashPattern([3, 3])
                for color, offset in [
                        (QtGui.QColor("black"), 0),
                        (QtGui.QColor("white"), 3),
                ]:
                    pen.setDashOffset(offset)
                    pen.setColor(color)
                    painter.setPen(pen)
                    # Draw the lines from x0, y0 towards x1, y1 so that the
                    # dashes don't "jump" when moving the zoom box.
                    painter.drawLine(x0, y0, x0, y1)
                    painter.drawLine(x0, y0, x1, y0)
                    painter.drawLine(x0, y1, x1, y1)
                    painter.drawLine(x1, y0, x1, y1)
        else:
            def _draw_rect_callback(painter):
                return
        self._draw_rect_callback = _draw_rect_callback
        self.update()

#TODO may crash sometime
class FigureCanvasQTAgg(FigureCanvasAgg, FigureCanvasQT):

    def __init__(self, figure):
        # Must pass 'figure' as kwarg to Qt base class.
        super().__init__(figure=figure)

    def paintEvent(self, event):
        """
        Copy the image from the Agg canvas to the qt.drawable.

        In Qt, all drawing should be done inside of here when a widget is
        shown onscreen.
        """
        self._draw_idle()  # Only does something if a draw is pending.

        # If the canvas does not have a renderer, then give up and wait for
        # FigureCanvasAgg.draw(self) to be called.
        if not hasattr(self, 'renderer'):
            return

        painter = QtGui.QPainter(self)
        try:
            # See documentation of QRect: bottom() and right() are off
            # by 1, so use left() + width() and top() + height().
            rect = event.rect()
            # scale rect dimensions using the screen dpi ratio to get
            # correct values for the Figure coordinates (rather than
            # QT5's coords)
            width = rect.width() * self._dpi_ratio
            height = rect.height() * self._dpi_ratio
            left, top = self.mouseEventCoords(rect.topLeft())
            # shift the "top" by the height of the image to get the
            # correct corner for our coordinate system
            bottom = top - height
            # same with the right side of the image
            right = left + width
            # create a buffer using the image bounding box
            bbox = Bbox([[left, bottom], [right, top]])
            reg = self.copy_from_bbox(bbox)
            buf = cbook._unmultiplied_rgba8888_to_premultiplied_argb32(
                memoryview(reg))

            # clear the widget canvas
            painter.eraseRect(rect)

            # if QT_API == "PyQt6":
            #     from PyQt6 import sip
            #     ptr = sip.voidptr(buf)
            # else:
            #     ptr = buf
            ptr = buf
            qimage = QtGui.QImage(
                ptr, buf.shape[1], buf.shape[0],
                QtGui.QImage.Format.Format_ARGB32_Premultiplied)
            #_setDevicePixelRatio(qimage, self._dpi_ratio)
            qimage.setDevicePixelRatio(self._dpi_ratio)
            # set origin using original QT coordinates
            origin = QtCore.QPoint(rect.left(), rect.top())
            painter.drawImage(origin, qimage)
            # Adjust the buf reference count to work around a memory
            # leak bug in QImage under PySide.
            #if QT_API in ('PySide', 'PySide2'):
            #    ctypes.c_long.from_address(id(buf)).value = 1
            #ctypes.c_long.from_address(id(buf)).value = 1

            self._draw_rect_callback(painter)
        finally:
            painter.end()

    def print_figure(self, *args, **kwargs):
        super().print_figure(*args, **kwargs)
        self.draw()


# The first one is a standard name; The second not so
FigureCanvas = FigureCanvasQtQuickAgg


class DemoViewModel(QtCore.QObject):
    """ A bridge class to interact with the plot in python
    """
    coordinatesChanged = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # The figure and toolbar
        self.figure = None
        self.toolbar = None

        # this is used to display the coordinates of the mouse in the window
        self._coordinates = ""

        self.pause=False

    def updateWithCanvas(self, canvas, dynamic=False):
        """ initialize with the canvas for the figure
        """
        self.figure = canvas.figure

        self.update_toolbar(canvas)

        if not dynamic:
            # make a small plot
            self.axes = self.figure.add_subplot(111)
            self.axes.grid(True)

            x = np.linspace(0, 2 * np.pi, 100)
            y = np.sin(x)

            self.axes.plot(x, y)
            canvas.draw_idle()
        else:
            self.axes = canvas.figure.subplots()
            t = np.linspace(0, 10, 101)
            # Set up a Line2D.
            self._line, = self.axes.plot(t, np.sin(t + time.time()))
            self._timer = canvas.new_timer(50)
            self._timer.add_callback(self._update_canvas)
            self._timer.start()
        # connect for displaying the coordinates
        self.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def _update_canvas(self):
        if self.pause :
            return
        t = np.linspace(0, 10, 101)
        # Shift the sinusoid as a function of time.
        self._line.set_data(t, np.sin(t + time.time()))
        self._line.figure.canvas.draw()

    def update_toolbar(self, canvas):
        # tips: use platform specific NavigationToolbar2QtQuick if you want to see the rubberband
        # self.toolbar = NavigationToolbar2QtQuick(canvas=canvas)
        self.toolbar = NavigationToolbar2(canvas=canvas)

    # define the coordinates property
    # (I have had problems using the @QtCore.Property directy in the past)
    def getCoordinates(self):
        return self._coordinates

    def setCoordinates(self, coordinates):
        self._coordinates = coordinates
        self.coordinatesChanged.emit(self._coordinates)

    coordinates = QtCore.Property(str, getCoordinates, setCoordinates,
                                  notify=coordinatesChanged)

    #TODO from ui or to ui, args?
    @QtCore.Slot()
    def pauseChanged(self, new_state:bool):
        self.pause = new_state
        pass

    # The toolbar commands
    @QtCore.Slot()
    def pan(self, *args):
        """Activate the pan tool."""
        self.toolbar.pan(*args)

    @QtCore.Slot()
    def zoom(self, *args):
        """activate zoom tool."""
        self.toolbar.zoom(*args)

    @QtCore.Slot()
    def home(self, *args):
        self.toolbar.home(*args)

    @QtCore.Slot()
    def back(self, *args):
        self.toolbar.back(*args)

    @QtCore.Slot()
    def forward(self, *args):
        self.toolbar.forward(*args)

    def on_motion(self, event):
        """
        Update the coordinates on the display
        """
        if event.inaxes == self.axes:
            self.coordinates = f"({event.xdata:.2f}, {event.ydata:.2f})"

def myMessageOutput(type:QtMsgType, context:QMessageLogContext, msg:str):
    logging.info(rf'====> {msg}')
    pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    qInstallMessageHandler(myMessageOutput)

    import PySide6
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QtGui.QGuiApplication(sys.argv)
    engine = PySide6.QtQml.QQmlApplicationEngine()

    # instantate the display bridge
    vm = DemoViewModel()

    # Expose the Python object to QML
    context = engine.rootContext()
    context.setContextProperty("vm", vm)

    # matplotlib stuff
    PySide6.QtQml.qmlRegisterType(FigureCanvasQtQuickAgg, "Backend", 1, 0, "FigureCanvas")

    # Load the QML file
    qmlFile = Path(Path.cwd(), Path(__file__).parent, "demoview.qml")
    engine.load(QtCore.QUrl.fromLocalFile(str(qmlFile)))

    win = engine.rootObjects()[0]
    vm.updateWithCanvas(win.findChild(QtCore.QObject, "figure"), dynamic=False)
    # execute and cleanup
    app.exec_()