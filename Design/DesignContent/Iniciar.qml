import QtQuick
import QtQuick.Controls

IniciarForm {
    id: form
    
    property var availableElections: []
    
    Component.onCompleted: {
        isLoading = true
        startElectionController.fetchAvailableElections()
    }
    
    Connections {
        target: startElectionController
        function onFetchAvailableFinished(resStr) {
            isLoading = false
            console.log("[Iniciar.qml] onFetchAvailableFinished retorno:", resStr)
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
                        statusMessage = "Nenhuma eleição disponível para iniciar."
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
                    console.error("Erro ao buscar: " + msg)
                }
            } catch (e) {
                statusIsError = true
                statusMessage = "Erro ao carregar dados das eleições."
                console.error("Erro no JSON de busca: " + e)
            }
        }
        
        function onStartElectionFinished(resStr) {
            isLoading = false
            console.log("Resultado Iniciar:", resStr)
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    statusIsError = false
                    statusMessage = "Eleição iniciada com sucesso!"
                    isElectionStarted = true
                    console.log("Eleição iniciada! Hora registrada:", res.dados ? res.dados.hora_registrada : "")
                } else {
                    statusIsError = true
                    isElectionStarted = false
                    var msg = res.mensagem || "Erro ao iniciar eleição."
                    if (typeof msg === 'object') {
                        var parts = []
                        for (var k in msg) {
                            parts.push(k + ": " + (Array.isArray(msg[k]) ? msg[k].join("; ") : msg[k]))
                        }
                        msg = parts.join(" | ")
                    }
                    statusMessage = msg
                    console.error("Erro ao iniciar:", msg)
                }
            } catch(e) {
                statusIsError = true
                isElectionStarted = false
                statusMessage = resStr
                console.error("Erro no JSON start:", e)
            }
        }
    }
    
    startElectionBtn.onClicked: {
        var idx = electionComboBox.currentIndex
        if (idx >= 0 && idx < availableElections.length) {
            var selectedHandle = availableElections[idx].keyHandle
            console.log("Iniciando a eleição: " + electionComboBox.currentText)
            statusMessage = ""
            isLoading = true
            startElectionController.startElection(selectedHandle)
        } else {
            statusIsError = true
            statusMessage = "Selecione uma eleição para iniciar."
            console.error("Nenhuma eleição selecionada.")
        }
    }
}
