import QtQuick
import QtQuick.Controls

CadastroForm {
    id: form

    signal cadastroConcluido
    signal irParaMainClicked

    onTogglePasswordVisibilityClicked: {
        isPasswordVisible = !isPasswordVisible
    }

    onToggleConfirmPasswordVisibilityClicked: {
        isConfirmPasswordVisible = !isConfirmPasswordVisible
    }

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

        function onPreRegistrationFinished(resStr) {
            isLoading = false
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    errorMessage = ""
                    if (res.requires_email_verification) {
                        emailCodeInput.text = ""
                        infoMessage = res.mensagem || "Código de verificação enviado para o seu e-mail."
                        currentStep = 2
                    } else {
                        infoMessage = ""
                        qrCodeSource = res.qr_base64 ? res.qr_base64 : ("file:///" + res.qr_path)
                        secretKeyText = res.secret || ""
                        currentStep = 3
                    }
                } else {
                    infoMessage = ""
                    errorMessage = res.mensagem || "Erro ao iniciar pré-cadastro."
                }
            } catch (e) {
                infoMessage = ""
                errorMessage = "Erro ao processar resposta: " + e
            }
        }

        function onVerificarEmailFinished(resStr) {
            isLoading = false
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    qrCodeSource = res.qr_base64 ? res.qr_base64 : ("file:///" + res.qr_path)
                    secretKeyText = res.secret || ""
                    infoMessage = ""
                    errorMessage = ""
                    currentStep = 3
                } else {
                    infoMessage = ""
                    errorMessage = res.mensagem || "Código de verificação inválido ou expirado."
                }
            } catch (e) {
                infoMessage = ""
                errorMessage = "Erro ao processar resposta: " + e
            }
        }

        function onReenviarEmailFinished(resStr) {
            isLoading = false
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    errorMessage = ""
                    infoMessage = res.mensagem || "Um novo código de verificação foi enviado para o seu e-mail."
                } else {
                    infoMessage = ""
                    errorMessage = res.mensagem || "Não foi possível reenviar o código."
                }
            } catch (e) {
                infoMessage = ""
                errorMessage = "Erro ao processar resposta: " + e
            }
        }

        function onConfirmarPreCadastroFinished(resStr) {
            isLoading = false
            try {
                var res = JSON.parse(resStr)
                if (res.status === "sucesso") {
                    currentStep = 4
                    infoMessage = ""
                    errorMessage = ""
                    form.cadastroConcluido()
                } else {
                    infoMessage = ""
                    errorMessage = res.mensagem || "Código TOTP inválido ou falha de autenticação."
                }
            } catch (e) {
                infoMessage = ""
                errorMessage = "Erro ao processar resposta: " + e
            }
        }
    }

    // Ação: Submeter Etapa 1 (Criar Chave e Iniciar Cadastro)
    onSubmitPreCadastroClicked: {
        errorMessage = ""
        if (isAlreadyRegistered) {
            errorMessage = "Esta máquina já possui um administrador vinculado (" + registeredEmailText + ")."
            return
        }
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
        authController.iniciarPreCadastro(email, senha)
    }

    // Ação: Submeter Etapa 2 (Verificar Código de E-mail)
    onSubmitEmailCodeClicked: {
        errorMessage = ""
        infoMessage = ""
        var email = emailInput.text.trim()
        var codigo = emailCodeInput.text.trim()

        if (!codigo || codigo.length !== 6) {
            errorMessage = "Por favor, digite o código de 6 dígitos enviado para o seu e-mail."
            return
        }

        isLoading = true
        authController.verificarEmailPreCadastro(email, codigo)
    }

    // Ação: Reenviar Código de Verificação por E-mail
    onResendEmailCodeClicked: {
        errorMessage = ""
        infoMessage = ""
        var email = emailInput.text.trim()
        if (!email) {
            errorMessage = "E-mail não informado."
            return
        }

        isLoading = true
        authController.reenviarEmailPreCadastro(email)
    }

    // Ação: Submeter Etapa 3 (Confirmar Código TOTP)
    onSubmitTotpClicked: {
        errorMessage = ""
        infoMessage = ""
        var email = emailInput.text.trim()
        var totp = totpInput.text.trim()
        var senha = passwordInput.text

        if (!totp || totp.length !== 6) {
            errorMessage = "Por favor, digite o código de 6 dígitos gerado pelo aplicativo autenticador."
            return
        }

        isLoading = true
        authController.confirmarPreCadastro(email, totp, senha)
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
        infoMessage = ""
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
