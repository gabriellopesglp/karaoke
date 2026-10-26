<script>
  // Fila de músicas: reordenar arrastando (HTML5 DnD, marcador .over), botão
  // "subir" em dispositivos de toque (via CSS), remover, limpar, clique toca
  // agora.
  import Icon from "../shared/Icon.svelte";
  import {
    byFolder,
    clearQueue,
    moveUpQueue,
    playFromQueue,
    queueView,
    removeFromQueue,
    reorderQueue,
  } from "./store.js";

  let dragF = null; // pasta sendo arrastada
  let overF = null; // pasta sob o cursor (marcador .over)

  function onDragStart(e, folder) {
    dragF = folder;
    e.dataTransfer.effectAllowed = "move";
  }
  function onDragEnd() {
    dragF = null;
    overF = null;
  }
  function onDragOver(e, folder) {
    if (dragF === null) return;
    e.preventDefault();
    overF = folder;
  }
  function onDrop(e, folder) {
    if (dragF === null) return;
    e.preventDefault();
    reorderQueue(dragF, folder);
    dragF = null;
    overF = null;
  }
</script>

<h3>
  Fila
  <span>
    <span>{$queueView.length || ""}</span>
    {#if $queueView.length}
      <button onclick={clearQueue}>limpar</button>
    {/if}
  </span>
</h3>
<div id="queue">
  {#if $queueView.length === 0}
    <div class="empty">Vazia. Use + na biblioteca para adicionar.</div>
  {:else}
    {#each $queueView as folder, k (folder)}
      {@const s = byFolder(folder) || { track: folder, artist: "" }}
      <div
        class="item row q"
        class:dragging={dragF === folder}
        class:over={overF === folder && dragF !== folder}
        draggable="true"
        role="button"
        tabindex="0"
        title="Arraste para reordenar · clique para tocar agora"
        onclick={() => playFromQueue(folder)}
        onkeydown={(e) => e.key === "Enter" && playFromQueue(folder)}
        ondragstart={(e) => onDragStart(e, folder)}
        ondragend={onDragEnd}
        ondragover={(e) => onDragOver(e, folder)}
        ondrop={(e) => onDrop(e, folder)}
      >
        <span class="qn">{k + 1}</span>
        <div class="txt">
          <div class="t">{s.track}</div>
          <div class="s">{s.artist}</div>
        </div>
        {#if k > 0}
          <button
            class="act up"
            title="Subir na fila"
            aria-label="Subir na fila"
            onclick={(e) => { e.stopPropagation(); moveUpQueue(folder); }}
          >
            <Icon name="up" size={16} />
          </button>
        {/if}
        <button
          class="act"
          title="Tirar da fila"
          aria-label="Tirar da fila"
          onclick={(e) => { e.stopPropagation(); removeFromQueue(folder); }}
        >
          <Icon name="x" size={16} />
        </button>
      </div>
    {/each}
  {/if}
</div>
