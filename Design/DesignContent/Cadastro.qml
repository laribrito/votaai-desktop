import QtQuick
import QtQuick.Controls

CadastroForm {
    id: form

    signal cadastroConcluido
    signal irParaMainClicked

    Component.onCompleted: {
        isAlreadyRegistered = authController.isRegistered
        registeredEmailText = authController.registeredEmail
        if (institutionalDomain && institutionalDomain.trim() !== "") {
            emailInput.text = "admin" + institutionalDomain
        }
    }

    Connections {
        target: authController
        function onRegistrationStatusChanged() {
            isAlreadyRegistered = authController.isRegistered
            registeredEmailText = authController.registeredEmail
        }
    }

    // Ação: Submeter Etapa 1 (Criar Chave e Iniciar Cadastro)
    onSubmitPreCadastroClicked: {
        errorMessage = ""
        var email = emailInput.text.trim()
        var senha = passwordInput.text
        var confSenha = confirmPasswordInput.text

        if (!email) {
            errorMessage = "Por favor, informe o e-mail do administrador."
            return
        }

        if (!senha) {
            errorMessage = "Por favor, informe a senha."
            return
        }

        if (senha.length < 8) {
            errorMessage = "A senha deve conter no mínimo 8 caracteres."
            return
        }

        if (senha !== confSenha) {
            errorMessage = "As senhas não coincidem. Verifique a confirmação."
            return
        }

        isLoading = true

        var resStr = authController.iniciarPreCadastro(email, senha)
        isLoading = false

        try {
            var res = JSON.parse(resStr)
            if (res.status === "sucesso") {
                qrCodeSource = res.qr_base64 ? res.qr_base64 : ("file:///" + res.qr_path)
                secretKeyText = res.secret || ""
                currentStep = 2
                errorMessage = ""
            } else {
                errorMessage = res.mensagem || "Erro ao iniciar pré-cadastro."
            }
        } catch (e) {
            errorMessage = "Erro ao processar resposta: " + e
        }
    }

    // Ação: Submeter Etapa 2 (Confirmar Código TOTP)
    onSubmitTotpClicked: {
        errorMessage = ""
        var email = emailInput.text.trim()
        var totp = totpInput.text.trim()

        if (!totp || totp.length !== 6) {
            errorMessage = "Por favor, digite o código de 6 dígitos gerado pelo aplicativo autenticador."
            return
        }

        isLoading = true

        var resStr = authController.confirmarPreCadastro(email, totp)
        isLoading = false

        try {
            var res = JSON.parse(resStr)
            if (res.status === "sucesso") {
                currentStep = 3
                errorMessage = ""
                form.cadastroConcluido()
            } else {
                errorMessage = res.mensagem || "Código TOTP inválido ou falha de autenticação."
            }
        } catch (e) {
            errorMessage = "Erro ao processar resposta: " + e
        }
    }

    // Ação: Copiar chave manual
    onCopySecretClicked: {
        if (secretKeyText) {
            authController.copyToClipboard(secretKeyText)
            errorMessage = "Chave copiada para a área de transferência!"
        }
    }

    // Ação: Voltar para Etapa 1
    onBackToStep1Clicked: {
        errorMessage = ""
        currentStep = 1
    }

    // Ação: Acessar painel após conclusão
    onAccessMainClicked: {
        form.irParaMainClicked()
    }

    // Ação: Acesso direto caso já cadastrado
    onDirectAccessClicked: {
        form.irParaMainClicked()
    }
}
