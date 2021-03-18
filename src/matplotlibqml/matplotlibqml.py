import logging
import os
import sys
import traceback
from pathlib import Path

import matplotlib
import numpy as np
from matplotlib import cbook

from matplotlib.backend_bases import FigureCanvasBase, NavigationToolbar2, MouseButton, TimerBase
from matplotlib.backend_tools import cursors
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PySide6 import QtCore, QtGui, QtQuick, QtWidgets

from PySide6.QtCore import Qt, qInstallMessageHandler, QMessageLogContext, QtMsgType


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

class FigureCanvasQtQuick(QtQuick.QQuickPaintedItem, FigureCanvasBase):
    """ This class creates a QtQuick Item encapsulating a Matplotlib
        Figure and all the functions to interact with the 'standard'
        Matplotlib navigation toolbar.
    """

    dpi_ratio_changed = QtCore.Signal()

    # map Qt button codes to MouseEvent's ones:
    buttond = {QtCore.Qt.LeftButton: MouseButton.LEFT,
               QtCore.Qt.MiddleButton: MouseButton.MIDDLE,
               QtCore.Qt.RightButton: MouseButton.RIGHT,
               QtCore.Qt.XButton1: MouseButton.BACK,
               QtCore.Qt.XButton2: MouseButton.FORWARD,
               }

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
        button = self.buttond.get(event.button())
        if button is not None:
            FigureCanvasBase.button_press_event(self, x, y, button,
                                                guiEvent=event)

    def mouseReleaseEvent(self, event):
        x, y = self.mouseEventCoords(event.pos())
        button = self.buttond.get(event.button())
        if button is not None:
            FigureCanvasBase.button_release_event(self, x, y, button,
                                                  guiEvent=event)

    def mouseDoubleClickEvent(self, event):
        x, y = self.mouseEventCoords(event.pos())
        button = self.buttond.get(event.button())
        if button is not None:
            FigureCanvasBase.button_press_event(self, x, y,
                                                button, dblclick=True,
                                                guiEvent=event)

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


# The first one is a standard name; The second not so
FigureCanvas = FigureCanvasQtQuickAgg



if __name__ == "__main__":

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

        def updateWithCanvas(self, canvas):
            """ initialize with the canvas for the figure
            """
            self.figure = canvas.figure
            self.toolbar = NavigationToolbar2QtQuick(canvas=canvas)

            # make a small plot
            self.axes = self.figure.add_subplot(111)
            self.axes.grid(True)

            x = np.linspace(0, 2 * np.pi, 100)
            y = np.sin(x)

            self.axes.plot(x, y)
            canvas.draw_idle()

            # connect for displaying the coordinates
            self.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

        # define the coordinates property
        # (I have had problems using the @QtCore.Property directy in the past)
        def getCoordinates(self):
            return self._coordinates

        def setCoordinates(self, coordinates):
            self._coordinates = coordinates
            self.coordinatesChanged.emit(self._coordinates)

        coordinates = QtCore.Property(str, getCoordinates, setCoordinates,
                                      notify=coordinatesChanged)

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

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    def myMessageOutput(type:QtMsgType, context:QMessageLogContext, msg:str):
        logging.info(rf'====> {msg}')
        pass
        # QByteArray localMsg = msg.toLocal8Bit();
        # switch (type) {
        # case QtDebugMsg:
        #     fprintf(stderr, "Debug: %s (%s:%u, %s)\n", localMsg.constData(), context.file, context.line, context.function);
        #     break;
        # case QtInfoMsg:
        #     fprintf(stderr, "Info: %s (%s:%u, %s)\n", localMsg.constData(), context.file, context.line, context.function);
        #     break;
        # case QtWarningMsg:
        #     fprintf(stderr, "Warning: %s (%s:%u, %s)\n", localMsg.constData(), context.file, context.line, context.function);
        #     break;
        # case QtCriticalMsg:
        #     fprintf(stderr, "Critical: %s (%s:%u, %s)\n", localMsg.constData(), context.file, context.line, context.function);
        #     break;
        # case QtFatalMsg:
        #     fprintf(stderr, "Fatal: %s (%s:%u, %s)\n", localMsg.constData(), context.file, context.line, context.function);
        #     abort();
        # }

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
    vm.updateWithCanvas(win.findChild(QtCore.QObject, "figure"))
    # execute and cleanup
    app.exec_()