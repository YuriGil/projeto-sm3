# Projeto SM3 — 07F — preview de revisão salva

O 07E confirmou `CARROSSEL_0004` na revisão 2 e registrou `EDIT_SESSION_STATUS=SAVED` em `04_CONTEUDOS`. O 07F produz um MP4 separado, a partir da receita dessa revisão e de cópias novas das mídias originais recuperadas do Google Drive.

## Instalar a partir da pasta real do projeto

Coloque `PROJETO_SM3_07F_v1_PACKAGE.zip` em `D:\MOLOTOV_SOCIAL_OS_RC7`, extraia ali e execute no PowerShell:

```powershell
cd D:\MOLOTOV_SOCIAL_OS_RC7
Expand-Archive -LiteralPath .\PROJETO_SM3_07F_v1_PACKAGE.zip -DestinationPath . -Force
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& .\PROJETO_SM3_07F_v1_PACKAGE\PROJETO_SM3_07F_INSTALL_WORKER_2_6_0.ps1
```

Se a pasta já estiver extraída, pule `Expand-Archive`. O instalador primeiro lê a receita real da revisão 2: caso ela use recursos visuais que o preview ainda não consegue representar, ele **interrompe antes de alterar ou recompilar o Worker** e apresenta o motivo. A compilação mostra saída contínua. No sucesso: `SM3_MEDIA_WORKER_2_6_0_INSTALL_PASS`.

## Executar e verificar

Importe `PROJETO_SM3_07F_EDIT_PREVIEWS_v1_VERIFIED_COMMIT.json` do pacote no n8n e execute. O fluxo lê `04_CONTEUDOS` e `03_MIDIAS`, baixa do Drive os arquivos originais, escreve no armazenamento compartilhado, compara os IDs exigidos pela receita, renderiza no Worker, consulta de novo o arquivo gerado e só então registra `RENDER_STATUS=EDIT_PREVIEW_READY` em `04_CONTEUDOS`. A leitura posterior da planilha deve retornar `SM3_07F_EDIT_PREVIEW_VERIFIED_COMMIT` com `committed_count=1`. Na segunda execução, deve retornar `SM3_07F_ALREADY_COMMITTED` sem modificar uma revisão.

Depois do workflow:

```powershell
& .\PROJETO_SM3_07F_v1_PACKAGE\PROJETO_SM3_07F_VERIFY_PREVIEWS.ps1
```

Resultado: `SM3_07F_EDIT_PREVIEW_PASS`. O teste consulta a revisão atual, baixa o vídeo pelo endpoint do Worker e compara SHA-256 e tamanho. Reabra o editor do carrossel: ele passará a carregar o preview **da revisão atual**, se a renderização tiver sido verificada. A tela informa quando ainda mostra o preview da variante base.

## Escopo real deste renderizador

Esta etapa renderiza timeline, ordem, enquadramento `CONTAIN` e tratamento de cor dentro da faixa validada. A intenção textual da edição é metadado e não muda pixels. Textos na imagem, identidade visual, áudio, transições animadas, zoom, `SMART_CROP`, `PAN_SCAN` e `FOCAL_TRACK` exigem renderizadores ou geometria da tattoo adicionais; solicitações que os ativam são recusadas com erro explícito. O vídeo resultante é **preview de revisão em baixa resolução**; não é render final nem publicação. Nenhum arquivo da variante original ou das revisões anteriores é modificado.

O workflow 07E fixa a versão 2.5.0 no health gate. Guarde sua execução validada como evidência; após atualizar para 2.6.0, execute o 07F para a próxima etapa.
