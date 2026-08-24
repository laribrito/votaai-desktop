import QtQuick
import QtQuick.Controls

IniciarForm {
    id: form
    
    startElectionBtn.onClicked: {
        console.log("Iniciando a eleição: " + electionComboBox.currentText)
        // Aqui podemos integrar a chamada ao backend
        // backend.startElection(electionComboBox.currentText)
    }
}
