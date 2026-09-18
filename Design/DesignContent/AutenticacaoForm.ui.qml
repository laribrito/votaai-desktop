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
    id: root
    width: Constants.width
    height: Constants.height
    color: "#e8e8e8"

    property string errorMessage: ""
    property bool isLoading: false
    property bool isPasswordVisible: false
    property string registeredEmailText: ""
    property string registeredNameText: ""

    property alias emailDisplayInput: emailDisplayInput
    property alias passwordInput: passwordInput
    property alias totpInput: totpInput
    property alias submitLoginBtn: submitLoginBtn
    property alias togglePasswordBtn: togglePasswordBtn

    signal submitLoginClicked
    signal togglePasswordVisibilityClicked

    // Cabeçalho da Página
    Text {
        id: text1
        x: 45
        y: 47
        text: qsTr("Autenticação de Dois Fatores (2FA)")
        font.pixelSize: 22
        font.weight: Font.Bold
        color: "#222222"
    }

    Text {
        id: text2
        x: 45
        y: 81
        text: qsTr("Confirme sua senha e código de autenticação para gerenciar o sistema eleitoral")
        font.pixelSize: 13
        font.weight: Font.Light
        color: "#555555"
    }

    // Campo E-mail
    Text {
        id: labelEmail
        x: 45
        y: 138
        text: qsTr("E-mail")
        font.pixelSize: 12
        color: "#333333"
    }

    Rectangle {
        id: emailBox
        x: 45
        y: 163
        width: 450
        height: 35
        color: "#f0f0f0"
        radius: 4
        border.color: "#a0a0a0"
        border.width: 1

        TextField {
            id: emailDisplayInput
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            text: root.registeredEmailText
            readOnly: true
            color: "#555555"
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
            clip: true
            background: Item {}
        }
    }

    // Campo Senha
    Text {
        id: labelPassword
        x: 45
        y: 218
        text: qsTr("Senha")
        font.pixelSize: 12
        color: "#333333"
    }

    Rectangle {
        id: passwordBox
        x: 45
        y: 243
        width: 450
        height: 35
        color: "#ffffff"
        radius: 4
        border.color: "#a0a0a0"
        border.width: 1

        TextField {
            id: passwordInput
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 36
            echoMode: root.isPasswordVisible ? TextInput.Normal : TextInput.Password
            placeholderText: qsTr("Digite sua senha de administrador")
            color: "#333333"
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
            clip: true
            background: Item {}
        }

        Item {
            id: togglePasswordBtn
            anchors.right: parent.right
            anchors.rightMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            width: 24
            height: 24

            Text {
                anchors.centerIn: parent
                text: root.isPasswordVisible ? "👁" : "👁‍🗨"
                font.pixelSize: 14
                color: eyeMouseArea.containsMouse ? "#111827" : "#777777"
            }

            MouseArea {
                id: eyeMouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    root.togglePasswordVisibilityClicked()
                }
            }
        }
    }

    // Campo Código de Autenticação (TOTP)
    Text {
        id: labelTotp
        x: 45
        y: 298
        text: qsTr("Código de Autenticação (TOTP)")
        font.pixelSize: 12
        color: "#333333"
    }

    Rectangle {
        id: totpBox
        x: 45
        y: 323
        width: 450
        height: 35
        color: "#ffffff"
        radius: 4
        border.color: "#a0a0a0"
        border.width: 1

        TextField {
            id: totpInput
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            placeholderText: qsTr("000000")
            color: "#333333"
            font.pixelSize: 13
            maximumLength: 6
            inputMethodHints: Qt.ImhDigitsOnly
            verticalAlignment: Text.AlignVCenter
            clip: true
            background: Item {}
        }
    }

    Text {
        id: textTotpHint
        x: 45
        y: 365
        text: qsTr("Digite o código de 6 dígitos gerado pelo seu aplicativo autenticador.")
        font.pixelSize: 11
        font.weight: Font.Light
        color: "#666666"
    }

    // Mensagem de Erro
    Text {
        id: errorText
        x: 45
        y: 395
        width: 450
        text: root.errorMessage
        color: "#d9534f"
        font.pixelSize: 12
        font.bold: true
        wrapMode: Text.WordWrap
        visible: root.errorMessage !== ""
    }

    // Botão de Ação Principal (Canto Inferior Direito)
    Button {
        id: submitLoginBtn
        x: Constants.width - width - 45
        y: Constants.height - height - 30
        width: 200
        height: 40
        text: root.isLoading ? qsTr("Autenticando...") : qsTr("Autenticar e Acessar")
        enabled: !root.isLoading

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
                root.submitLoginClicked()
            }
        }
    }
}
