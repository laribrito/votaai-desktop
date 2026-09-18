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

                Item {
                    id: eyeIconItem
                    width: 16
                    height: 14
                    anchors.verticalCenter: parent.verticalCenter

                    Canvas {
                        id: eyeCanvas
                        anchors.centerIn: parent
                        width: 16
                        height: 14
                        property bool isVisible: root.isEmailVisible
                        property color eyeColor: rowMouseArea.containsMouse ? "#111827" : "#666666"

                        onIsVisibleChanged: requestPaint()
                        onEyeColorChanged: requestPaint()

                        onPaint: {
                            var ctx = getContext("2d");
                            ctx.reset();
                            ctx.strokeStyle = eyeColor;
                            ctx.lineWidth = 1.3;
                            ctx.lineCap = "round";
                            ctx.lineJoin = "round";

                            var w = width;
                            var h = height;

                            // Contorno do olho
                            ctx.beginPath();
                            ctx.moveTo(1, h / 2);
                            ctx.quadraticCurveTo(w / 2, 0.5, w - 1, h / 2);
                            ctx.quadraticCurveTo(w / 2, h - 0.5, 1, h / 2);
                            ctx.stroke();

                            // Pupila
                            ctx.beginPath();
                            ctx.arc(w / 2, h / 2, 2.2, 0, 2 * Math.PI);
                            if (isVisible) {
                                ctx.fillStyle = eyeColor;
                                ctx.fill();
                            } else {
                                ctx.stroke();
                                // Linha diagonal cortando o olho quando oculto
                                ctx.beginPath();
                                ctx.moveTo(2, 2);
                                ctx.lineTo(w - 2, h - 2);
                                ctx.stroke();
                            }
                        }
                    }
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
