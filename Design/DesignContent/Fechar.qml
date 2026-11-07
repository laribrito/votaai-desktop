import QtQuick
import QtQuick.Controls

FecharForm {
    id: form
    
    property var availableElections: []
    
    Component.onCompleted: {
        isLoading = true
        closeElectionController.fetchAvailableElections()
    }
    
    Connections {
        target: closeElectionController
        function onFetchAvailableFinished(resStr) {
            isLoading = false
            console.log("[Fechar.qml] onFetchAvailableFinished retorno:", resStr)
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    availableElections = res.elections || []
                    var titles = []
                    for (var i = 0; i < availableElections.length; i++) {
                        titles.push(availableElections[i].titulo)
                    }
                    electionComboBox.model = titles
                    if (availableElections.length === 0) {
                        statusIsError = false
                        statusMessage = "Nenhuma eleição aberta disponível para fechar."
                    }
                } else {
                    availableElections = []
                    electionComboBox.model = []
                    var msg = res.mensagem || "Erro ao buscar eleições."
                    if (typeof msg === 'object') {
                        var parts = []
                        for (var k in msg) {
                            parts.push(k + ": " + (Array.isArray(msg[k]) ? msg[k].join("; ") : msg[k]))
                        }
                        msg = parts.join(" | ")
                    }
                    statusIsError = true
                    statusMessage = msg
                    console.error("Erro ao buscar eleições para fechar: " + msg)
                }
            } catch (e) {
                statusIsError = true
                statusMessage = "Erro ao carregar dados das eleições."
                console.error("Erro no JSON de busca: " + e)
            }
        }
        
        function onCloseElectionFinished(resStr) {
            isLoading = false
            console.log("[Fechar.qml] Resultado Fechar:", resStr)
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    statusIsError = false
                    var quorum = res.dados && res.dados.porcentagem_quorum !== undefined ? res.dados.porcentagem_quorum + "%" : ""
                    statusMessage = "Eleição fechada com sucesso! Quórum travado em " + quorum
                    isElectionClosed = true
                    console.log("Eleição fechada! Hora registrada:", res.dados ? res.dados.hora_registrada : "")
                } else {
                    statusIsError = true
                    isElectionClosed = false
                    var msg = res.mensagem || "Erro ao fechar eleição."
                    if (typeof msg === 'object') {
                        var parts = []
                        for (var k in msg) {
                            parts.push(k + ": " + (Array.isArray(msg[k]) ? msg[k].join("; ") : msg[k]))
                        }
                        msg = parts.join(" | ")
                    }
                    statusMessage = msg
                    console.error("Erro ao fechar eleição:", msg)
                }
            } catch(e) {
                statusIsError = true
                isElectionClosed = false
                statusMessage = resStr
                console.error("Erro no JSON close:", e)
            }
        }
    }
    
    actionBtn.onClicked: {
        var idx = electionComboBox.currentIndex
        if (idx >= 0 && idx < availableElections.length) {
            var selectedHandle = availableElections[idx].keyHandle
            console.log("Fechando a eleição: " + electionComboBox.currentText)
            statusMessage = ""
            isLoading = true
            closeElectionController.closeElection(selectedHandle)
        } else {
            statusIsError = true
            statusMessage = "Selecione uma eleição para fechar."
            console.error("Nenhuma eleição selecionada.")
        }
    }
}
