import QtQuick
import QtQuick.Controls
import Design

Window {
    id: appWindow
    width: stackView.currentItem ? stackView.currentItem.width : Constants.width
    height: stackView.currentItem ? stackView.currentItem.height : Constants.height

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
        id: cadastroComponent
        Cadastro {
            onCadastroConcluido: {
                // Cadastro concluído
            }
            onIrParaMainClicked: {
                stackView.replace(mainComponent)
            }
        }
    }

    StackView {
        id: stackView
        objectName: "stackView"
        anchors.fill: parent
        initialItem: (typeof authController !== 'undefined' && authController && authController.isRegistered) ? mainComponent : cadastroComponent
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

