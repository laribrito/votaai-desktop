

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
import QtQuick.Dialogs

Rectangle {
    width: Constants.width
    height: Constants.height
    color: "#e8e8e8"

    id: root

    property alias textInput: textInput
    property alias csvInput: csvInput
    property alias browseButton: browseButton
    property alias downloadTemplateBtn: downloadTemplateBtn
    property alias searchInput: searchInput
    property alias tableView: tableView
    property alias addQuestionBtn: addQuestionBtn
    property alias questionsList: questionsList
    property alias createElectionBtn: createElectionBtn
    property alias fileDialog: fileDialog
    property alias saveFileDialog: saveFileDialog
    property alias questionsModel: questionsModel

    property bool isValidCsv: false
    property string csvErrorMessage: ""
    property bool hasValidQuestion: false

    signal backClicked
    signal moveQuestionUpClicked(int index)
    signal moveQuestionDownClicked(int index)
    signal questionTextEdited(int index, string text)
    signal addOptionClicked(int index)
    signal optionTextEdited(int questionIndex, int optionIndex, string text)

    Button {
        id: backButton
        x: 45
        y: 12
        width: 30
        height: 30
        text: "←"

        background: Rectangle {
            color: parent.down ? "#999999" : (parent.hovered ? "#aaaaaa" : "transparent")
            radius: 4
        }
        contentItem: Text {
            text: parent.text
            color: "#333333"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 22
            font.bold: true
        }
        Connections {


            function onClicked() {
                root.backClicked()
            }
        }
    }

    Text {
        id: text1
        x: 45
        y: 47
        text: qsTr("Criar Eleição")
        font.pixelSize: 22
        font.weight: Font.Bold
    }

    Text {
        id: text2
        x: 45
        y: 81
        text: qsTr("Adicione um csv e configure a cédula da eleição")
        font.pixelSize: 13
        font.weight: Font.Light
    }

    Rectangle {
        x: 45
        y: 163
        width: 450
        height: 30
        color: "#ffffff"
        radius: 4
        border.color: "#a0a0a0"
        border.width: 1

        TextField {
            id: textInput
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            placeholderText: qsTr("Título da eleição")
            color: "#333333"
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
            clip: true
            background: Item {}
        }
    }

    Text {
        id: text3
        x: 45
        y: 138
        text: qsTr("Título")
        font.pixelSize: 12
    }

    Text {
        id: textCsv
        x: 45
        y: 208
        text: qsTr("Arquivo CSV (Colégio Eleitoral)")
        font.pixelSize: 12
    }

    Rectangle {
        x: 45
        y: 233
        width: 335
        height: 30
        color: "#ffffff"
        radius: 4
        border.color: "#a0a0a0"
        border.width: 1

        TextField {
            id: csvInput
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            placeholderText: qsTr("Selecione um arquivo .csv")
            color: "#666666"
            font.pixelSize: 12
            verticalAlignment: Text.AlignVCenter
            clip: true
            readOnly: true
            background: Item {}
        }
    }

    Button {
        id: browseButton
        x: 395
        y: 233
        width: 100
        height: 30
        text: qsTr("Procurar...")

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
    }

    Column {
        x: 45
        y: 290
        width: 450
        spacing: 15
        visible: !isValidCsv

        Text {
            text: csvErrorMessage
                  !== "" ? csvErrorMessage : qsTr(
                               "Apenas serão aceitos eleitores com emails institucionais ("
                               + (typeof institutionalDomain
                                  !== 'undefined' ? institutionalDomain : "@uesc.br") + ")")
            color: csvInput.text !== ""
                   && csvInput.text !== "Arquivo selecionado é inválido!" ? "#d9534f" : (csvInput.text === "Arquivo selecionado é inválido!" ? "#d9534f" : "#555555")
            font.pixelSize: 12
            font.bold: csvInput.text !== ""
            horizontalAlignment: Text.AlignHCenter
            width: parent.width
            wrapMode: Text.WordWrap
        }

        Button {
            id: downloadTemplateBtn
            anchors.horizontalCenter: parent.horizontalCenter
            width: 180
            height: 30
            text: qsTr("Baixar Modelo CSV")

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
                    saveFileDialog.open()
                }
            }
        }
    }

    Column {
        x: 45
        y: 290
        width: 450
        spacing: 15
        visible: isValidCsv

        Row {
            spacing: 10
            width: parent.width

            Text {
                text: qsTr("Pré-visualização: (" + tableView.rows
                           + (tableView.rows === 1 ? " eleitor)" : " eleitores)"))
                font.pixelSize: 12
                font.weight: Font.Medium
                anchors.verticalCenter: parent.verticalCenter
            }

            Item {
                width: parent.width - parent.children[0].width - 10
                height: 25

                TextField {
                    id: searchInput
                    anchors.right: parent.right
                    width: 200
                    height: 25
                    placeholderText: qsTr("Buscar eleitor...")
                    font.pixelSize: 12
                    color: "#333333"

                    background: Rectangle {
                        border.color: "#a0a0a0"
                        border.width: 1
                        radius: 4
                        color: "#ffffff"
                    }
                }
            }
        }

        Rectangle {
            width: parent.width
            height: 360
            border.color: "#a0a0a0"
            border.width: 1
            radius: 4
            clip: true

            HorizontalHeaderView {
                id: horizontalHeader
                syncView: tableView
                anchors.left: tableView.left
                anchors.top: parent.top
                anchors.topMargin: 1
                anchors.leftMargin: 1
                clip: true
                height: 30
            }

            TableView {
                id: tableView
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: horizontalHeader.bottom
                anchors.bottom: parent.bottom
                anchors.margins: 1

                model: typeof backend !== 'undefined'
                       && backend ? backend.csvModel : null
                clip: true

                delegate: Rectangle {
                    implicitWidth: 200
                    implicitHeight: 30
                    border.color: "#e0e0e0"
                    border.width: 1
                    Text {
                        text: display
                        anchors.fill: parent
                        anchors.margins: 5
                        verticalAlignment: Text.AlignVCenter
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }

    Button {
        id: addQuestionBtn
        x: 520
        y: 118
        width: 180
        height: 30
        text: qsTr("+ Adicionar Pergunta")

        background: Rectangle {
            color: parent.down ? "#243342" : (parent.hovered ? "#374d63" : "#2c3e50")
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
            font.bold: true
        }
    }

    ListView {
        id: questionsList
        x: 520
        y: 163
        width: 460
        height: Constants.height - 163 - 90
        clip: true
        spacing: 15

        model: ListModel {
            id: questionsModel
            ListElement {
                questionText: ""
                options: [
                    ListElement {
                        optionText: ""
                    },
                    ListElement {
                        optionText: ""
                    }
                ]
            }
        }

        delegate: Rectangle {
            id: questionDelegate
            property int questionIndex: index
            width: ListView.view.width
            height: 140 + (options.count * 40)
            color: "#f8f8f8"
            border.color: "#999999"
            border.width: 1
            radius: 6
            Rectangle {
                z: -1
                width: parent.width
                height: parent.height
                y: 2
                color: "#1a000000"
                radius: 6
            }

            Text {
                x: 15
                y: 15
                text: qsTr("Título da Pergunta:")
                font.pixelSize: 12
                font.weight: Font.Medium
            }

            Button {
                id: moveUpBtn
                x: parent.width - 65
                y: 10
                width: 22
                height: 22
                text: "▲"
                enabled: index > 0
                opacity: enabled ? 1.0 : 0.3
                background: Rectangle {
                    color: parent.down ? "#d0d0d0" : (parent.hovered ? "#e0e0e0" : "#ffffff")
                    border.color: "#cccccc"
                    radius: 4
                }
                contentItem: Text {
                    text: parent.text
                    color: "#333333"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 10
                }
                Connections {


                    function onClicked() {
                        root.moveQuestionUpClicked(index)
                    }
                }
            }

            Button {
                id: moveDownBtn
                x: parent.width - 35
                y: 10
                width: 22
                height: 22
                text: "▼"
                enabled: index < questionsModel.count - 1
                opacity: enabled ? 1.0 : 0.3
                background: Rectangle {
                    color: parent.down ? "#d0d0d0" : (parent.hovered ? "#e0e0e0" : "#ffffff")
                    border.color: "#cccccc"
                    radius: 4
                }
                contentItem: Text {
                    text: parent.text
                    color: "#333333"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.pixelSize: 10
                }
                Connections {


                    function onClicked() {
                        root.moveQuestionDownClicked(index)
                    }
                }
            }

            Rectangle {
                x: 15
                y: 35
                width: parent.width - 30
                height: 30
                color: "#ffffff"
                border.color: "#a0a0a0"
                border.width: 1
                radius: 4

                TextField {
                    id: questionTextInput
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    placeholderText: qsTr("Digite a pergunta...")
                    text: questionText
                    color: "#333333"
                    font.pixelSize: 12
                    verticalAlignment: Text.AlignVCenter
                    clip: true
                    background: Item {}
                    Connections {


                        function onTextEdited() {
                            root.questionTextEdited(index, questionTextInput.text)
                        }
                    }
                }
            }

            Text {
                x: 15
                y: 75
                text: qsTr("Opções:")
                font.pixelSize: 12
                font.weight: Font.Medium
            }

            Column {
                x: 15
                y: 95
                width: parent.width - 30
                spacing: 8

                Repeater {
                    model: options
                    delegate: Rectangle {
                        width: parent.width
                        height: 30
                        color: "#ffffff"
                        border.color: "#a0a0a0"
                        border.width: 1
                        radius: 4

                        TextField {
                            id: optionTextInput
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            placeholderText: qsTr("Opção...")
                            text: optionText
                            color: "#333333"
                            font.pixelSize: 12
                            verticalAlignment: Text.AlignVCenter
                            clip: true
                            background: Item {}
                            Connections {


                                function onTextEdited() {
                                    root.optionTextEdited(questionDelegate.questionIndex, index, optionTextInput.text)
                                }
                            }
                        }
                    }
                }

                Button {
                    text: qsTr("+ Adicionar Opção")
                    width: 140
                    height: 28

                    background: Rectangle {
                        color: parent.down ? "#3d3d3d" : (parent.hovered ? "#5c5c5c" : "#4a4a4a")
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
                        font.pixelSize: 11
                    }

                    Connections {


                        function onClicked() {
                            root.addOptionClicked(index)
                        }
                    }
                }
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: "Selecione um arquivo CSV"
        nameFilters: ["Arquivos CSV (*.csv)", "Todos os arquivos (*)"]
    }

    FileDialog {
        id: saveFileDialog
        title: "Salvar Modelo CSV"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Arquivos CSV (*.csv)"]
        defaultSuffix: "csv"
    }

    Button {
        id: createElectionBtn
        x: Constants.width - width - 45
        y: Constants.height - height - 30
        width: 160
        height: 40
        text: qsTr("Criar Eleição")
        enabled: textInput.text !== "" && isValidCsv && hasValidQuestion
        opacity: enabled ? 1.0 : 0.5

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
    }
}
