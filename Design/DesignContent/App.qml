import QtQuick
import QtQuick.Controls
import Design

Window {
    id: appWindow

    // Margem de segurança para decorações da janela do SO (barra de títulos, painel do sistema e bordas)
    readonly property int windowDecorationMargin: 80
    readonly property bool isCompactWidth: Screen.desktopAvailableWidth < Constants.width
    readonly property bool isCompactHeight: (Screen.desktopAvailableHeight - windowDecorationMargin) < Constants.height

    width: isCompactWidth ? Math.max(1024, Screen.desktopAvailableWidth - 20) : Constants.width
    height: isCompactHeight ? Math.max(680, Screen.desktopAvailableHeight - windowDecorationMargin) : Constants.height
    minimumWidth: Math.min(1024, width)
    maximumWidth: Constants.width
    minimumHeight: Math.min(680, height)
    maximumHeight: Constants.height

    flags: Qt.Window | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint
    visible: true
    title: "Vota Aí"

    function navigateTo(page) {
        return stackView.push(page)
    }

    function popPage() {
        return stackView.pop()
    }

    Component {
        id: mainComponent
        Main {
            onCriarEleicaoClicked: {
                var item = stackView.push("Criacao.qml")
                if (item) {
                    item.backClicked.connect(function() { stackView.pop() })
                }
            }
            onIniciarEleicaoClicked: {
                var item = stackView.push("Iniciar.qml")
                if (item) {
                    item.backClicked.connect(function() { stackView.pop() })
                }
            }
            onFecharEleicaoClicked: {
                var item = stackView.push("Fechar.qml")
                if (item) {
                    item.backClicked.connect(function() { stackView.pop() })
                }
            }
            onApurarEleicaoClicked: {
                var item = stackView.push("Apurar.qml")
                if (item) {
                    item.backClicked.connect(function() { stackView.pop() })
                }
            }
        }
    }

    Component {
        id: autenticacaoComponent
        Autenticacao {
            onLoginSucesso: {
                stackView.replace(mainComponent)
            }
            onAuditarClicked: {
                var item = stackView.push("Auditoria.qml")
                if (item) {
                    item.backClicked.connect(function() { stackView.pop() })
                }
            }
        }
    }

    Component {
        id: cadastroComponent
        Cadastro {
            onCadastroConcluido: {
                // Cadastro concluído
            }
            onIrParaMainClicked: {
                stackView.replace(autenticacaoComponent)
            }
            onAuditarClicked: {
                var item = stackView.push("Auditoria.qml")
                if (item) {
                    item.backClicked.connect(function() { stackView.pop() })
                }
            }
        }
    }

    Flickable {
        id: flickable
        anchors.fill: parent
        contentWidth: width
        contentHeight: stackView.currentItem ? Math.max(height, stackView.currentItem.height) : height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        ScrollBar.vertical: ScrollBar {
            id: verticalScrollBar
            policy: flickable.contentHeight > flickable.height ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded
        }

        StackView {
            id: stackView
            objectName: "stackView"
            width: flickable.width
            height: Math.max(flickable.height, currentItem ? currentItem.height : flickable.height)
            initialItem: (typeof authController !== 'undefined' && authController && authController.isRegistered) 
                         ? (authController.isAuthenticated ? mainComponent : autenticacaoComponent) 
                         : cadastroComponent

            onCurrentItemChanged: {
                flickable.contentY = 0
            }
        }

        ResponsibleUserBadge {
            id: responsibleUserBadge
            objectName: "responsibleUserBadge"
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.topMargin: 47
            anchors.rightMargin: 45
            z: 999
            visible: (typeof authController !== 'undefined' && authController && authController.isRegistered)
        }
    }
}

