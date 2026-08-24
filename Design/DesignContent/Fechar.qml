import QtQuick
import QtQuick.Controls

FecharForm {
    id: form
    
    actionBtn.onClicked: {
        console.log("Fechando a eleição: " + electionComboBox.currentText)
        // Aqui podemos integrar a chamada ao backend
        // backend.closeElection(electionComboBox.currentText)
    }
}
