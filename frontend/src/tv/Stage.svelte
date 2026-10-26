<script>
  // Palco: header (capa, título/artista, próxima, tela cheia), stage (fundo
  // com capa borrada animada, letra, nota de sincronização, mensagem) e
  // footer (transporte, mixer, ferramentas).
  import Icon from "../shared/Icon.svelte";
  import Lyrics from "./Lyrics.svelte";
  import Transport from "./Transport.svelte";
  import Mixer from "./Mixer.svelte";
  import ToolsBar from "./ToolsBar.svelte";
  import { byFolder, cover, currentSong, drawer, immersive, msg, queueView, syncNote } from "./store.js";

  let { onToggleImmersive } = $props();

  const next = $derived($queueView.length ? byFolder($queueView[0]) : null);
</script>

<main>
  <div
    class="stage-bg"
    class:show={!!$cover}
    style:background-image={$cover ? `url("${$cover}")` : "none"}
  ></div>
  <header>
    <button
      class="icon-btn menu-btn"
      title="Músicas"
      aria-label="Músicas"
      onclick={() => drawer.update((v) => !v)}
    >
      <Icon name="menu" size={18} /><span class="btn-txt">Músicas</span>
    </button>
    <div class="now">
      {#if $cover}
        <img class="h-cover" src={$cover} alt="" />
      {/if}
      <div class="h-meta">
        <div class="track">{$currentSong ? $currentSong.track : "Escolha uma música"}</div>
        <div class="artist">{$currentSong ? $currentSong.artist || " " : " "}</div>
      </div>
    </div>
    <div class="side">
      <div class="upnext">
        {#if next}
          Próxima: <b>{next.track}</b> · {next.artist}
        {/if}
      </div>
      <button
        class="icon-btn"
        title="Letra em tela cheia (F)"
        aria-label="Tela cheia"
        onclick={onToggleImmersive}
      >
        <span><Icon name={$immersive ? "shrink" : "expand"} size={18} /></span>
        <span class="btn-txt">{$immersive ? "Sair" : "Tela cheia"}</span>
      </button>
    </div>
  </header>
  <div class="stage">
    <Lyrics />
    {#if $syncNote}
      <div class="note">{$syncNote}</div>
    {/if}
    {#if $msg}
      <div
        class="msg"
        style:align-items={$msg.small ? "end" : "center"}
        style:padding-bottom={$msg.small ? "40px" : "24px"}
      >
        <div><b>{$msg.title}</b>{$msg.text}</div>
      </div>
    {/if}
  </div>
  <footer>
    <Transport {next} />
    <Mixer />
    <ToolsBar />
  </footer>
</main>
