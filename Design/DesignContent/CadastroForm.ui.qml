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

    property int currentStep: 1
    property string errorMessage: ""
    property string qrCodeSource: ""
    property string secretKeyText: ""
    property bool isLoading: false
    property bool isAlreadyRegistered: false
    property string registeredEmailText: ""

    property alias emailInput: emailInput
    property alias passwordInput: passwordInput
    property alias confirmPasswordInput: confirmPasswordInput
    property alias submitPreCadastroBtn: submitPreCadastroBtn

    property alias totpInput: totpInput
    property alias submitTotpBtn: submitTotpBtn

    property alias copySecretBtn: copySecretBtn
    property alias backToStep1Btn: backToStep1Btn
    property alias accessMainBtn: accessMainBtn
    property alias directAccessBtn: directAccessBtn

    signal submitPreCadastroClicked
    signal submitTotpClicked
    signal copySecretClicked
    signal backToStep1Clicked
    signal accessMainClicked
    signal directAccessClicked

    // Cabeçalho da Página
    Text {
        id: text1
        x: 45
        y: 47
        text: root.currentStep === 2 ? qsTr("Autenticação em Duas Etapas (TOTP)") : (root.currentStep === 3 ? qsTr("Cadastro Concluído") : qsTr("Pré-cadastro de Administrador"))
        font.pixelSize: 22
        font.weight: Font.Bold
        color: "#222222"
    }

    Text {
        id: text2
        x: 45
        y: 81
        text: root.currentStep === 2 ? qsTr("Escaneie o QR Code com seu aplicativo autenticador e digite o código de 6 dígitos") : (root.currentStep === 3 ? qsTr("Sua máquina foi vinculada e o usuário administrador foi ativado") : qsTr("Cadastre suas credenciais e vincule sua máquina com segurança de hardware"))
        font.pixelSize: 13
        font.weight: Font.Light
        color: "#555555"
    }

    // ==========================================
    // ETAPA 1: Credenciais e Hardware TPM
    // ==========================================
    Item {
        id: step1Item
        x: 0
        y: 0
        width: parent.width
        height: parent.height
        visible: root.currentStep === 1

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
            x: 45
            y: 163
            width: 450
            height: 35
            color: "#ffffff"
            radius: 4
            border.color: "#a0a0a0"
            border.width: 1

            TextField {
                id: emailInput
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                placeholderText: qsTr("admin@uesc.br")
                color: "#333333"
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
                anchors.rightMargin: 8
                echoMode: TextInput.Password
                placeholderText: qsTr("Mínimo de 8 caracteres")
                color: "#333333"
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
                clip: true
                background: Item {}
            }
        }

        // Campo Confirmar Senha
        Text {
            id: labelConfirmPassword
            x: 45
            y: 298
            text: qsTr("Confirmar Senha")
            font.pixelSize: 12
            color: "#333333"
        }

        Rectangle {
            x: 45
            y: 323
            width: 450
            height: 35
            color: "#ffffff"
            radius: 4
            border.color: "#a0a0a0"
            border.width: 1

            TextField {
                id: confirmPasswordInput
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                echoMode: TextInput.Password
                placeholderText: qsTr("Repita a mesma senha")
                color: "#333333"
                font.pixelSize: 12
                verticalAlignment: Text.AlignVCenter
                clip: true
                background: Item {}
            }
        }

        // Mensagem de Erro
        Text {
            id: errorStep1
            x: 45
            y: 375
            width: 450
            text: root.errorMessage
            color: "#d9534f"
            font.pixelSize: 12
            font.bold: true
            wrapMode: Text.WordWrap
            visible: root.errorMessage !== ""
        }

        // Seção caso a máquina já esteja registrada
        Column {
            x: 45
            y: 430
            spacing: 8
            visible: root.isAlreadyRegistered

            Text {
                text: qsTr("Esta máquina já está vinculada (" + root.registeredEmailText + ").")
                font.pixelSize: 12
                color: "#555555"
            }

            Button {
                id: directAccessBtn
                width: 180
                height: 30
                text: qsTr("Ir para o Painel")

                background: Rectangle {
                    color: parent.down ? "#2b3d4f" : (parent.hovered ? "#3e5770" : "#34495e")
                    radius: 4
                    Rectangle {
                        z: -1
                        width: parent.width
                        height: parent.height
                        y: 2
                        color: "#26000000"
                        radius: 4
                    }
                }
                contentItem: Text {
                    text: parent.text
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 12
                }
                Connections {
                    function onClicked() {
                        root.directAccessClicked()
                    }
                }
            }
        }

        // Botão de Ação Principal (Canto Inferior Direito)
        Button {
            id: submitPreCadastroBtn
            x: Constants.width - width - 45
            y: Constants.height - height - 30
            width: 220
            height: 40
            text: root.isLoading ? qsTr("Criando Chave...") : qsTr("Criar Chave e Cadastrar")
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
                    root.submitPreCadastroClicked()
                }
            }
        }
    }

    // ==========================================
    // ETAPA 2: Segundo Fator de Autenticação (TOTP)
    // ==========================================
    Item {
        id: step2Item
        x: 0
        y: 0
        width: parent.width
        height: parent.height
        visible: root.currentStep === 2

        // Lado Esquerdo: QR Code
        Text {
            id: labelQrCode
            x: 45
            y: 138
            text: qsTr("QR Code do Aplicativo Autenticador")
            font.pixelSize: 12
            color: "#333333"
        }

        Rectangle {
            x: 45
            y: 163
            width: 200
            height: 200
            color: "#ffffff"
            radius: 4
            border.color: "#a0a0a0"
            border.width: 1

            Image {
                id: qrImage
                anchors.fill: parent
                anchors.margins: 8
                fillMode: Image.PreserveAspectFit
                source: root.qrCodeSource
                cache: false
            }
        }

        Text {
            x: 45
            y: 380
            text: qsTr("Chave manual: ") + root.secretKeyText
            font.pixelSize: 11
            font.family: "Courier New"
            color: "#555555"
        }

        Button {
            id: copySecretBtn
            x: 45
            y: 405
            width: 120
            height: 30
            text: qsTr("Copiar Chave")

            background: Rectangle {
                color: parent.down ? "#2b3d4f" : (parent.hovered ? "#3e5770" : "#34495e")
                radius: 4
                Rectangle {
                    z: -1
                    width: parent.width
                    height: parent.height
                    y: 2
                    color: "#26000000"
                    radius: 4
                }
            }
            contentItem: Text {
                text: parent.text
                color: "white"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 12
            }
            Connections {
                function onClicked() {
                    root.copySecretClicked()
                }
            }
        }

        // Lado Direito: Campo TOTP
        Text {
            id: labelTotp
            x: 285
            y: 138
            text: qsTr("Código de 6 dígitos gerado pelo aplicativo")
            font.pixelSize: 12
            color: "#333333"
        }

        Rectangle {
            x: 285
            y: 163
            width: 210
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
                font.pixelSize: 14
                font.bold: true
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                clip: true
                maximumLength: 6
                inputMethodHints: Qt.ImhDigitsOnly
                background: Item {}
            }
        }

        Text {
            x: 285
            y: 215
            width: 340
            text: qsTr("Abra o Google Authenticator ou Microsoft Authenticator em seu celular para escanear o QR Code e digitar o código gerado.")
            font.pixelSize: 12
            font.weight: Font.Light
            color: "#555555"
            wrapMode: Text.WordWrap
        }

        Text {
            id: errorStep2
            x: 285
            y: 280
            width: 340
            text: root.errorMessage
            color: "#d9534f"
            font.pixelSize: 12
            font.bold: true
            wrapMode: Text.WordWrap
            visible: root.errorMessage !== ""
        }

        // Botão Voltar (Inferior Esquerdo)
        Button {
            id: backToStep1Btn
            x: 45
            y: Constants.height - height - 30
            width: 120
            height: 40
            text: qsTr("Voltar")

            background: Rectangle {
                color: parent.down ? "#999999" : (parent.hovered ? "#aaaaaa" : "transparent")
                border.color: "#a0a0a0"
                border.width: 1
                radius: 4
            }
            contentItem: Text {
                text: parent.text
                color: "#333333"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.pixelSize: 14
            }
            Connections {
                function onClicked() {
                    root.backToStep1Clicked()
                }
            }
        }

        // Botão Confirmar e Ativar (Inferior Direito)
        Button {
            id: submitTotpBtn
            x: Constants.width - width - 45
            y: Constants.height - height - 30
            width: 200
            height: 40
            text: root.isLoading ? qsTr("Validando...") : qsTr("Confirmar e Ativar")
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
                    root.submitTotpClicked()
                }
            }
        }
    }

    // ==========================================
    // ETAPA 3: Concluído com Sucesso
    // ==========================================
    Item {
        id: step3Item
        x: 0
        y: 0
        width: parent.width
        height: parent.height
        visible: root.currentStep === 3

        Text {
            x: 45
            y: 150
            width: 600
            text: qsTr("✓ Administrador ativado e máquina vinculada!")
            font.pixelSize: 16
            font.weight: Font.Bold
            color: "#1e7e34"
        }

        Text {
            x: 45
            y: 190
            width: 600
            text: qsTr("Esta máquina física agora possui as credenciais criptográficas de hardware (TPM) necessárias para gerenciar as eleições com total integridade e sigilo.")
            font.pixelSize: 13
            font.weight: Font.Light
            color: "#555555"
            wrapMode: Text.WordWrap
        }

        Button {
            id: accessMainBtn
            x: Constants.width - width - 45
            y: Constants.height - height - 30
            width: 200
            height: 40
            text: qsTr("Ir para o Painel")

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
                    root.accessMainClicked()
                }
            }
        }
    }
}
