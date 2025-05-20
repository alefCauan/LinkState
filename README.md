# 🛰️ LinkState - Simulador de Roteamento por Estado de Enlace

Este projeto simula uma rede de computadores em ambiente Docker, onde cada roteador executa o algoritmo **Link State Routing** (baseado em Dijkstra). A comunicação entre nós da rede é realizada via **UDP**, e toda a infraestrutura é gerada dinamicamente com Python.

> ⚙️ Projeto desenvolvido como parte da disciplina **Redes de Computadores II** – UFPI | Campus CSHNB.

---

## 🚀 Como Executar o Projeto

### 1. Pré-requisitos

- [x] **Docker**  
- [x] **Python** ≥ 3.9 (para executar scripts auxiliares)

---

### 2. Criar Ambiente Virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
---

### 3. Gerar Topologia da Rede


```bash
python3 generate_topology.py
```

Gera o arquivo `network_topology.json`, contendo a estrutura da rede (roteadores, hosts e enlaces com custos).

### 4. Criar Arquivo docker-compose

```bash
python3 generate_docker_compose.py
```

Gera dinamicamente o `docker-compose.yml` baseado na topologia criada.

### 5. Construir e Subir os Containers

```bash
docker-compose up --build
```

Todos os roteadores e hosts são iniciados conforme a topologia gerada.

### 6. Monitorar Logs da Rede

Você pode acompanhar os logs diretamente pelo Docker Compose ou acessar os containers individualmente para depuração detalhada.

### 7. Fechar o projeto

```bash
./down.sh

---

## 🌐 Estrutura da Rede

* Cada **sub-rede** contém:

  * 🖥️ 2 hosts
  * 🔁 1 roteador

* Os **roteadores** se conectam entre si de forma aleatória e parcialmente conectada, com **pesos variáveis** (custos de enlace).

* Cada roteador implementa:

  * Banco de Dados de Estado de Enlace (**LSDB**)
  * Algoritmo de **Dijkstra** para cálculo das melhores rotas
  * Threads independentes para **envio** e **recepção** de LSAs via UDP

---

## 📡 Por que UDP?

O protocolo escolhido para a comunicação entre roteadores é o **UDP**. Ele é ideal para esse tipo de simulação porque:

* É **leve** e tem **baixa sobrecarga**
* Não exige conexão prévia (sem handshake)
* Tolerância à perda de pacotes (ambiente controlado)
* Maior velocidade para **mensagens frequentes**, como pacotes Discovery e LSAs

---

## 🛠️ Como a Topologia é Gerada

O script `generate_topology.py` executa:

* Geração automática de `N` sub-redes (por padrão, 3)
* Criação de roteadores e hosts por sub-rede
* Conexões aleatórias entre roteadores com pesos (custos)
* Garantia de conectividade entre todos os nós
* Exportação da topologia no formato JSON

---

## 🔧 Principais Funcionalidades

* ✅ Roteadores com múltiplas threads para recepção/transmissão de pacotes
* ✅ Atualização **automática e dinâmica** das tabelas de roteamento
* ✅ Containerização de todos os nós da rede (hosts + roteadores)
* ✅ Comunicação via sockets UDP
* ✅ Geração automatizada da rede via scripts Python
* ✅ Interface modular, permitindo customização da topologia 

---

## 🧰 Tecnologias Utilizadas

| Tecnologia          | Finalidade                                  |
| ------------------- | ------------------------------------------- |
| **Python**          | Scripts de controle e lógica do protocolo   |
| **Docker**          | Criação dos nós em containers isolados      |
| **Docker Compose**  | Orquestração dos containers                 |
| **UDP Sockets**     | Comunicação entre os roteadores             |
| **Threading**       | Execução paralela de funções nos roteadores |
| **Dijkstra**        | Algoritmo de cálculo das rotas ótimas       |
| **`route` command** | Manipulação da tabela de rotas dos hosts    |

---

## 📺 Demonstração em Vídeo

🎥 Em breve: [Acesse a demonstração no YouTube](#)

---

## 📚 Créditos

Desenvolvido para o curso de **SISTEMAS DE INFORMAÇÃO** – UFPI (CSHNB)
Disciplina: *Redes de Computadores II*
---

## 📜 Licença
Este projeto é licenciado sob a Licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.