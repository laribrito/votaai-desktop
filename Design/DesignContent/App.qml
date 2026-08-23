import QtQuick
import QtQuick.Controls
import Design

Window {
    width: stackView.currentItem ? stackView.currentItem.width : 640
    height: stackView.currentItem ? stackView.currentItem.height : 480

    visible: true
    title: "Design"

    StackView {
        id: stackView
        anchors.fill: parent
        initialItem: Main {
            onCriarEleicaoClicked: {
                stackView.push("Criacao.ui.qml")
            }
        }
    }
}
