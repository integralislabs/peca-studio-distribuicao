> PREPARAÇÃO DA VERSÃO 1.10.1 — conteúdo para revisão. Os links versionados abaixo só devem ser ativados depois da publicação final. Este arquivo não muda o canal ativo.

# Peça Studio · Integralis Labs

Estúdio criativo para Windows: organize projetos, crie peças e carrosséis, edite HTML/CSS e transforme imagens em camadas editáveis.

**[Conhecer e assinar na Integralis](https://integralislabs.com/marketplace/peca-studio)** · **[Baixar instalador para Windows](https://github.com/integralislabs/peca-studio-distribuicao/releases/download/v1.10.1/PecaStudio-Setup-1.10.1.exe)**

## Começar

1. Assine o Peça Studio na Integralis. A assinatura mensal custa US$ 20; confira o valor final no checkout.
2. Baixe o arquivo `PecaStudio-Setup-1.10.1.exe` da release e instale no Windows 10/11 de 64 bits com Microsoft Edge WebView2 disponível.
3. Abra o Peça Studio e clique em **Entrar com Integralis**, usando a conta com acesso ao produto.
4. Crie seu projeto ou importe suas peças. Os exemplos iniciais são demonstrações.

É necessária conexão à internet para confirmar o acesso. A política da Integralis permite uma sessão de uso por conta; iniciar outro aplicativo pode substituir a sessão atual.

## O que inclui

- Planejamento de carrossel, briefing e revisão local de conteúdo e marca.
- Alertas editoriais são triagens; fatos, fotos e exceções de marca exigem conferência humana.
- Biblioteca com grade, lista e Kanban; projetos, pastas, busca, modelos, kit de marca e lixeira.
- Editor de texto, formas, imagens, camadas e slides; importação e edição de HTML/CSS preservado.
- Conversão de imagens com OCR local e revisão da qualidade e das fontes. A separação em camadas pode precisar de ajustes manuais.
- Exportação para imagem, PDF para impressão e vídeo; fontes personalizadas e recursos de impressão.
- Conexão opcional com provedores de IA, transcrição e fontes de vídeo.
- Backup local e integração MCP para agentes autorizados no computador.

Os recursos de IA exigem configuração da chave do provedor pelo próprio usuário. **Consumo e cobranças dos provedores de IA são separados da assinatura** e não incluem créditos de geração neste plano. Downloads de fontes externas dependem da disponibilidade e da permissão de acesso ao conteúdo.

## Dados e atualizações

Seu acervo permanece no computador. Faça backup em **Configurações e backup**. Não envie chaves, credenciais ou acervos privados em chamados públicos. Recursos de IA e publicação enviam o conteúdo necessário ao provedor configurado quando você os utiliza.

O instalador contém o aplicativo e ferramentas locais; não contém biblioteca privada nem chaves de IA. Antes da publicação da versão 1.10.1, a TI deve confirmar a assinatura digital do aplicativo, Setup e desinstalador. O manifesto final deve informar o SHA-256 dos bytes assinados para conferência da integridade. As atualizações são verificadas no aplicativo e dependem de confirmação para instalar.

Este repositório distribui o instalador, documentos de uso e o manifesto de atualização, e também contém o [código-fonte revisado da versão 1.9.1](https://github.com/integralislabs/peca-studio-distribuicao/tree/main/codigo-fonte), com testes e scripts de build. A pasta informa a origem, as adaptações e como executar o projeto. As licenças das dependências acompanham o aplicativo. A publicação do código não adiciona uma nova licença de reutilização.

## Suporte

[Abrir um chamado sobre o Peça Studio](https://github.com/integralislabs/peca-studio-distribuicao/issues/new). Descreva a versão, o que tentou fazer e a mensagem exibida, sem incluir dados privados. Assinaturas, conta e pagamentos são administrados pela [Integralis Labs](https://integralislabs.com).

## Fontes correspondentes e licenças

Links candidatos: publicar estes arquivos junto do instalador final e conferir os hashes antes de ativar a página. Cada componente mantém seus direitos e avisos. As receitas próprias de reprodução têm MIT restrita a esses scripts, sem alterar a licença do aplicativo.

- [PecaStudio-1.10.1-FONTES-PYTHON-E-AVISOS.zip](https://github.com/integralislabs/peca-studio-distribuicao/releases/download/v1.10.1/PecaStudio-1.10.1-FONTES-PYTHON-E-AVISOS.zip)
- [PecaStudio-1.10.1-FONTES-OCR.zip](https://github.com/integralislabs/peca-studio-distribuicao/releases/download/v1.10.1/PecaStudio-1.10.1-FONTES-OCR.zip)
- [PecaStudio-1.10.1-FONTES-VIDEO.zip](https://github.com/integralislabs/peca-studio-distribuicao/releases/download/v1.10.1/PecaStudio-1.10.1-FONTES-VIDEO.zip)
- [Índice de fontes e hashes](https://github.com/integralislabs/peca-studio-distribuicao/releases/download/v1.10.1/SOURCE-KIT-INDEX.json)

A biblioteca svglib LGPL pode ser substituída por fonte compatível em `_internal/svglib/`; instruções e textos completos acompanham o pacote. A TI deve regenerar o vínculo dos kits depois de assinar o Setup.
