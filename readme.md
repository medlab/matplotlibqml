A matplotlib mini backend always base on the latest QT for Python, no compatible will be care

Focus on Qt 6 (will always point to the latest) for Python and QML/QWidget as main user case, only desktop application will be care

Mainly base on:

    1. https://github.com/jmitrevs/matplotlib_backend_qtquick
    2. https://github.com/matplotlib/matplotlib/blob/master/lib/matplotlib/backends/backend_qt5.py
    3. https://github.com/matplotlib/matplotlib/blob/master/lib/matplotlib/backends/backend_qt5agg.py

The module can run as qml demo application itself, like:

```bash
    python -m matplotlibqml    
```

A standalone classic QWidget sample(pure QWidget) is provided too, like:

```bash
    python -m matplotlibqml.widgetdemo
```

# 你好

![](https://raw.githubusercontent.com/medlab/matplotlibqml/main/hello_qml.gif)
![](https://raw.githubusercontent.com/medlab/matplotlibqml/main/hello_qwidget.gif)

Why
=================

    QT keep improving and changing, and compatibility will kill flexibility, especially when upstream not so stable

Credit:
=================
    1. https://github.com/fcollonval/matplotlib_qtquick_playground
    2. https://github.com/jmitrevs/matplotlib_backend_qtquick
    3. https://github.com/matplotlib/matplotlib/blob/master/lib/matplotlib/backends/backend_qt5.py
    4. https://github.com/matplotlib/matplotlib/blob/master/lib/matplotlib/backends/backend_qt5agg.py
    5. Some weekend play for fun self Python project