import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtQuick.Layouts

import Backend 1.0

ApplicationWindow {
    id: mainWindow
    visible: true
    width: 800
    height: 600
    title: qsTr("QtQuick Simple View")

    
    FigureCanvas {
        id: mplView
        objectName : "figure"
        dpi_ratio: Screen.devicePixelRatio
	    anchors.fill: parent
    }

    footer: ToolBar {
        RowLayout {
            ToolButton {
                text: qsTr("home")
                onClicked: {
                    vm.home();
                }
            }

            Button {
                text: qsTr("back")
                onClicked: {
                    vm.back();
                }
            }

            Button {
                text: qsTr("forward")
                onClicked: {
                    vm.forward();
                }
            }

            ToolSeparator{}

            Button {
                id: pan
                text: qsTr("pan")
                checkable: true
                onClicked: {
                    if (zoom.checked) {
                        zoom.checked = false;
                    }
                    vm.pan();
                }
            }

            Button {
                id: zoom
                text: qsTr("zoom")
                checkable: true
                onClicked: {
                    if (pan.checked) {
                        // toggle pan off
                        pan.checked = false;
                    }
                    vm.zoom();
                }
            }
            ToolSeparator {}
            TextInput {
                id: location
                readOnly: true
                text: vm.coordinates
            }
        }
    }

}
