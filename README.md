# Manual Studio Qt5

Editor de manuais técnicos feito em **Python + PyQt5**. O projeto mantém o conteúdo em tópicos e gera diferentes formatos a partir da mesma fonte.

## Recursos

- projeto `.qmanual` em JSON, com imagens incorporadas em Base64;
- árvore hierárquica de tópicos e subtópicos;
- arrastar e soltar tópicos na árvore;
- editor rich-text com negrito, itálico, sublinhado, H1/H2/H3, alinhamento, listas, links, tabelas, cor e imagens;
- seletor de **fonte e tamanho em pontos** na barra de formatação;
- menu **Inserir** com imagem, ajuste de imagem, tabela, link, linha horizontal e quebra de página;
- inserção de imagem com tamanho físico em **mm**, porcentagem da largura útil e alinhamento esquerda/centro/direita;
- reajuste posterior de uma imagem já inserida (também por duplo clique);
- imagens antigas ou maiores que a área útil são limitadas automaticamente no PDF, sem distorcer a proporção;
- propriedades do manual: título, autor/empresa, versão, idioma, rodapé e logo;
- configuração de página com **A4, A5, Carta e Ofício**, orientação retrato/paisagem e margens independentes;
- cabeçalho e rodapé configuráveis, inclusive logo no rodapé;
- tipografia global configurável: fonte, corpo, H1, H2, H3, entrelinhas e espaçamento de parágrafo;
- capa e sumário automáticos opcionais;
- exportação **HTML** com navegação lateral;
- exportação **PDF** com escala física corrigida, cabeçalho/rodapé e paginação automática;
- exportação **CHM** via Microsoft HTML Help Workshop (`hhc.exe`);
- se o `hhc.exe` não estiver instalado, o programa ainda gera o projeto `.hhp`, `.hhc`, `.hhk` e HTML para compilação posterior.

## Instalação

No Windows, com Python 3.10+:

```bat
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py main.py
```

## Configuração da página

Use **Manual > Configuração da página...**.

As abas permitem controlar:

- papel e orientação;
- margens superior, inferior, esquerda e direita;
- reserva e distância do cabeçalho/rodapé;
- logo no rodapé;
- fonte e tamanhos tipográficos;
- entrelinhas e espaçamento de parágrafo;
- geração automática de capa e sumário.

As medidas são gravadas no próprio `.qmanual`.

## Imagens

Use **Inserir > Imagem...**. Antes de inserir, o programa mostra uma janela para definir:

- largura em milímetros;
- largura em porcentagem da área útil da página;
- alinhamento à esquerda, centralizado ou à direita;
- atalhos de 25%, 50%, 75% e 100%.

A proporção original é preservada. Para modificar uma imagem já existente, use **Inserir > Ajustar imagem selecionada...** ou dê duplo clique nela.

## CHM

O formato CHM depende do compilador **Microsoft HTML Help Workshop**. O Manual Studio procura automaticamente por:

```text
C:\Program Files (x86)\HTML Help Workshop\hhc.exe
C:\Program Files\HTML Help Workshop\hhc.exe
```

Também é possível selecionar manualmente em **Ferramentas > Configurar compilador CHM**.

> O `hhc.exe` não é incluído no projeto.

## PDF

O PDF é produzido diretamente pelo sistema de impressão do Qt, sem LibreOffice, Word ou navegador externo.

Nesta versão, o documento do Qt é diagramado em uma base lógica de **96 dpi** e escalado para a resolução física da impressora PDF. Isso corrige o problema da versão inicial em que conteúdo, imagens e fontes podiam sair muito pequenos em relação à folha.

## Estrutura do projeto

```text
manual_studio_qt5/
├─ main.py
├─ requirements.txt
├─ build_windows.bat
└─ manual_studio/
   ├─ model.py
   ├─ editor.py
   ├─ dialogs.py
   ├─ exporters.py
   ├─ ui_extras.py
   └─ main_window.py
```

## Gerar EXE

Execute:

```bat
build_windows.bat
```

O executável será criado em `dist\ManualStudioQt5.exe`.

O ícone do aplicativo fica em `assets/manual_studio.ico` e também é incorporado ao executável pelo PyInstaller. A versão PNG transparente correspondente está em `assets/manual_studio.png`.

## Melhorias desta revisão

- Correção do erro `QTextBlockFormat.setAlignment(...): unexpected type 'int'` ao inserir imagens.
- Imagens selecionadas exibem uma alça no canto inferior direito e podem ser redimensionadas arrastando com o mouse, preservando a proporção.
- Duplo clique ou botão direito na imagem abre tamanho e posição; também há alinhamento à esquerda, centro e direita.
- Novo comando **Inserir > Imagem com texto ao lado...** cria um bloco de duas colunas sem borda, com divisão configurável (por exemplo 50/50), permitindo imagem à esquerda e texto à direita ou o inverso.
- Imagens podem ser inseridas dentro de células de tabelas; o limite de largura passa a considerar a coluna atual.
- Inserção de tabela ganhou diálogo com linhas, colunas, largura, borda, padding e opção de primeira linha em negrito.
- Botão direito dentro de uma tabela oferece **Propriedades / tamanho**, inserção e remoção de linhas/colunas.
- Propriedades da tabela permitem largura total e proporções individuais das colunas.
- Barra de formatação ampliada: fonte, tamanho, negrito, itálico, sublinhado, alinhamento inclusive justificado, listas, recuo, cor e realce.
- A barra acompanha a formatação do texto na posição atual e a seleção também pode ser formatada pelo menu de contexto.

## Cabeçalho e rodapé avançados

Em **Manual > Propriedades > Cabeçalho e rodapé** há um designer para cada faixa. Ele permite texto rico com fontes/tamanhos diferentes, logo, fundo sólido, gradiente ou imagem, linha separadora e espaçamentos internos.

Itens dinâmicos disponíveis nos templates:

- `{{title}}` — título do manual;
- `{{author}}` — autor/empresa;
- `{{version}}` — versão definida nas propriedades;
- `{{page}}` e `{{pages}}` — página atual e total no PDF;
- `{{topic}}` — tópico que ocupa a página;
- `{{category}}` — categoria raiz do tópico;
- `{{date}}` — data da exportação;
- `{{language}}` — idioma do projeto;
- `{{footer_text}}` — texto livre configurado nas propriedades;
- `{{logo}}` — logo principal do manual.

A versão é resolvida no momento da exportação, portanto alterar **Versão do manual** atualiza automaticamente qualquer cabeçalho ou rodapé que use `{{version}}`.

## Melhorias v4 — diagramação, CSS e idiomas

- régua horizontal estilo editor de texto, com marcadores arrastáveis para margem esquerda/direita e guias pontilhadas durante o ajuste;
- proteção de área útil: a régua mantém no mínimo 40 mm de largura, o diálogo de página valida margens e imagens/tabelas antigas são limitadas ao espaço disponível;
- imagens podem ser movidas horizontalmente arrastando a própria imagem; a posição é limitada à área útil ou à célula atual;
- `Backspace`, `Delete`, digitação sobre seleção e recorte não apagam imagens selecionadas acidentalmente; a exclusão fica no menu de contexto e pede confirmação;
- layouts **Imagem + texto** recebem proteção adicional antes de alterações estruturais de tabela;
- ferramenta **Remover fundo por cor** para imagens, com tolerância configurável (usa Pillow);
- prévia visual de cabeçalho e rodapé dentro das Propriedades e no designer, incluindo cores/gradientes e conteúdo dinâmico;
- botão direto **Editar cabeçalho** / **Editar rodapé** na área do documento;
- cada tópico pode herdar, exibir ou ocultar cabeçalho e rodapé individualmente em **Opções desta página...**;
- a Introdução dos novos projetos e as páginas automáticas de capa/sumário são criadas sem cabeçalho/rodapé por padrão;
- tópicos especiais: **Sumário automático** e **Histórico de revisões**. O sumário continua automático, mas o tópico permanece editável para textos introdutórios;
- criação de novo projeto com três bases: em branco, manual técnico completo e manual de software;
- suporte a vários idiomas no mesmo `.qmanual`, com conteúdo/título por idioma e fallback para o idioma principal;
- HTML multilíngue com seletor de idioma no próprio manual;
- PDF pode ser gerado em um idioma, em arquivos separados por idioma, ou com todos os idiomas sequencialmente em um único PDF;
- editor de **HTML / CSS** em `Manual > Propriedades > HTML / CSS` e também em `Manual > Estilo HTML / CSS...`;
- ajustes fáceis de cores, largura da navegação e largura do conteúdo, mais CSS livre aplicado por último para sobrescrever o tema base.

A régua de margens altera os mesmos valores usados pela exportação PDF, portanto não existe uma segunda configuração escondida: o que é ajustado na régua é o que o documento grava.

## Alterações v5

- Gerenciador de idiomas com idioma padrão/fonte editorial.
- Cópia automática opcional do idioma padrão ao adicionar idiomas.
- Sincronização segura: somente cópias ainda não traduzidas acompanham mudanças da fonte.
- Cópia manual de qualquer idioma para qualquer outro; não existe tradução automática.
- Novos tópicos podem ser espelhados automaticamente nos idiomas configurados.
- Margens do editor aplicadas ao frame real do QTextDocument, usando a largura física da folha.
- Régua usa a escala da página e as margens são reaplicadas após carregar HTML.
- Imagens podem ser substituídas individualmente ou ter o arquivo-fonte do recurso substituído pelo menu de contexto.
- Ajuda interna própria em `manual_studio.ajuda`, com contêiner binário versionado, zlib e CRC32.
- `F1` abre a ajuda interna; também é possível abrir outros arquivos `.ajuda`.
- O build PyInstaller inclui automaticamente o arquivo `.ajuda`.
- O próprio manual também pode ser exportado como um único arquivo binário `.ajuda`, incluindo idiomas, tópicos e imagens; o visualizador interno abre esse formato.

## PDF v6 — composição por tópicos

O exportador PDF foi refeito para não montar o manual inteiro como um único fluxo contínuo. Agora capa, sumário e cada tópico são medidos e paginados separadamente. Cada tópico começa em uma nova página física; se o conteúdo do tópico ultrapassar a folha, somente esse tópico continua nas páginas seguintes.

Em **Manual > Configuração do PDF...** (e também pelo menu Arquivo) é possível configurar capa, título/numeração dos tópicos, comportamento de cabeçalho/rodapé, qualidade, numeração inicial e o sumário. O sumário usa duas passagens de layout para mostrar os números de página reais dos tópicos antes da gravação final do PDF.


## v7 — WebHelp e PDF refinados

- Sumário automático independente para HTML e PDF; não é necessário criar um tópico de sumário.
- HTML com prévia ao vivo, seletor de cores, barra superior com idioma, árvore recolhível e rodapé preso ao fim da janela.
- Exportação HTML sempre cria uma subpasta própria dentro da pasta escolhida.
- Página inicial do HTML configurável.
- Capa do PDF com fundo sólido, gradiente ou imagem, alinhamento, logo, título, autor, versão e idioma configuráveis.
- Imagens podem receber links pelo menu de contexto.
- Inserção de blocos de código com estilo próprio no editor, HTML e PDF.

## v8 — prévia WebHelp em RAM, capa PDF e build cx_Freeze

Projeto oficial: https://github.com/Valdemir-DSW/manual_studio_qt5

### Prévia HTML / WebHelp

A tela **HTML / WebHelp** agora usa `PyQtWebEngine` quando disponível. Em vez de desenhar uma aproximação com `QTextBrowser`, ela pré-compila o projeto aberto e renderiza a mesma estrutura do WebHelp: barra superior, seletor de idioma, árvore, sumário, introdução, tópicos, cabeçalho, rodapé, CSS personalizado e imagens.

A prévia usa um `QWebEngineProfile` off-the-record, cache `MemoryHttpCache` e o esquema interno `manualpreview://`; o documento compilado é servido por bytes em memória. Nenhuma pasta temporária é criada para essa prévia. Alterações visuais/CSS são recompiladas com debounce curto enquanto o diálogo está aberto.

A configuração HTML também possui o campo **Link do projeto/suporte**, inicialmente apontando para o repositório oficial. Ele pode ser exibido na página inicial do WebHelp.

### Capa do PDF

**Manual > Configuração do PDF > Capa** possui agora uma prévia proporcional da folha e controles específicos para:

- tipo de fundo: nenhum, sólido, gradiente ou imagem;
- duas cores e direção do gradiente;
- imagem de fundo com `Cobrir`, `Conter` ou `Esticar`;
- escala de 10% a 400%;
- posição X/Y e opacidade;
- reposicionamento da imagem diretamente arrastando-a na prévia;
- logo específico da capa ou logo principal;
- tamanho do logo, título, subtítulo, cor/tamanho do título, alinhamento e posição vertical;
- visualização das margens físicas por linha pontilhada.

Os mesmos parâmetros são usados pela exportação final do PDF.

### Build cx_Freeze + Inno Setup

Além do `build_windows.bat` com PyInstaller, existem:

```text
setup_cxfreeze.py
build_cxfreeze_installer.bat
installer/manual_studio.iss
```

`build_cxfreeze_installer.bat`:

1. localiza `py` ou `python`;
2. instala as dependências e `cx_Freeze`;
3. gera `build\ManualStudio\ManualStudioQt5.exe`;
4. procura automaticamente `ISCC.exe` do **Inno Setup 6** em `Program Files`, `LocalAppData`, `PATH` e chaves de desinstalação do Registro;
5. quando encontrado, compila `dist\ManualStudioQt5_Setup.exe`.

Se o Inno Setup não estiver instalado, o build cx_Freeze continua disponível em `build\ManualStudio` e o BAT informa exatamente o que faltou.

## v9 — fragmentos portáteis de tópicos

O Manual Studio pode transformar um tópico em um arquivo portátil `.mfrag` para reutilização em outros projetos.

### Exportar fragmento

Selecione um tópico e use **Arquivo → Exportar tópico como fragmento...** ou clique com o botão direito na árvore e escolha **Exportar como fragmento...**.

Na janela de exportação é possível escolher:

- o tópico raiz e quais subtópicos entram no pacote;
- somente o idioma atual ou vários idiomas;
- imagens e recursos incorporados;
- formatação rich-text (fontes, listas, tabelas, alinhamentos e links);
- propriedades específicas dos tópicos, como cabeçalho, rodapé, tipo especial e participação no sumário;
- tipografia global do documento;
- folha e margens;
- cabeçalho e rodapé;
- estilo HTML/CSS;
- configuração visual do PDF.

O fragmento **não traduz automaticamente** os textos. Os idiomas são copiados exatamente como existem no projeto de origem.

### Importar fragmento

Use **Arquivo → Importar fragmento...** e escolha onde a nova estrutura será anexada no manual.

Antes da importação o programa mostra a árvore do pacote e permite:

- selecionar novamente os tópicos que serão importados;
- escolher um tópico de destino ou a raiz do manual;
- mapear cada idioma do fragmento para um idioma existente;
- adicionar ao projeto idiomas que ainda não existem;
- ignorar idiomas que não serão usados;
- aplicar ou ignorar os estilos globais transportados pelo fragmento.

Os estilos globais ficam **desmarcados por padrão na importação**, evitando que um fragmento altere silenciosamente a aparência do projeto de destino. Imagens incorporadas recebem novos identificadores internos e suas referências são reescritas automaticamente para evitar conflitos.
