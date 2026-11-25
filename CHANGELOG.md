## v0.9.0 (2026-11-25)

### Feat

- **security**: add native CFF bytecode and frozen bundle protection
- **security**: include pinned server initial_key.json in integrity manifest verification
- **crypto**: apply ISO/IEC 7816-4 fixed-size padding to desktop API envelopes
- **crypto**: unpad ISO/IEC 7816-4 ballots across tally controller and native backends
- **security**: implement runtime anti-root, anti-debug and anti-tamper guard
- **http**: send Accept-Language header in API requests
- **ui**: add email verification step to admin registration screen
- **auth**: handle email verification and resend in AuthController
- **routes**: register admin email verification and resend endpoints
- **audit**: display machine_fingerprint and election key_handle in audit screen
- **crypto**: generate unique key_handle per election across native backends
- **ui**: add Auditoria screen and public audit entry points in App, Login, and Cadastro views
- **audit**: implement sovereign audit ZIP verification, PEM vote decryption, and core tallying
- **ui**: render abstention metrics and question breakdown with percentages in Apurar
- **election**: add metadata mapping, abstention metrics, and structured tally results
- **election**: implement sovereign tallying, private key export, and UI in Apurar
- **crypto**: manage election private key outside TEE for sovereign tallying
- **ui**: integrate election closing flow, status feedback, and quorum display in Fechar views
- **election**: implement CloseElectionController with TPM signing and anti-replay protection
- **api**: add election close route definition
- **ui**: add responsive single-column layout for compact displays
- **window**: add window size limits and vertical scroll support

### Fix

- **security**: enforce security guard in frozen builds and detect cross-thread python tracers
- **security**: require valid encrypted envelopes on HTTP 2xx desktop responses
- **auth**: attach Knox Authorization token to protected desktop API requests

### Refactor

- troca mensagem do mecanismo de auditoria
- **crypto**: refine election key metadata note in tpm_linux

## v0.8.0 (2026-10-11)

### Feat

- **election**: implement StartElectionController and integrate start election flow in QML
- **api**: add election start and availability routes with enhanced HTTP logging
- **crypto**: add TPM 2.0 decryption, dynamic handles, and hardware RNG
- **api**: centralize API routes configuration

### Fix

- **election**: include machine public key in start election requests
- **election**: include machine public key in election creation request
- **election**: add label field to ballot options for backend schema compatibility
- **auth**: include machine public key in authentication request
- **crypto**: refine public key injection in payload signing
- **crypto**: improve TPM tool compatibility and payload signing structure

### Refactor

- **api**: centralize endpoints in json and remove duplicated route definitions
- **crypto**: log origin of random number generation across platforms
- **election**: align election start and create payloads with backend contract
- **auth**: enforce strict device_id and remove duplicate key fields
- **crypto**: always inject machine_public_key and remove client_public_key duplicate
- **election**: extract election creation from csvController into ElectionController
- **auth, csv**: enforce envelope signature for payloads and snake_case in election creation

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
