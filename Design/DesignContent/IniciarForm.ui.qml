
/*
This is a UI file (.ui.qml) that is intended to be edited in Qt Design Studio only.
It is supposed to be strictly declarative and only uses a subset of QML. If you edit
this file manually, you might introduce QML code that is not supported by Qt Design Studio.
Check out https://doc.qt.io/qtcreator/creator-quick-ui-forms.html for details on .ui.qml files.
*/
import QtQuick
import QtQuick.Controls
import Design
import QtQuick.Studio.DesignEffects

Rectangle {
    width: Constants.width
    height: Constants.height
    color: "#e8e8e8"

    id: root

    property alias electionComboBox: electionComboBox
    property alias startElectionBtn: startElectionBtn
    property alias backToMainBtn: backToMainBtn

    property bool isLoading: false
    property string statusMessage: ""
    property bool statusIsError: false
    property bool isElectionStarted: false

    signal backClicked

    Button {
        id: backButton
        x: 45
        y: 12
        width: 30
        height: 30
        text: "←"

        background: Rectangle {
            color: parent.down ? "#999999" : (parent.hovered ? "#aaaaaa" : "transparent")
            radius: 4
        }
        contentItem: Text {
            text: parent.text
            color: "#333333"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 22
            font.bold: true
        }
        Connections {
            function onClicked() {
                root.backClicked()
            }
        }
    }

    Text {
        id: text1
        x: 45
        y: 47
        text: qsTr("Iniciar Eleição")
        font.pixelSize: 22
        font.weight: Font.Bold
    }

    Text {
        id: text2
        x: 45
        y: 81
        text: qsTr("Selecione a eleição que deseja iniciar o recebimento de votos")
        font.pixelSize: 13
        font.weight: Font.Light
    }

    Text {
        id: text3
        x: 45
        y: 138
        text: qsTr("Eleição")
        font.pixelSize: 12
    }

    ComboBox {
        id: electionComboBox
        x: 45
        y: 163
        width: 450
        height: 35
        model: []
        enabled: !root.isLoading && !root.isElectionStarted

        background: Rectangle {
            color: "#ffffff"
            radius: 4
            border.color: "#a0a0a0"
            border.width: 1
        }

        contentItem: Text {
            leftPadding: 10
            rightPadding: electionComboBox.indicator.width + electionComboBox.spacing
            text: electionComboBox.displayText
            font.pixelSize: 12
            color: "#333333"
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    Button {
        id: startElectionBtn
        x: Constants.width - width - 45
        y: Constants.height - height - 30
        width: 160
        height: 40
        text: root.isLoading ? qsTr("Iniciando...") : qsTr("Iniciar Eleição")
        enabled: !root.isLoading && (electionComboBox.currentIndex >= 0) && (electionComboBox.count > 0) && !root.isElectionStarted
        visible: !root.isElectionStarted

        opacity: enabled ? 1.0 : 0.5

        background: Rectangle {
            color: parent.down ? "#176128" : (parent.hovered ? "#24913d" : "#1e7e34")
            radius: 6
            Rectangle {
                z: -1
                width: parent.width
                height: parent.height
                y: 3
                color: "#33000000"
                radius: 6
            }
        }
        contentItem: Text {
            text: parent.text
            color: "white"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 14
            font.bold: true
        }
    }

    Button {
        id: backToMainBtn
        x: Constants.width - width - 45
        y: Constants.height - height - 30
        width: 160
        height: 40
        text: qsTr("Voltar ao Painel")
        visible: root.isElectionStarted

        background: Rectangle {
            color: parent.down ? "#2b3d4f" : (parent.hovered ? "#3e5770" : "#34495e")
            radius: 6
            Rectangle {
                z: -1
                width: parent.width
                height: parent.height
                y: 3
                color: "#33000000"
                radius: 6
            }
        }
        contentItem: Text {
            text: parent.text
            color: "white"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 14
            font.bold: true
        }
        Connections {
            function onClicked() {
                root.backClicked()
            }
        }
    }

    Text {
        id: statusMessageText
        anchors.right: (startElectionBtn.visible ? startElectionBtn.left : (backToMainBtn.visible ? backToMainBtn.left : parent.right))
        anchors.rightMargin: (startElectionBtn.visible || backToMainBtn.visible) ? 15 : 45
        anchors.verticalCenter: startElectionBtn.verticalCenter
        width: 480
        text: root.statusMessage
        color: root.statusIsError ? "#d9534f" : "#1e7e34"
        font.pixelSize: 13
        font.bold: true
        horizontalAlignment: Text.AlignRight
        wrapMode: Text.WordWrap
        visible: root.statusMessage !== ""
    }
}
