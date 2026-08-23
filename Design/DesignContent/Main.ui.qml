

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
    width: Constants.width
    height: Constants.height
    color: "#bcbcbc"

    signal criarEleicaoClicked()

    Text {
        id: text1
        x: 45
        y: 47
        text: qsTr("Vota ai")
        font.pixelSize: 22
        font.weight: Font.Bold
    }

    Text {
        id: text2
        x: 45
        y: 81
        text: qsTr("Selecione uma ação para gerenciar o sistema eleitoral.")
        font.pixelSize: 13
        font.weight: Font.Light
    }

    Grid {
        id: grid
        x: 45
        y: 133
        width: 556
        height: 252
        spacing: 35
        horizontalItemAlignment: Grid.AlignLeft
        rows: 2
        columns: 2

        Rectangle {
            id: rectangle7
            width: 260
            height: 109
            color: "#ffffff"
            radius: 5
            border.color: "#ababab"
            border.width: 1

            MouseArea {
                id: mouseAreaCriarEleicao
                anchors.fill: parent
                onClicked: criarEleicaoClicked()
            }

            Text {
                id: text9
                x: 16
                y: 50
                width: 167
                height: 51
                color: "#3d3d3d"
                text: qsTr("Cadastre o colégio eleitoral e as questões da cédula")
                font.pixelSize: 10
                wrapMode: Text.WordWrap
            }

            Text {
                id: text10
                x: 16
                y: 22
                text: qsTr("Criar Eleição")
                font.pixelSize: 12
                font.weight: Font.Medium
            }

            Image {
                id: image4
                x: 203
                y: 15
                width: 40
                height: 40
                source: "../../app/resources/plus.png"
                fillMode: Image.PreserveAspectFit
            }
        }

        Rectangle {
            id: rectangle8
            width: 260
            height: 109
            color: "#ffffff"
            radius: 5
            border.color: "#ababab"
            border.width: 1
            Text {
                id: text11
                x: 16
                y: 50
                width: 167
                height: 51
                color: "#3d3d3d"
                text: qsTr("Permitir recebimento de votos")
                font.pixelSize: 10
                wrapMode: Text.WordWrap
            }

            Text {
                id: text12
                x: 16
                y: 22
                text: qsTr("Iniciar Eleição")
                font.pixelSize: 12
                font.weight: Font.Medium
            }

            Image {
                id: image5
                x: 203
                y: 15
                width: 40
                height: 40
                source: "../../app/resources/play.png"
                fillMode: Image.PreserveAspectFit
            }
        }

        Rectangle {
            id: rectangle9
            width: 260
            height: 109
            color: "#ffffff"
            radius: 5
            border.color: "#ababab"
            border.width: 1
            Text {
                id: text13
                x: 16
                y: 50
                width: 167
                height: 51
                color: "#3d3d3d"
                text: qsTr("Finalizar recebimento de votos")
                font.pixelSize: 10
                wrapMode: Text.WordWrap
            }

            Text {
                id: text14
                x: 16
                y: 22
                text: qsTr("Fechar Eleição")
                font.pixelSize: 12
                font.weight: Font.Medium
            }

            Image {
                id: image6
                x: 203
                y: 15
                width: 40
                height: 40
                source: "../../app/resources/close.png"
                fillMode: Image.PreserveAspectFit
            }
        }

        Rectangle {
            id: rectangle10
            width: 260
            height: 109
            color: "#ffffff"
            radius: 5
            border.color: "#ababab"
            border.width: 1
            Text {
                id: text15
                x: 16
                y: 50
                width: 167
                height: 51
                color: "#3d3d3d"
                text: qsTr("Contabilizar votos e gerar relatório")
                font.pixelSize: 10
                wrapMode: Text.WordWrap
            }

            Text {
                id: text16
                x: 16
                y: 22
                text: qsTr("Apurar Eleição")
                font.pixelSize: 12
                font.weight: Font.Medium
            }

            Image {
                id: image7
                x: 203
                y: 15
                width: 40
                height: 40
                source: "../../app/resources/graph.png"
                fillMode: Image.PreserveAspectFit
            }
        }
    }
}
