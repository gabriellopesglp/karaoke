<script>
  // Biblioteca: filtro local (todas as palavras, sem acentos; opção "Só
  // artista"), itens de job no topo (spinner/etapa/%/barra; erro dispensa no
  // clique), badges, ações no hover (split 3 faixas, deletar, +fila) e clique
  // para tocar.
  import Icon from "../shared/Icon.svelte";
  import { norm } from "./util.js";
  import {
    addToQueue,
    artistOnly,
    askSplit,
    clearFinishedJobs,
    currentSong,
    deleteSong,
    jobs,
    library,
    openSong,
    query,
    queue,
  } from "./store.js";

  const items = $derived.by(() => {
    const words = norm($query).split(/\s+/).filter(Boolean);
    return $library.filter((s) => {
      const hay = $artistOnly ? s.artist : `${s.artist} ${s.track}`;
      return words.every((w) => norm(hay).includes(w));
    });
  });

  // Músicas sendo processadas (ou com erro) aparecem no topo da biblioteca
  const pending = $derived($jobs.filter((j) => j.status !== "pronto"));

  function canSplit(s) {
    return (
      s.stems.length === 2 &&
      s.id &&
      !$jobs.some((j) => j.id === s.id && j.status !== "pronto" && j.status !== "erro")
    );
  }
</script>

<h3>Biblioteca <span>{$library.length || ""}</span></h3>
<div id="library">
  {#each pending as j (j.id)}
    {#if j.status === "erro"}
      <button class="item job err" title="Clique para dispensar" onclick={clearFinishedJobs}>
        <div class="t">{j.title}</div>
        <div class="s"><span class="badge err">erro</span>{j.error}</div>
      </button>
    {:else}
      {@const waiting = j.status === "na fila"}
      <div class="item job">
        <div class="t">{j.title}</div>
        <div class="s">
          {#if !waiting}<span class="spinner"></span>{/if}
          {waiting ? "na fila" : j.step || "iniciando…"}
          <span class="pct">{waiting ? "" : `${j.pct || 0}%`}</span>
        </div>
        <div class="bar"><i style="--w:{j.pct || 0}%"></i></div>
      </div>
    {/if}
  {/each}

  {#if items.length === 0}
    <div class="empty">
      {$library.length
        ? "Nada na biblioteca. Aperte Enter para buscar no YouTube."
        : "Biblioteca vazia. Digite uma música e aperte Enter."}
    </div>
  {:else}
    {#each items as s (s.folder)}
      {@const inQueue = $queue.includes(s.folder)}
      <div
        class="item row"
        class:active={$currentSong?.folder === s.folder}
        role="button"
        tabindex="0"
        title="Tocar agora"
        onclick={() => openSong(s)}
        onkeydown={(e) => e.key === "Enter" && openSong(s)}
      >
        <div class="txt">
          <div class="t">{s.track}</div>
          <div class="s">
            {s.artist}
            {#if s.stems.length > 2}<span class="badge">3 faixas</span>{/if}
          </div>
        </div>
        {#if canSplit(s)}
          <button
            class="act split"
            title="Separar os backing vocals da voz principal (3 faixas, mais lento)"
            aria-label="Separar backing vocals"
            onclick={(e) => { e.stopPropagation(); askSplit(s); }}
          >
            <Icon name="voices" size={16} />
          </button>
        {/if}
        <button
          class="act"
          title="Deletar música baixada"
          aria-label="Deletar música"
          onclick={(e) => { e.stopPropagation(); deleteSong(s); }}
        >
          <Icon name="trash" size={16} />
        </button>
        <button
          class="act"
          class:on={inQueue}
          title={inQueue ? "Já está na fila" : "Adicionar à fila"}
          aria-label="Adicionar à fila"
          onclick={(e) => { e.stopPropagation(); addToQueue(s.folder); }}
        >
          <Icon name={inQueue ? "check" : "plus"} size={16} />
        </button>
      </div>
    {/each}
  {/if}
</div>
