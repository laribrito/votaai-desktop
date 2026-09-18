import QtQuick
import QtQuick.Controls

AutenticacaoForm {
    id: form

    signal loginSucesso

    Component.onCompleted: {
        if (typeof authController !== 'undefined' && authController) {
            registeredEmailText = authController.registeredEmailMasked
            registeredNameText = authController.registeredUserName
        }
    }

    Connections {
        target: (typeof authController !== 'undefined' && authController) ? authController : null
        function onRegistrationStatusChanged() {
            if (authController) {
                registeredEmailText = authController.registeredEmailMasked
                registeredNameText = authController.registeredUserName
            }
        }
    }

    onTogglePasswordVisibilityClicked: {
        isPasswordVisible = !isPasswordVisible
    }

    Connections {
        target: form.passwordInput
        function onAccepted() {
            form.totpInput.forceActiveFocus()
        }
    }

    Connections {
        target: form.totpInput
        function onAccepted() {
            form.submitLoginClicked()
        }
    }

    onSubmitLoginClicked: {
        errorMessage = ""
        var senha = passwordInput.text
        var totp = totpInput.text.trim()

        if (!senha) {
            errorMessage = qsTr("Por favor, informe sua senha de administrador.")
            passwordInput.forceActiveFocus()
            return
        }

        if (!totp) {
            errorMessage = qsTr("Por favor, digite o código de 6 dígitos gerado pelo autenticador (TOTP).")
            totpInput.forceActiveFocus()
            return
        }

        if (totp.length !== 6 || !/^\d+$/.test(totp)) {
            errorMessage = qsTr("O código TOTP deve conter exatamente 6 dígitos numéricos.")
            totpInput.forceActiveFocus()
            return
        }

        isLoading = true

        var resStr = authController.login(senha, totp)
        isLoading = false

        try {
            var res = JSON.parse(resStr)
            if (res.status === "sucesso") {
                errorMessage = ""
                form.loginSucesso()
            } else {
                errorMessage = res.mensagem || qsTr("Falha na autenticação.")
            }
        } catch (e) {
            errorMessage = qsTr("Erro ao processar resposta do servidor: ") + e
        }
    }
}
