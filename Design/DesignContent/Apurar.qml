import QtQuick
import QtQuick.Controls

ApurarForm {
    id: form

    property var availableElections: []

    Component.onCompleted: {
        isLoading = true
        tallyElectionController.fetchClosedElections()
    }

    Connections {
        target: tallyElectionController

        function onFetchAvailableFinished(resStr) {
            isLoading = false
            console.log("[Apurar.qml] onFetchAvailableFinished retorno:", resStr)
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
                        statusMessage = "Nenhuma eleição fechada disponível para apuração."
                    }
                } else {
                    availableElections = []
                    electionComboBox.model = []
                    var msg = res.mensagem || "Erro ao buscar eleições fechadas."
                    if (typeof msg === 'object') {
                        var parts = []
                        for (var k in msg) {
                            parts.push(k + ": " + (Array.isArray(msg[k]) ? msg[k].join("; ") : msg[k]))
                        }
                        msg = parts.join(" | ")
                    }
                    statusIsError = true
                    statusMessage = msg
                    console.error("Erro ao buscar eleições para apurar: " + msg)
                }
            } catch (e) {
                statusIsError = true
                statusMessage = "Erro ao carregar dados das eleições."
                console.error("Erro no JSON de busca: " + e)
            }
        }

        function onTallyElectionFinished(resStr) {
            isLoading = false
            console.log("[Apurar.qml] Resultado Apuração:", resStr)
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    statusIsError = false
                    isElectionTallied = true
                    statusMessage = "Apuração soberana concluída e chave privada publicada!"

                    var details = "Total de cédulas apuradas: " + (res.total_votos !== undefined ? res.total_votos : 0) + "\n"
                    details += "Audit Hash (SHA-256): " + (res.tally_hash || "N/A") + "\n\n"
                    details += "--- CONTAGEM DE VOTOS POR QUESTÃO ---\n"

                    var results = res.results || {}
                    for (var q in results) {
                        details += "• " + q + ":\n"
                        var opts = results[q]
                        for (var opt in opts) {
                            details += "   - " + opt + ": " + opts[opt] + " voto(s)\n"
                        }
                    }

                    tallyDetailsText = details
                } else {
                    statusIsError = true
                    isElectionTallied = false
                    var msg = res.mensagem || "Erro ao apurar eleição."
                    if (typeof msg === 'object') {
                        var parts = []
                        for (var k in msg) {
                            parts.push(k + ": " + (Array.isArray(msg[k]) ? msg[k].join("; ") : msg[k]))
                        }
                        msg = parts.join(" | ")
                    }
                    statusMessage = msg
                    console.error("Erro ao apurar eleição:", msg)
                }
            } catch (e) {
                statusIsError = true
                isElectionTallied = false
                statusMessage = resStr
                console.error("Erro no JSON tally:", e)
            }
        }
    }

    actionBtn.onClicked: {
        var idx = electionComboBox.currentIndex
        if (idx >= 0 && idx < availableElections.length) {
            var selectedHandle = availableElections[idx].keyHandle
            console.log("Apurando a eleição: " + electionComboBox.currentText + " (handle: " + selectedHandle + ")")
            statusMessage = ""
            isLoading = true
            tallyElectionController.tallyElection(selectedHandle)
        } else {
            statusIsError = true
            statusMessage = "Selecione uma eleição para apurar."
            console.error("Nenhuma eleição selecionada.")
        }
    }
}
