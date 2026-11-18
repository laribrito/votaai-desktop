/*
This is a UI file (.ui.qml) that is intended to be edited in Qt Design Studio only.
It is supposed to be strictly declarative and only uses a subset of QML. If you edit
this file manually, you might introduce QML code that is not supported by Qt Design Studio.
Check out https://doc.qt.io/qtcreator/creator-quick-ui-forms.html for details on .ui.qml files.
*/
import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import Design
import QtQuick.Studio.DesignEffects

Rectangle {
    id: root
    width: parent ? parent.width : Constants.width
    height: Constants.height
    color: "#e8e8e8"

    property alias zipPathDisplay: zipPathDisplay
    property alias browseBtn: browseBtn
    property alias actionBtn: actionBtn
    property alias newAuditBtn: newAuditBtn
    property alias fileDialog: fileDialog

    property bool isLoading: false
    property bool hasSelectedFile: false
    property string statusMessage: ""
    property bool statusIsError: false
    property bool isAuditCompleted: false
    property bool isAuditValid: false
    property string auditDetailsText: ""

    signal backClicked
    signal browseClicked
    signal auditClicked
    signal newAuditClicked

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
        text: qsTr("Auditoria de Eleição")
        font.pixelSize: 22
        font.weight: Font.Bold
        color: "#222222"
    }

    Text {
        id: text2
        x: 45
        y: 81
        text: qsTr("Importe o pacote ZIP oficial para decifrar as cédulas e conferir o hash da eleição")
        font.pixelSize: 13
        font.weight: Font.Light
        color: "#555555"
    }

    // Seleção do Arquivo ZIP
    Text {
        id: labelZip
        x: 45
        y: 138
        text: qsTr("Pacote de Auditoria (.zip)")
        font.pixelSize: 12
        color: "#333333"
    }

    Rectangle {
        id: zipBox
        x: 45
        y: 163
        width: Math.min(480, root.width - 210)
        height: 35
        color: "#ffffff"
        radius: 4
        border.color: "#a0a0a0"
        border.width: 1

        TextField {
            id: zipPathDisplay
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            readOnly: true
            placeholderText: qsTr("Nenhum arquivo .zip selecionado...")
            color: "#333333"
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
            clip: true
            background: Item {}
        }
    }

    Button {
        id: browseBtn
        x: zipBox.x + zipBox.width + 15
        y: 163
        width: 130
        height: 35
        text: qsTr("Selecionar...")
        enabled: !root.isLoading && !root.isAuditCompleted

        background: Rectangle {
            color: parent.down ? "#2b3d4f" : (parent.hovered ? "#3e5770" : "#34495e")
            radius: 4
        }
        contentItem: Text {
            text: parent.text
            color: "white"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 12
            font.bold: true
        }
        Connections {
            function onClicked() {
                root.browseClicked()
            }
        }
    }

    // Painel de Resultados da Auditoria
    Rectangle {
        id: resultsContainer
        x: 45
        y: 215
        width: Math.min(650, root.width - 90)
        height: Math.max(160, Constants.height - y - 85)
        color: "#ffffff"
        radius: 6
        border.color: root.isAuditValid ? "#1e7e34" : "#d9534f"
        border.width: 1
        visible: root.isAuditCompleted

        Text {
            id: resultsTitle
            x: 15
            y: 12
            text: root.isAuditValid
                  ? qsTr("✓ Integridade Confirmada! O hash calculado confere com a ata oficial.")
                  : qsTr("✗ Divergência Detectada! O hash calculado difere da ata oficial.")
            font.pixelSize: 13
            font.bold: true
            color: root.isAuditValid ? "#1e7e34" : "#d9534f"
        }

        Flickable {
            id: resultsFlickable
            x: 15
            y: 35
            width: parent.width - 30
            height: parent.height - 45
            contentWidth: resultsText.paintedWidth
            contentHeight: resultsText.paintedHeight
            clip: true

            Text {
                id: resultsText
                width: resultsFlickable.width
                text: root.auditDetailsText
                font.pixelSize: 12
                font.family: "Monospace"
                color: "#222222"
                wrapMode: Text.WordWrap
            }
        }
    }

    // Botão de Realizar Auditoria
    Button {
        id: actionBtn
        x: root.width - width - 45
        y: Constants.height - height - 30
        width: 180
        height: 40
        text: root.isLoading ? qsTr("Auditando...") : qsTr("Realizar Auditoria")
        enabled: !root.isLoading && root.hasSelectedFile && !root.isAuditCompleted
        visible: !root.isAuditCompleted
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
        Connections {
            function onClicked() {
                root.auditClicked()
            }
        }
    }

    // Botão Nova Auditoria (quando auditoria já foi concluída)
    Button {
        id: newAuditBtn
        x: root.width - width - 45
        y: Constants.height - height - 30
        width: 180
        height: 40
        text: qsTr("Nova Auditoria")
        visible: root.isAuditCompleted

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
                root.newAuditClicked()
            }
        }
    }

    Text {
        id: statusMessageText
        anchors.right: (actionBtn.visible ? actionBtn.left : (newAuditBtn.visible ? newAuditBtn.left : parent.right))
        anchors.rightMargin: (actionBtn.visible || newAuditBtn.visible) ? 15 : 45
        anchors.verticalCenter: (actionBtn.visible ? actionBtn.verticalCenter : newAuditBtn.verticalCenter)
        width: Math.min(450, root.width - 250)
        text: root.statusMessage
        color: root.statusIsError ? "#d9534f" : "#1e7e34"
        font.pixelSize: 13
        font.bold: true
        horizontalAlignment: Text.AlignRight
        wrapMode: Text.WordWrap
        visible: root.statusMessage !== ""
    }

    FileDialog {
        id: fileDialog
        title: qsTr("Selecione o Pacote de Auditoria (.zip)")
        nameFilters: [qsTr("Arquivos ZIP (*.zip)"), qsTr("Todos os Arquivos (*)")]
    }
}
