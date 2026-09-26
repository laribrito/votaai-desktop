## v0.7.0 (2026-09-26)

### Feat

- add comments command to run_commands.py
- **ui**: add loading feedback and post-creation navigation in election screen
- **election**: integrate election creation endpoint with hardware signature and dual fields
- **auth**: implement asynchronous authentication and api timeout handling
- **crypto**: add linux and mac secure hardware tpm support
- **ui**: mascarar e-mail do usuario na tela de autenticacao
- **auth**: reutilizar chave tpm e refinar tratamento de erros no login
- **ui**: adicionar tela de autenticacao 2FA com estetica padrao do sistema
- **auth**: implementar metodo de login com autenticacao em dois fatores (2FA) e assinatura TPM
- **ui**: exibir responsavel da maquina com controle de visualizacao de email
- **auth**: expor propriedades do administrador e identificador da maquina
- **auth**: bloquear pre-cadastro quando maquina ja possui administrador vinculado
- primeiro commit

### Fix

- **script**: conditionalize automated tests for desktop project
- **script**: enable shell execution on posix systems in run_commands.py
- **ui**: increase column spacing in step 2 to prevent title overlap
- **http**: preservar estrutura de dados em respostas de erro da api

### Refactor

- reorganize api services, extract controllers and translate auth variables
- remove unused auth_service.py mock

## v0.6.0 (2026-09-04)

### Feat

- **api**: adicionar descriptografia automatica de respostas no http client
- **crypto**: integrar gerenciamento de chaves tpm do cliente e envio da chave publica
- **crypto**: implementar operacoes de hardware cng em c nativo
- atualiza a forma de retirar o erro
- **ui**: adicionar botao de teste de conexao hibrida na tela inicial
- **api**: integrar criptografia hibrida no cliente http
- **crypto**: implementar servico de criptografia hibrida AES-GCM e RSA
- **crypto**: adicionar chave publica inicial compilada
- **api**: implement device authentication and request signing
- **ui**: add election control pages and update navigation

### Fix

- corrige a execução para sistemas windows

### Refactor

- **ui**: implement Form-Logic pattern for Criacao screen

## v0.5.0 (2026-08-23)

### Feat

- integrate hardware payload and add duplicate email validation
- add multi-platform hardware crypto and external API service
