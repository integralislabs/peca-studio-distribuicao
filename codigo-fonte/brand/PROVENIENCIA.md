# Marca oficial Integralis Labs no Peça Studio

Fonte: repositório privado `integralislabs/integralis`, revisão `0e2781a`, consultada em 05/11/2026 pelo conector GitHub autorizado.

- `integralis-logo.svg`: cópia byte a byte de `brand/integralis-logo.svg`. SHA-256 `e0e4ad8f4bbf4b08c1125daf1b49609a04ff16d101b16e6b9ef7746c91ac8325`.
- `tokens.css`: cópia byte a byte de `brand/tokens.css`. SHA-256 `9bcfd5480c54ed8a9568d15e677bd3b3e8d1eb5b57b0e46812070ad24c50a596`.
- `integralis-icon.svg`: conteúdo oficial de `apps/web/app/icon.svg` (apenas normalização de quebra final ao salvar); Git blob `317a741550b17c33516eaca89a14caeab08e418a`.
- `fonts/*.woff2`: quatro arquivos binários exatos de `apps/web/app/fonts/`, obtidos em base64, decodificados localmente sem conversão. Nomes, tamanhos e SHA-256 em `source-hashes.json`.
- `fonts/fonts.css`: quatro primeiras declarações de `apps/web/app/fonts/fonts.css`, mantendo famílias, pesos e unicode-ranges originais; somente as fontes usadas na interface são distribuídas.
- `fonts/OFL.txt`: licença oficial de `brand/fonts/OFL.txt`, SIL Open Font License 1.1. Montserrat © 2024 The Montserrat.Git Project Authors; Public Sans © 2015 The Public Sans Project Authors. O texto oficial inclui também o aviso IBM Plex, que não é distribuído nesta adaptação.

A especificação de uso foi lida de `brand/README.md`: arte sem alteração de cor ou proporção, nome em Public Sans 700 com INTEGRALIS `#7fd6f0` e LABS `#9aa2a7`. O desenho ocupa 31 px de altura, com área livre ao redor, no desktop; permanece acima do mínimo de 24 px nas larguras móveis.

`../integralis-theme.css` adapta apenas a interface aos tokens oficiais: fundo `#070609`, painéis `#0f0f15`/`#111118`, ações `#1c6f8c`/`#0e5576`, foco `#7fd6f0`, corpo Montserrat e títulos Public Sans. O tema escuro é fixado em `index.html` para coincidir com o produto. Nenhuma regra altera pixels de canvas, documentos em iframe ou cores de arte; cores de identificação de projetos permanecem controladas pelo usuário.

O produto aparece como Peça Studio, subordinado à marca Integralis Labs. A seção Conta Integralis é estilizada pelo seu rótulo sem atribuir estado de compra; o estado exibido vem da integração de conta. Diálogos com CSS inserido em tempo de execução usam sobrescritas limitadas aos controles e ao contêiner, sem aplicar regras à arte.

Os tokens oficiais documentam contraste de texto, foco e botões; esta adaptação mantém suas combinações. A aprovação de aparência e responsividade depende da inspeção visual do aplicativo, além da integridade dos arquivos.
