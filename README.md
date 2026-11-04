# VotaAí - Desktop Application

Aplicativo desktop do sistema de votação digital seguro **VotaAí**, desenvolvido em **Python 3.12+**, **PySide6 (Qt Quick / QML)** e integração com criptografia em hardware (**TPM 2.0 / CNG / Secure Storage**).

---

## 🚀 Requisitos e Configuração

### 1. Criar e Ativar o Ambiente Virtual
```bash
python -m venv .venv
source .venv/bin/activate  # No Linux / macOS
# .venv\Scripts\activate   # No Windows
```

### 2. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 3. Variáveis de Ambiente (`.env`)
Crie um arquivo `.env` na raiz do projeto com base no [`.env.example`](.env.example):
```ini
INSTITUTIONAL_DOMAIN=@uesc.br
API_BASE_URL=http://127.0.0.1:8000
```

---

## 🔑 Configuração Obrigatória da Chave Inicial do Servidor (`initial_key.json`)

Para que o aplicativo Desktop consiga estabelecer a comunicação inicial criptografada com o backend (criptografia híbrida **AES-256-GCM + RSA**), é **obrigatório** fornecer a chave pública inicial do servidor no arquivo:

📁 `app/resources/initial_key.json`

### 📄 Modelo do `initial_key.json`

```json
{
    "KeyName": "VotaAI_SecureKey_1",
    "PublicKeyBase64": "==chave publica do servidor em base64==",
    "Algorithm": "RSA",
    "Provider": "Microsoft Platform Crypto Provider"
}
```

> **Nota:** Também é suportado o formato de lista de chaves exportado pelo comando `python manage.py generate_se_keys` do backend.

### 📌 Campos do Arquivo:
- **`KeyName`**: Identificador da chave no servidor (padrão: `"VotaAI_SecureKey_1"`).
- **`PublicKeyBase64`**: Chave pública do servidor em formato Base64 (BLOB CNG, DER ou PEM).
- **`Algorithm`**: Algoritmo criptográfico assimétrico utilizado (`"RSA"`).
- **`Provider`**: Nome do provedor criptográfico de origem.

Um arquivo de exemplo também está disponível em [`app/resources/initial_key.json.example`](app/resources/initial_key.json.example).

---

## 🖥️ Como Executar a Aplicação

Com o ambiente virtual ativo e o `initial_key.json` configurado:

```bash
python main.py
```

---

## 🔒 Arquitetura de Segurança Multiplataforma

- **Windows:** Integração com TPM nativo via [cng_windows.py](app/controllers/native/cng_windows.py) (**Windows CNG / `ncrypt.dll`**).
- **Linux / macOS:** Provedor seguro via [tpm_linux.py](app/controllers/native/tpm_linux.py) e [enclave_mac.py](app/controllers/native/enclave_mac.py) com chaves protegidas e permissões estritas de arquivo (`0600`).
- **Comunicação Segura:** Todos os payloads trafegam em envelopes cifrados com **AES-GCM**, onde a chave AES é protegida pela chave pública RSA do servidor e assinada com a chave privada residente no dispositivo.


---

## 📊 Diagramas de Fluxo das Ações do Aplicativo Desktop

Esta seção documenta detalhadamente todos os fluxos e ações desempenhados pelo aplicativo Desktop no ciclo eleitoral, bem como a camada de segurança criptográfica em hardware.

---

### 1. Visão Geral da Navegação e Estados da Aplicação

O ciclo de vida do aplicativo varia conforme a existência de registro prévio e o estado da sessão do administrador:

```mermaid
flowchart TD
    Start([Início da Aplicação]) --> CheckReg{"Máquina vinculada?<br/>(registration_info.json)"}
    
    CheckReg -- Não --> PageCadastro["Tela de Cadastro (Cadastro.qml)"]
    PageCadastro --> FlowReg["Ação 1: Pré-cadastro 2FA + Provisionamento TPM"]
    FlowReg --> PageAuth["Tela de Autenticação (Autenticacao.qml)"]
    
    CheckReg -- Sim --> CheckAuth{"Sessão ativa?"}
    CheckAuth -- Não --> PageAuth
    PageAuth --> FlowAuth["Ação 2: Login com Senha + TOTP + Assinatura TPM"]
    FlowAuth --> MainPanel["Painel Principal (Main.ui.qml)"]
    CheckAuth -- Sim --> MainPanel
    
    MainPanel --> Action1["Ação 3 e 4: Criar Eleição<br/>(Importação CSV + Cédula + Chave no TPM)"]
    MainPanel --> Action2["Ação 5: Iniciar Eleição<br/>(Nonce Anti-Replay + Dupla Assinatura)"]
    MainPanel --> Action3["Ação 6: Fechar Eleição<br/>(Bloqueio de Recebimento de Votos)"]
    MainPanel --> Action4["Ação 7: Apurar Eleição<br/>(Decifração e Contagem dos Votos)"]
```

---

### 2. Ação 1: Pré-cadastro do Administrador e Vinculação da Máquina (TPM + TOTP)

Fluxo executado quando o dispositivo ainda não possui um administrador associado. Realiza o provisionamento do par de chaves RSA em hardware e configuração do segundo fator (TOTP):

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Administrador
    participant UI as Interface (Cadastro.qml)
    participant Auth as AuthController
    participant TPM as TPM 2.0 / Secure Enclave
    participant API as Backend (API)
    actor App2FA as App Autenticador

    Note over Admin,API: Etapa 1: Início do Pré-cadastro e Geração da Chave da Máquina
    Admin->>UI: Insere E-mail institucional e Senha
    UI->>Auth: iniciarPreCadastro(email, password)
    Auth->>TPM: Carrega ou gera par de chaves RSA (client_key.json)
    TPM-->>Auth: Chave Pública da Máquina (PEM / Base64)
    Auth->>Auth: Monta payload com email, password e device_id
    Auth->>Auth: Cifra envelope com AES-256-GCM + RSA do Servidor e assina no TPM
    Auth->>API: POST /api/admin/pre-registration/ (Envelope Híbrido)
    API-->>Auth: Resposta Cifrada (URI de provisionamento TOTP)
    Auth->>TPM: Descriptografa a chave AES da resposta
    Auth->>Auth: Decifra payload e gera QR Code local (totp_qr.png)
    Auth-->>UI: Exibe QR Code e segredo Base32 na tela
    Admin->>App2FA: Escaneia o QR Code no aplicativo autenticador

    Note over Admin,API: Etapa 2: Confirmação e Ativação do Dispositivo
    Admin->>UI: Digita código TOTP de 6 dígitos gerado no app
    UI->>Auth: confirmarPreCadastro(email, totp_code, password)
    Auth->>Auth: Monta payload com email, totp_code e device_id
    Auth->>Auth: Assina e cifra envelope híbrido
    Auth->>API: POST /api/admin/pre-registration/confirm/
    API-->>Auth: Confirmação de ativação do Administrador
    Auth->>Auth: Salva registration_info.json (is_registered: true)
    Auth-->>UI: Emite confirmação e redireciona para a tela de autenticação
```

---

### 3. Ação 2: Autenticação em Dois Fatores (2FA) e Assinatura por Hardware

Login obrigatório para acesso às funções administrativas do sistema. A requisição é autenticada por senha, código TOTP de tempo limitado e a assinatura criptográfica da chave privada residente no chip seguro:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Administrador
    participant UI as Interface (Autenticacao.qml)
    participant Auth as AuthController
    participant TPM as TPM 2.0 / Secure Enclave
    participant API as Backend (API)

    Admin->>UI: Insere Senha e Código TOTP atual
    UI->>Auth: autenticar(senha, codigo_totp)
    Auth->>Auth: Monta payload com username, password, totp_code e device_id
    Auth->>TPM: Assina o JSON canônico com RSA-PSS via chave privada da máquina
    TPM-->>Auth: Assinatura digital da máquina
    Auth->>Auth: Cifra com AES-256-GCM e protege chave AES com RSA do servidor
    Auth->>API: POST /api/auth/login/ (Envelope Cifrado)
    Note over API: Valida senha, TOTP temporizado e a assinatura física da máquina
    API-->>Auth: Envelope Cifrado com Token JWT de Acesso
    Auth->>TPM: Descriptografa a chave AES de sessão
    Auth->>Auth: Decifra payload e armazena authToken
    Auth-->>UI: Emite loginSucesso e libera acesso ao Painel Principal
```

---

### 4. Ação 3: Importação e Validação do Colégio Eleitoral (CSV)

Processamento local dos arquivos CSV contendo os eleitores aptos a votar:

```mermaid
flowchart TD
    Upload["Administrador seleciona arquivo CSV"] --> Read["CsvController lê arquivo linha a linha"]
    Read --> CheckHeader{"Cabeçalho é exatamente<br/>'nomeCompleto,email'?"}
    CheckHeader -- Não --> ErrHeader["Erro: Cabeçalho inválido"]
    CheckHeader -- Sim --> CheckRows["Validação de cada eleitor"]
    
    CheckRows --> CheckDomain{"Email termina com<br/>o domínio institucional (@uesc.br)?"}
    CheckDomain -- Não --> ErrDomain["Erro: Rejeita email não institucional"]
    CheckDomain -- Sim --> CheckDup{"Email já existe<br/>no conjunto?"}
    CheckDup -- Sim --> ErrDup["Erro: Rejeita email duplicado"]
    CheckDup -- Não --> AddRow["Adiciona eleitor à lista validada"]
    
    AddRow --> MoreRows{"Existem mais linhas?"}
    MoreRows -- Sim --> CheckRows
    MoreRows -- Não --> UpdateModel["Atualiza CsvTableModel e QSortFilterProxyModel"]
    UpdateModel --> RenderTable["Tabela reativa renderizada na tela com pesquisa instantânea"]
```

---

### 5. Ação 4: Criação e Registro de Nova Eleição com Chave Dedicada

Geração isolada da chave criptográfica da eleição diretamente no hardware e envio seguro da cédula e colégio eleitoral para a API:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Administrador
    participant UI as Interface (Criacao.qml)
    participant ElectionCtrl as ElectionController
    participant TPM as TPM 2.0 / Secure Enclave
    participant API as Backend (API)

    Admin->>UI: Configura título, perguntas/opções da cédula e colégio eleitoral
    Admin->>UI: Clica em "Salvar Eleição"
    UI->>ElectionCtrl: createElection(titulo, cedula_json)
    
    Note over ElectionCtrl,TPM: Geração da Chave da Eleição no Hardware
    ElectionCtrl->>TPM: generate_hardware_keys()
    Note over TPM: Cria novo par RSA isolado no chip seguro
    TPM-->>ElectionCtrl: Retorna public_key e key_handle
    Note right of TPM: A chave privada da eleição NUNCA sai do chip/armazenamento seguro!

    ElectionCtrl->>ElectionCtrl: Monta payload com title, public_key, key_handle, ballot e electoral_college
    ElectionCtrl->>TPM: Assina payload com a chave privada da máquina (RSA-PSS)
    TPM-->>ElectionCtrl: Assinatura da máquina
    ElectionCtrl->>ElectionCtrl: Cifra payload com AES-256-GCM + chave pública do servidor
    ElectionCtrl->>API: POST /api/election/create/ (Envelope Cifrado)
    API-->>ElectionCtrl: Confirmação de cadastro da eleição
    ElectionCtrl-->>UI: Emite createElectionFinished e exibe feedback de sucesso
```

---

### 6. Ação 5: Consulta e Abertura Oficial da Eleição (Anti-Replay e Dupla Assinatura)

Fluxo de abertura oficial da eleição com proteção contra ataques de repetição (*replay attack*) usando números aleatórios gerados no hardware (*hardware nonces*) e dupla assinatura digital:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Administrador
    participant UI as Interface (Iniciar.qml)
    participant StartCtrl as StartElectionController
    participant TPM as TPM 2.0 / Secure Enclave
    participant API as Backend (API)

    Note over Admin,API: Etapa 1: Consulta de Eleições Disponíveis
    Admin->>UI: Acessa a tela "Iniciar Eleição"
    UI->>StartCtrl: fetchAvailableElections()
    StartCtrl->>TPM: generate_random(16) -> Gera nonceClient1
    TPM-->>StartCtrl: Nonce criptográfico aleatório (16 bytes)
    StartCtrl->>StartCtrl: Monta payload com FETCH_AVAILABLE e nonceClient1
    StartCtrl->>TPM: Assina payload com chave da máquina via TPM (RSA-PSS)
    TPM-->>StartCtrl: Assinatura digital da máquina
    StartCtrl->>StartCtrl: Cifra envelope com AES-256-GCM + chave pública do Servidor
    StartCtrl->>API: POST /api/election/available/ (Envelope Cifrado)
    API-->>StartCtrl: Resposta cifrada contendo lista de eleições e o nonceClient1
    StartCtrl->>TPM: Decifra chave AES de sessão no hardware
    StartCtrl->>StartCtrl: Decifra dados e valida se nonce_recebido == nonceClient1
    StartCtrl-->>UI: Popula lista de eleições aptas a serem iniciadas

    Note over Admin,API: Etapa 2: Abertura Oficial da Eleição (Dupla Assinatura)
    Admin->>UI: Seleciona a eleição desejada e clica em "Iniciar Eleição"
    UI->>StartCtrl: startElection(key_handle)
    StartCtrl->>TPM: generate_random(16) -> Gera nonceClient2
    TPM-->>StartCtrl: Nonce criptográfico aleatório (16 bytes)
    
    Note over StartCtrl,TPM: 1ª Assinatura: Chave Específica da Eleição
    StartCtrl->>TPM: sign_data(key_handle, payload_interno)
    TPM-->>StartCtrl: election_signature
    
    Note over StartCtrl,TPM: 2ª Assinatura: Chave da Máquina (Envelope Global)
    StartCtrl->>TPM: Assina envelope global com chave da máquina
    TPM-->>StartCtrl: machine_signature
    StartCtrl->>StartCtrl: Cifra payload com AES-256-GCM + RSA do Servidor
    
    StartCtrl->>API: POST /api/election/start/
    Note over API: Valida assinatura da eleição, assinatura da máquina e ativa a votação
    API-->>StartCtrl: Confirmação com nonceClient2
    StartCtrl->>StartCtrl: Valida se nonce_recebido == nonceClient2
    StartCtrl-->>UI: Emite startElectionFinished e confirma início oficial
```

---

### 7. Ação 6: Encerramento e Apuração da Eleição

Ações finais de encerramento do recebimento de votos e contagem dos resultados:

```mermaid
sequenceDiagram
    autonumber
    actor Admin as Administrador
    participant UI as Interface (Fechar.qml / Apurar.qml)
    participant Ctrl as Controllers (Python)
    participant TPM as TPM 2.0 / Secure Enclave
    participant API as Backend (API)

    Note over Admin,API: Encerramento da Votação (Fechar.qml)
    Admin->>UI: Seleciona a eleição ativa e clica em "Fechar Eleição"
    UI->>Ctrl: Solicita encerramento da eleição
    Ctrl->>TPM: Assina solicitação com o handle da eleição
    Ctrl->>API: Envia requisição de bloqueio de novos votos
    API-->>Ctrl: Confirmação de encerramento da votação
    Ctrl-->>UI: Atualiza status da eleição para "Encerrada"

    Note over Admin,API: Apuração dos Resultados (Apurar.qml)
    Admin->>UI: Clica em "Apurar Eleição"
    UI->>Ctrl: Dispara processo de totalização
    Ctrl->>API: Requisita os votos cifrados da eleição
    API-->>Ctrl: Retorna cédulas cifradas com a chave pública da eleição
    Ctrl->>TPM: Descriptografa votos utilizando a chave privada residente (key_handle)
    Note over TPM: A decifração ocorre no módulo seguro (a chave nunca é exposta)
    TPM-->>Ctrl: Votos individuais decifrados
    Ctrl->>Ctrl: Totaliza votos por questão e gera estatísticas
    Ctrl-->>UI: Exibe relatório de apuração e resultados oficiais
```

---

### 8. Protocolo Criptográfico de Envelope Híbrido (Sign-then-Encrypt)

Padrão de comunicação utilizado em **todas** as interações entre o aplicativo Desktop e o Servidor Backend:

```mermaid
sequenceDiagram
    autonumber
    participant Desktop as Desktop App (Python)
    participant TPM as Chip de Segurança (TPM / CNG)
    participant Rede as Comunicação de Rede (HTTP)
    participant Server as Backend Server (API)

    Note over Desktop,Server: Envio: Sign-then-Encrypt
    Desktop->>Desktop: 1. Serialização Canônica JSON (chaves ordenadas, sem espaços)
    Desktop->>TPM: 2. Assina hash SHA-256 com RSA-PSS da chave da máquina
    TPM-->>Desktop: Assinatura digital da máquina
    Desktop->>Desktop: 3. Injeta machine_public_key e signature no payload
    Desktop->>Desktop: 4. Gera chave AES-256 efêmera e IV aleatório (12 bytes)
    Desktop->>Desktop: 5. Cifra payload com AES-256-GCM -> (ciphertext, tag de 16 bytes)
    Desktop->>Desktop: 6. Cifra a chave AES com a chave pública RSA do servidor (initial_key.json)
    Desktop->>Rede: 7. Envia envelope {encrypted_payload, encrypted_aes_key, iv, tag}
    Rede->>Server: Entrega requisição HTTP POST

    Note over Desktop,Server: Resposta: Decifração no Hardware
    Server-->>Rede: Retorna envelope {encrypted_payload, encrypted_aes_key, iv, tag}
    Rede-->>Desktop: Recebe resposta cifrada
    Desktop->>TPM: 8. Descriptografa encrypted_aes_key com a chave privada da máquina
    TPM-->>Desktop: Chave AES efêmera descriptografada
    Desktop->>Desktop: 9. Decifra ciphertext com AES-256-GCM usando chave AES, IV e tag
    Desktop->>Desktop: 10. Converte JSON decifrado para uso da aplicação
```


---

## 📂 Estrutura de Pastas

A organização do repositório foi planejada para separar claramente a interface (UI) das regras de negócio (Python) e serviços de rede:

```text
votaai-desktop/
├── app/                  # Lógica de negócio e comunicação em Python
│   ├── controllers/      # Controladores que integram as telas (QML) com as ações do sistema (ex: AuthController)
│   ├── services/         # Serviços puramente de API e rede (ex: HttpClient, ElectionApi)
│   └── resources/        # Arquivos locais e de chaves criptográficas (ex: initial_key.json)
├── Design/               # Interface de Usuário (UI)
│   └── DesignContent/    # Componentes visuais e telas desenvolvidos em Qt Quick / QML
├── mock_csvs/            # Arquivos CSV usados para testes locais
├── main.py               # Arquivo principal que inicia a aplicação PySide6
├── run_commands.py       # Script utilitário para facilitar comandos do Git/CLI do projeto
└── requirements.txt      # Arquivo de dependências do Python
```
