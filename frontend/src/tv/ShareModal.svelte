<script>
  // Modal de compartilhar (QR code): dois modos — "app" (app completo) e
  // "remote" (controle remoto desta sessão). O SVG do QR vem do servidor e é
  // exibido via <img data:> (nunca HTML injetado). Botão copiar com fallback
  // e "trocar código" (reset=1) com confirmação.
  import { get } from "svelte/store";
  import Icon from "../shared/Icon.svelte";
  import { apiJson } from "../shared/api.js";
  import { confirmBox, sessionId, shareOpen, shareReset } from "./store.js";

  let { mode } = $props(); // "app" | "remote"

  let loading = $state(true);
  let error = $state("");
  let svgUrl = $state("");
  let address = $state("");
  let fullUrl = $state("");
  let copied = $state(false);

  const title = $derived(mode === "app" ? "Abrir no celular ou tablet" : "Controle remoto");
  const icon = $derived(mode === "app" ? "phone" : "remote");
  const text = $derived(
    mode === "app"
      ? "Escaneie com o celular ou tablet para abrir o app completo do karaokê neste aparelho."
      : "Escaneie com o celular para controlar esta sessão. Você controla play, volume das faixas, fundo, foco, pintar e adicionar músicas na fila.",
  );

  async function load(reset = false) {
    loading = true;
    error = "";
    copied = false;
    // skipAuthRedirect: erro aparece na caixa, sem chutar para a reconexão
    const sess = mode === "remote" ? `?session=${sessionId}` : "";
    const sep = mode === "remote" ? "&" : "?";
    const d = await apiJson(`/api/share${sess}${reset ? sep + "reset=1" : ""}`, {
      skipAuthRedirect: true,
    }).catch(() => ({ error: "Servidor indisponível." }));
    loading = false;
    if (d.error) {
      error = d.error;
      return;
    }
    svgUrl = `data:image/svg+xml;utf8,${encodeURIComponent(d.svg)}`;
    address = d.address;
    fullUrl = d.url;
  }
  // Montagem: respeita um "trocar código" pendente
  load(get(shareReset));
  shareReset.set(false);

  function close() {
    shareOpen.set(null);
  }

  function onKeydown(e) {
    if (e.key === "Escape") close();
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(fullUrl);
    } catch (e) {
      // fallback: seleciona e copia com execCommand
      const ta = document.createElement("textarea");
      ta.value = fullUrl;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } catch (e2) {}
      document.body.removeChild(ta);
    }
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }

  async function reset() {
    close();
    const ok = await confirmBox({
      title: "Trocar o código?",
      body: [
        [
          { t: "Os celulares e tablets que já abriram o karaokê " },
          { t: "perdem o acesso", b: true },
          { t: " e precisam escanear o novo código." },
        ],
      ],
      ok: "Trocar",
    });
    if (ok) {
      shareReset.set(true);
      shareOpen.set(mode);
    } else {
      shareOpen.set(mode); // cancelou: reabre o modal como estava
    }
  }
</script>

<svelte:document onkeydown={onKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events (clique fora fecha) -->
<div class="modal" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.target === e.currentTarget && close()}>
  <div class="box">
    <h4><Icon name={icon} size={18} /> {title}</h4>
    <p>
      {text} O aparelho precisa estar <b>na mesma rede Wi-Fi</b>.
    </p>
    <div class="qr">
      {#if loading}
        <div class="empty" style="color:#555;text-align:center;padding:40px 0">Gerando…</div>
      {:else if error}
        <div style="color:#333;padding:20px;text-align:center">{error}</div>
      {:else}
        <img src={svgUrl} alt="QR code" />
      {/if}
    </div>
    <div class="share-url-row">
      <div class="share-url">{error ? "" : address}</div>
      <button class="linkish share-copy" class:copied type="button" title="Copiar URL completa (com o código de acesso)" onclick={copy}>
        {copied ? "Copiado!" : "Copiar"}
      </button>
    </div>
    <div class="btns">
      <button
        class="linkish"
        title="Gera um código novo; aparelhos já conectados perdem o acesso"
        onclick={reset}
      >
        trocar código
      </button>
      <button class="primary" onclick={close}>Fechar</button>
    </div>
  </div>
</div>
