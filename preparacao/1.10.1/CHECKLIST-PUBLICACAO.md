# Publicação 1.10.1 — checklist da TI

O canal ativo é controlado pelos arquivos da raiz. Esta pasta é staging: não altera README.md, release-manifest.json, o instalador disponível ou a cobrança. Não mesclar ativação do canal antes de todos os requisitos abaixo.

## Antes de tornar a release pública
- [ ] Confirmar assinatura válida e timestamp no aplicativo, Setup e desinstalador; registrar o certificado empresarial correto.
- [ ] Recalcular hashes dos bytes finais e regenerar o vínculo dos kits ao instalador assinado. Não reutilizar índice ou hash de candidato sem assinatura.
- [ ] Executar a homologação com exigência de assinatura e substituição LGPL; guardar o RESULTADO.json.
- [ ] Registrar aceite humano em Windows 10 e Windows 11 com conta de homologação e acervo sintético: edição, exportação, backup/restauração, atualização e desinstalação. Não usar acervo pessoal ou concessão administrativa para simular compra.
- [ ] TI validar Stripe LIVE e o fluxo autorizado de pagamento, webhook, acesso, download e cancelamento. TEST não comprova LIVE.
- [ ] Obter aprovação final da liberação com as evidências.

## Arquivos da release v1.10.1
- PecaStudio-Setup-1.10.1.exe (pacote FINAL assinado).
- PecaStudio-1.10.1-FONTES-PYTHON-E-AVISOS.zip.
- PecaStudio-1.10.1-FONTES-OCR.zip.
- PecaStudio-1.10.1-FONTES-VIDEO.zip.
- SOURCE-KIT-INDEX.json atualizado e hashes finais.
- Notas e instruções de uso revisadas.

Os componentes mantêm suas próprias licenças. Os três kits e o índice devem estar disponíveis junto do instalador correspondente; retenção temporária do Actions não é entrega durável das fontes. Não publicar bundle interno de assinatura, assets DO-NOT-PUBLISH, chaves, perfil, acervo, histórico privado ou a cópia inteira do repositório privado.

## Ativação do canal, somente depois da aprovação
1. Publicar a release versionada v1.10.1 com todos os arquivos finais; baixar anonimamente instalador e três kits e conferir hashes com o índice.
2. Preparar release-manifest.json com version 1.10.1, installer PecaStudio-Setup-1.10.1.exe, sha256 calculado do arquivo final assinado e installer_url versionado. Nunca usar valor fictício ou o hash de outro candidato.
3. Copiar o conteúdo revisado de README-candidato.md para a raiz, removendo o aviso de preparação e confirmando que nenhum link aponta a arquivo ausente. Atualizar manifesto e README juntos, passando o CI.
4. No catálogo Integralis, conferir a página /marketplace/peca-studio e o botão de download da versão certa. Preservar US$ 20/mês, produto peca_studio, slug, OAuth e campos existentes.
5. Conferir o manifesto servido, a versão baixada e o acesso autorizado; registrar URL, hash, data e responsável.

## Preservação da versão anterior
Manter a release 1.9.1 e seu instalador como histórico/recuperação. O código em codigo-fonte/ continua identificado como snapshot 1.9.1; esta preparação não o substitui por um snapshot novo nem altera sua licença.
