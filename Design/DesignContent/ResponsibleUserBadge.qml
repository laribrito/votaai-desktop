import QtQuick
import QtQuick.Controls

Item {
    id: root
    implicitWidth: contentColumn.implicitWidth
    implicitHeight: contentColumn.implicitHeight

    property bool isEmailVisible: false

    Column {
        id: contentColumn
        anchors.right: parent.right
        spacing: 3

        Text {
            id: labelText
            anchors.right: parent.right
            text: qsTr("Responsável da máquina")
            font.pixelSize: 11
            color: "#666666"
        }

        Text {
            id: userNameText
            anchors.right: parent.right
            text: (typeof authController !== 'undefined' && authController && authController.registeredUserName)
                  ? authController.registeredUserName
                  : ""
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: "#222222"
        }

        Item {
            id: emailContainer
            anchors.right: parent.right
            width: emailRow.implicitWidth
            height: emailRow.implicitHeight

            Row {
                id: emailRow
                spacing: 6
                anchors.verticalCenter: parent.verticalCenter

                Text {
                    id: emailDisplay
                    anchors.verticalCenter: parent.verticalCenter
                    text: {
                        var fullEmail = (typeof authController !== 'undefined' && authController && authController.registeredEmail)
                                        ? authController.registeredEmail
                                        : "";
                        if (!fullEmail) return "";
                        return root.isEmailVisible ? fullEmail : "••••••••••••••••••••";
                    }
                    font.pixelSize: 11
                    color: rowMouseArea.containsMouse ? "#111827" : "#666666"
                    font.letterSpacing: root.isEmailVisible ? 0 : 1
                }

                EyeIcon {
                    id: eyeIconItem
                    anchors.verticalCenter: parent.verticalCenter
                    isVisible: root.isEmailVisible
                    eyeColor: rowMouseArea.containsMouse ? "#111827" : "#666666"
                }
            }

            MouseArea {
                id: rowMouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.isEmailVisible = !root.isEmailVisible
                }

                ToolTip.visible: containsMouse
                ToolTip.text: root.isEmailVisible ? qsTr("Ocultar e-mail") : qsTr("Visualizar e-mail")
                ToolTip.delay: 300
            }
        }
    }
}
