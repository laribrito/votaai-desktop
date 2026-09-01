import QtQuick
import QtQuick.Controls
import Design

Window {
    width: stackView.currentItem ? stackView.currentItem.width : 640
    height: stackView.currentItem ? stackView.currentItem.height : 480

    visible: true
    title: "Vota Aí"

    StackView {
        id: stackView
        anchors.fill: parent
        initialItem: Main {
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
            onTestConnectionClicked: {
                testResult = backend.testConnection()
            }
        }
    }
}
