<script>
  // Barra lateral: brand, busca (filtro local + toggles), listas e rodapé
  // com os botões de compartilhar/controle/desligar.
  import Icon from "../shared/Icon.svelte";
  import QueueList from "./QueueList.svelte";
  import LibraryList from "./LibraryList.svelte";
  import SearchResults from "./SearchResults.svelte";
  import {
    artistOnly,
    backing,
    BACKING_BODY,
    confirmBox,
    isMac,
    query,
    searchYT,
    backToLibrary,
    settingsOpen,
    shareOpen,
    shutdown,
    ytOpen,
  } from "./store.js";

  let qEl;

  import { onMount } from "svelte";
  onMount(() => qEl?.focus()); // o autofocus do legado

  function onInput(e) {
    if (!e.currentTarget.value) ytOpen.set(false);
  }

  function onKeydown(e) {
    if (e.key === "Enter") searchYT();
    if (e.key === "Escape") {
      backToLibrary();
      qEl?.blur();
    }
  }

  // O toggle de backing vocals pede confirmação (é bem mais lento)
  async function onBackingClick(e) {
    e.preventDefault(); // reverte o toggle visual; o estado manda
    if (!$backing) {
      const ok = await confirmBox({
        title: "Separar backing vocals?",
        body: [...BACKING_BODY, [{ t: "Vale para as próximas músicas que você baixar do YouTube." }]],
        ok: "Ativar",
      });
      backing.set(ok);
    } else {
      backing.set(false); // desligar não precisa confirmar
    }
  }
</script>

<aside>
  <div class="brand">
    <Icon name="mic" size={20} /><span>Karaok<span class="accent">ê</span></span>
  </div>
  <div class="search">
    <input
      id="q"
      type="search"
      placeholder="Buscar música ou artista…"
      autocomplete="off"
      bind:this={qEl}
      bind:value={$query}
      oninput={onInput}
      onkeydown={onKeydown}
    />
    <div class="hint">
      <div class="hint-row"><kbd>Enter</kbd> busca no YouTube</div>
      <div class="toggles">
        <label
          class="switch"
          title="Filtrar a biblioteca apenas por artista (ignora o título da música)"
        >
          <input type="checkbox" bind:checked={$artistOnly} /><span class="knob"></span>
          <span class="lbl">Só artista</span>
        </label>
        <label
          class="switch"
          title="Gera 3 faixas: voz principal, backing vocals e instrumental. Leva uns 2 min por minuto de música."
        >
          <input type="checkbox" checked={$backing} onclick={onBackingClick} /><span class="knob"></span>
          <span class="lbl">Backing vocals <small>· lento</small></span>
        </label>
      </div>
    </div>
  </div>
  <div class="lists">
    <QueueList />
    <LibraryList />
    {#if $ytOpen}
      <SearchResults />
    {/if}
  </div>
  <div class="aside-foot">
    {#if isMac}
      <button
        class="icon-btn wide"
        title="Mostra um QR code para abrir o karaokê no celular ou tablet"
        onclick={() => shareOpen.set("app")}
      >
        <Icon name="phone" size={18} /> Abrir no celular ou tablet
      </button>
    {/if}
    <button
      class="icon-btn"
      title="Modo controle remoto: interface simplificada para celular (play, próxima, volume, tom)"
      onclick={() => shareOpen.set("remote")}
    >
      <Icon name="remote" size={18} /> Controle
    </button>
    <button
      class="icon-btn"
      title="Configurações"
      aria-label="Configurações"
      onclick={() => settingsOpen.set(true)}
    >
      <Icon name="settings" size={18} />
    </button>
    {#if isMac}
      <button
        class="icon-btn power"
        title="Desligar o karaokê"
        aria-label="Desligar o karaokê"
        onclick={shutdown}
      >
        <Icon name="power" size={18} />
      </button>
    {/if}
  </div>
</aside>
