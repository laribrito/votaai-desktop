import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

CriacaoForm {
    id: form
    
    Component.onCompleted: {
        tableView.columnWidthProvider = function (column) {
            return tableView.width / 2 - 2;
        }
    }
    
    function validateQuestions() {
        for (var i = 0; i < questionsModel.count; i++) {
            var question = questionsModel.get(i);
            if (question.questionText.trim() !== "") {
                for (var j = 0; j < question.options.count; j++) {
                    if (question.options.get(j).optionText.trim() !== "") {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    // Connect exposed buttons
    browseButton.onClicked: fileDialog.open()
    downloadTemplateBtn.onClicked: saveFileDialog.open()
    
    addQuestionBtn.onClicked: {
        questionsModel.append({
            "questionText": "",
            "options": [
                {"optionText": ""}
            ]
        })
        hasValidQuestion = validateQuestions()
    }
    
    searchInput.onTextEdited: {
        backend.search(searchInput.text)
    }

    createElectionBtn.onClicked: {
        statusMessage = ""
        isLoading = true
        var ballot = []
        for (var i = 0; i < questionsModel.count; i++) {
            var q = questionsModel.get(i)
            var options = []
            for (var j = 0; j < q.options.count; j++) {
                var optText = q.options.get(j).optionText.trim()
                if (optText !== "") {
                    options.push(optText)
                }
            }
            if (q.questionText.trim() !== "") {
                ballot.push({
                    "question": q.questionText.trim(),
                    "options": options
                })
            }
        }
        electionController.createElection(textInput.text, JSON.stringify(ballot))
    }

    Connections {
        target: electionController
        function onCreateElectionFinished(resStr) {
            isLoading = false
            console.log("Resultado da criação da eleição:", resStr)
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    statusIsError = false
                    statusMessage = "Eleição criada com sucesso!"
                    isElectionCreated = true
                } else {
                    statusIsError = true
                    isElectionCreated = false
                    var msg = res.mensagem || "Erro ao criar eleição."
                    if (typeof msg === 'object') {
                        var parts = []
                        for (var k in msg) {
                            parts.push(k + ": " + (Array.isArray(msg[k]) ? msg[k].join("; ") : msg[k]))
                        }
                        msg = parts.join(" | ")
                    }
                    statusMessage = msg
                }
            } catch (e) {
                statusIsError = true
                isElectionCreated = false
                statusMessage = resStr
            }
        }
    }


    // Connect FileDialogs
    fileDialog.onAccepted: {
        var path = fileDialog.selectedFile.toString();
        path = path.replace(/^(file:\/{2})/, "");
        if (Qt.platform.os === "windows") {
            path = path.replace(/^\/([a-zA-Z]:)/, "$1");
        }
        path = decodeURIComponent(path);
        
        var err = backend.validateCsv(path);
        if (err === "") {
            csvInput.text = path;
            isValidCsv = true;
            csvErrorMessage = "";
        } else {
            csvInput.text = "Arquivo selecionado é inválido!";
            isValidCsv = false;
            csvErrorMessage = err;
        }
    }

    saveFileDialog.onAccepted: {
        var path = saveFileDialog.selectedFile.toString();
        path = path.replace(/^(file:\/{2})/, "");
        if (Qt.platform.os === "windows") {
            path = path.replace(/^\/([a-zA-Z]:)/, "$1");
        }
        path = decodeURIComponent(path);
        backend.saveTemplate(path);
    }

    // Connect Delegate Signals
    onMoveQuestionUpClicked: function(index) {
        if (index > 0) {
            questionsModel.move(index, index - 1, 1)
        }
    }
    
    onMoveQuestionDownClicked: function(index) {
        if (index < questionsModel.count - 1) {
            questionsModel.move(index, index + 1, 1)
        }
    }
    
    onQuestionTextEdited: function(index, text) {
        questionsModel.get(index).questionText = text
        hasValidQuestion = validateQuestions()
    }
    
    onAddOptionClicked: function(index) {
        questionsModel.get(index).options.append({"optionText": "Nova Opção"})
        hasValidQuestion = validateQuestions()
    }
    
    onOptionTextEdited: function(questionIndex, optionIndex, text) {
        questionsModel.get(questionIndex).options.get(optionIndex).optionText = text
        hasValidQuestion = validateQuestions()
    }
}
