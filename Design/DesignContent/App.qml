import QtQuick
import QtQuick.Controls
import Design

Window {
    id: appWindow

    // Margem de segurança para decorações da janela do SO (barra de títulos/bordas)
    readonly property int windowDecorationMargin: 40
    readonly property bool isCompactWidth: Screen.desktopAvailableWidth < Constants.width
    readonly property bool isCompactHeight: (Screen.desktopAvailableHeight - windowDecorationMargin) < Constants.height

    width: isCompactWidth ? Screen.desktopAvailableWidth : Constants.width
    height: isCompactHeight ? (Screen.desktopAvailableHeight - windowDecorationMargin) : Constants.height
    minimumWidth: width
    maximumWidth: width
    minimumHeight: height
    maximumHeight: height

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

