# Módulo de Portaria e Reconhecimento Facial

Este módulo é responsável pela detecção e identificação facial dos alunos e funcionários no ponto de acesso escolar, integrando-se em tempo real com o BackEnd Django e o banco PostgreSQL.

---

## 🛠️ Tecnologias Utilizadas
- **Python 3.12**
- **OpenCV (opencv-python)**: Detecção de faces via Haar Cascade e correspondência de padrões faciais.
- **Requests**: Comunicação HTTP com a API REST do Django (/api/access/, /api/bootstrap/).
- **NumPy**: Processamento matricial de imagens.

---

## 🚀 Como Executar

### 1. Iniciar o Back-end
Certifique-se de que o Django está rodando na porta 8000:
`ash
cd BackEnd
python manage.py runserver
`

### 2. Cadastrar Rostos
Para cadastrar os rostos dos alunos/funcionários a partir da webcam ou de uma imagem:
`ash
cd portaria
python cadastrar_rosto.py
`
* O script listará as pessoas cadastradas no banco de dados.
* Digite o ID desejado e pressione [ESPAÇO] em frente à câmera para salvar o rosto.
* As fotos e padrões ficam salvos em portaria/rostos/.

Você também pode associar uma foto existente:
`ash
python cadastrar_rosto.py --id 1 --imagem caminho/para/foto.jpg
`

### 3. Iniciar o Monitoramento em Tempo Real
`ash
cd portaria
python reconhecimento.py
`

#### ⌨️ Controles do Monitoramento:
- **[S]**: Alterna o sentido entre **ENTRADA** e **SAÍDA**.
- **[T]**: Simula a passagem e reconhecimento de um aluno para teste.
- **[C]**: Abre o assistente de cadastro facial diretamente.
- **[Q] ou [ESC]**: Encerra a aplicação.

Caso você esteja sem câmera conectada no momento, o sistema entra automaticamente no **Modo de Simulação Interativa**, permitindo testar todos os registros e geração de alertas para o painel web.
