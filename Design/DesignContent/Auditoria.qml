import QtQuick
import QtQuick.Controls

AuditoriaForm {
    id: form

    property string selectedZipPath: ""

    Connections {
        target: (typeof tallyElectionController !== 'undefined' && tallyElectionController) ? tallyElectionController : null

        function onAuditFinished(resStr) {
            isLoading = false
            console.log("[Auditoria.qml] onAuditFinished:", resStr)
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    statusIsError = false
                    isAuditCompleted = true
                    isAuditValid = res.is_valid

                    var title = res.titulo || "Eleição"
                    var details = "ELEIÇÃO: " + title + " (Handle: " + (res.keyHandle || "N/A") + ")\n"
                    if (res.machine_fingerprint) {
                        details += "MÁQUINA APURADORA (Fingerprint): " + res.machine_fingerprint + "\n"
                    }
                    details += "STATUS DA AUDITORIA: " + (res.is_valid ? "Íntegro / Válido (100% autêntico)" : "DIVERGÊNCIA DETECTADA!") + "\n\n"

                    details += "--- CONFERÊNCIA CRIPTOGRÁFICA DE HASH ---\n"
                    details += "Hash Calculado (SHA-256):\n" + (res.calculated_hash || "N/A") + "\n"
                    details += "Hash Declarado na Ata Oficial (SHA-256):\n" + (res.expected_hash || "N/A") + "\n"
                    details += "Resultado da Comparação: " + (res.is_valid ? "CONFERE" : "NÃO CONFERE") + "\n\n"

                    details += "--- INFORMAÇÕES DO PLEITO ---\n"
                    details += "Total de Cédulas Cifradas Auditadas: " + (res.total_votos !== undefined ? res.total_votos : 0) + "\n"
                    var totalVoters = res.total_voters !== undefined ? res.total_voters : 0
                    var abstCount = res.abstention_count !== undefined ? res.abstention_count : 0
                    var abstPct = res.abstention_percentage !== undefined ? res.abstention_percentage : 0.0
                    details += "Colegiado Eleitoral Total: " + totalVoters + " eleitor(es)\n"
                    details += "Abstenção: " + (typeof abstPct === 'number' ? abstPct.toFixed(1) : abstPct) + "% (" + abstCount + " ausente(s))\n\n"

                    details += "--- CONTAGEM INDEPENDENTE DE VOTOS ---\n"
                    var resObj = res.results || {}
                    if (resObj.questions && Array.isArray(resObj.questions) && resObj.questions.length > 0) {
                        for (var i = 0; i < resObj.questions.length; i++) {
                            var qItem = resObj.questions[i]
                            details += "• " + qItem.question + ":\n"
                            var optsList = qItem.options || []
                            for (var j = 0; j < optsList.length; j++) {
                                var optItem = optsList[j]
                                var pctStr = (optItem.percentage !== undefined) ? (" (" + optItem.percentage.toFixed(1) + "%)") : ""
                                details += "   - " + optItem.label + ": " + optItem.votes + " voto(s)" + pctStr + "\n"
                            }
                            details += "\n"
                        }
                    } else {
                        var summary = resObj.summary || resObj
                        for (var q in summary) {
                            if (q === "questions" || q === "total_votos" || q === "total_voters" || q === "abstention_count" || q === "abstention_percentage") continue
                            details += "• " + q + ":\n"
                            var opts = summary[q]
                            for (var opt in opts) {
                                details += "   - " + opt + ": " + opts[opt] + " voto(s)\n"
                            }
                            details += "\n"
                        }
                    }

                    auditDetailsText = details
                    statusMessage = res.is_valid
                        ? qsTr("Auditoria concluída com sucesso! Hash oficial validado.")
                        : qsTr("Atenção: O hash calculado não confere com o da ata oficial.")
                } else {
                    statusIsError = true
                    isAuditCompleted = false
                    var msg = res.mensagem || qsTr("Falha ao processar auditoria do pacote.")
                    statusMessage = msg
                    console.error("Erro na auditoria:", msg)
                }
            } catch (e) {
                statusIsError = true
                isAuditCompleted = false
                statusMessage = qsTr("Erro ao processar dados de retorno da auditoria: ") + e
                console.error("Erro no JSON da auditoria:", e)
            }
        }
    }

    onBrowseClicked: {
        fileDialog.open()
    }

    fileDialog.onAccepted: {
        var path = fileDialog.selectedFile.toString()
        path = path.replace(/^(file:\/{2})/, "")
        if (Qt.platform.os === "windows") {
            path = path.replace(/^\/([a-zA-Z]:)/, "$1")
        }
        path = decodeURIComponent(path)

        selectedZipPath = path
        zipPathDisplay.text = path
        hasSelectedFile = (path.trim() !== "")
        statusMessage = ""
        isAuditCompleted = false
        auditDetailsText = ""
    }

    onAuditClicked: {
        if (!selectedZipPath || selectedZipPath.trim() === "") {
            statusIsError = true
            statusMessage = qsTr("Por favor, selecione um arquivo ZIP para auditar.")
            return
        }

        statusMessage = ""
        isLoading = true
        tallyElectionController.auditZip(selectedZipPath)
    }

    onNewAuditClicked: {
        selectedZipPath = ""
        zipPathDisplay.text = ""
        hasSelectedFile = false
        isAuditCompleted = false
        isAuditValid = false
        auditDetailsText = ""
        statusMessage = ""
    }
}
