import QtQuick
import QtQuick.Controls

ApurarForm {
    id: form
    
    actionBtn.onClicked: {
        console.log("Apurando a eleição: " + electionComboBox.currentText)
        // Aqui podemos integrar a chamada ao backend
        // backend.tallyElection(electionComboBox.currentText)
    }
}
