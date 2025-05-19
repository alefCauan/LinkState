# LinkState

Este projeto implementa uma simulação de rede de computadores utilizando Python e Docker, onde os roteadores implementam o Algoritmo de Roteamento por Estado de Enlace (Link State Routing Algorithm).

## Como Executar o Projeto

1. **Pré-requisitos**:
   - Docker e Docker Compose instalados.
   - Python >= 3.9 instalado (para scripts auxiliares).

2. **Gerar a topologia da rede**:
   - Execute o script de geração de topologia:
     ```bash
     python3 generate_topology.py
     ```
   - Isso irá criar o arquivo `network_topology.json` com a descrição da topologia.

3. **Gerar o docker compose**:
   - Execute o script de geração do Docker Compose:
     ```bash
     python3 generate_docker_compose.py
     ```
   - Isso irá criar o arquivo `docker-compose.yml` com a configuração dos containers.

4. **Construir e iniciar os containers**:
   - Utilize o Docker Compose para subir a infraestrutura:
     ```bash
     docker-compose up --build
     ```
   - Os containers de roteadores e hosts serão criados conforme a topologia gerada.

5. **Acompanhar logs**:
   - Os logs dos roteadores e hosts podem ser visualizados pelo Docker Compose ou acessando cada container individualmente.

## Justificativa do(s) Protocolo(s) Escolhido(s)

O protocolo escolhido foi o **UDP** (User Datagram Protocol). O UDP foi escolhido por ser um protocolo leve, sem conexão e com baixa sobrecarga, ideal para o envio frequente de mensagens de controle (como pacotes de descoberta e anúncios de estado de enlace) em ambientes simulados. Como o objetivo principal é a troca rápida de informações de roteamento e a rede simulada é controlada, a confiabilidade do TCP não é necessária, tornando o UDP mais adequado para este cenário.

## Como a Topologia Foi Construída

A topologia é gerada automaticamente pelo script `generate_topology.py`, que executa os seguintes passos:

- Define o número de sub-redes (por padrão, 3).
- Para cada sub-rede, cria 1 roteador e 2 hosts conectados a ele.
- Os hosts são conectados diretamente ao roteador de sua sub-rede, sem custo de caminho (essas ligações não afetam o cálculo de rotas).
- Os roteadores são conectados entre si formando uma topologia parcialmente conectada, com pesos aleatórios nas ligações entre roteadores, simulando diferentes custos de enlace.
- O grafo gerado é garantido como conectado, e a estrutura é salva em um arquivo JSON, que serve de base para a configuração dos containers Docker.

## Visão Geral

A rede consiste em múltiplas sub-redes, cada uma contendo:
- 2 hosts
- 1 roteador

Os roteadores conectam-se entre si em uma topologia aleatória (parcialmente conectada) e implementam o algoritmo de estado de enlace, mantendo:
- Banco de Dados de Estado de Enlace (LSDB)
- Tabela de roteamento atualizada com base no algoritmo de Dijkstra

## Principais Funcionalidades

- Roteadores multi-threaded com threads separadas para:
    - Recepção de pacotes de estado de enlace
    - Transmissão de pacotes de estado de enlace
- Containerização Docker para hosts e roteadores
- Atualização dinâmica das tabelas de roteamento
- Geração automática e aleatória da topologia

## Tecnologias

- Python: Lógica central da rede
- Docker: Simulação da infraestrutura de rede
- Comando `route`: Manutenção das tabelas de roteamento
- Threading: Execução concorrente nos roteadores
- Algoritmo de Dijkstra: Cálculo de rotas ótimas
- Link State Routing Algorithm: Protocolo de roteamento principal
- Programação de sockets: Comunicação entre roteadores e hosts

## Status do Projeto

Projeto desenvolvido para a disciplina de REDES DE COMPUTADORES II da UFPI - Campus CSHNB.

## Demonstração em Vídeo

[Project demonstration available on YouTube](#)


