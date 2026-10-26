<script>
  // Aba Fila: o que está tocando + a fila compartilhada (reordenar/remover).
  import Cover from "./Cover.svelte";
  import Icon from "../shared/Icon.svelte";
  import { fmtTime } from "../shared/fmt.js";
  import { cmd, libByFolder, mine, moveAt, position, queue, removeAt, view } from "./store.js";

  let { goSearch } = $props();

  const song = $derived($view?.song || null);
  const playing = $derived(!!$view?.playing);
  const pct = $derived($position.dur ? Math.min(100, ($position.cur / $position.dur) * 100) : 0);
</script>

<section class="card now">
  {#if song}
    <Cover folder={song.folder} size={92} radius={10} hasCover={true} />
    <div class="nowinfo">
      <div class="t">{song.track}</div>
      <div class="a">{song.artist}</div>
      <div class="prog">
        <span class="time">{fmtTime($position.cur)}</span>
        <div class="bar"><i style="--w:{pct}%"></i></div>
        <span class="time">{fmtTime($position.dur)}</span>
      </div>
      <div class="row">
        <button class="tbtn" aria-label="Reiniciar a música" onclick={() => cmd({ type: "prev" }, playing ? { cur: 0 } : null)}>
          <Icon name="prev" size={20} />
        </button>
        <button class="tbtn play" aria-label={playing ? "Pausar" : "Tocar"} onclick={() => cmd({ type: "play" }, { playing: !playing })}>
          <Icon name={playing ? "pause" : "play"} size={22} />
        </button>
        <button class="tbtn" aria-label="Próxima da fila" onclick={() => cmd({ type: "next" })}>
          <Icon name="next" size={20} />
        </button>
      </div>
    </div>
  {:else}
    <div class="idle">
      <Icon name="note" size={30} />
      <p>Nenhuma música tocando.<br />Coloque uma na fila para começar.</p>
    </div>
  {/if}
</section>

{#if $queue.length === 0}
  <section class="empty">
    <Icon name="queue" size={40} />
    <p>A fila está vazia.</p>
    <button class="btn accent" onclick={goSearch}>
      <Icon name="search" size={18} /> Buscar uma música
    </button>
  </section>
{:else}
  <section class="qlist" aria-label="Fila de músicas">
    {#each $queue as folder, i (i + ":" + folder)}
      {@const s = $libByFolder.get(folder)}
      <article class="qitem" class:own={$mine.has(folder)}>
        <span class="pos">{i + 1}</span>
        <Cover folder={folder} size={48} hasCover={s ? s.cover : true} />
        <div class="meta">
          <div class="t">{s ? s.track : folder}</div>
          <div class="a">{s ? s.artist : ""}</div>
          {#if $mine.has(folder)}
            <span class="ownlbl">você adicionou</span>
          {/if}
        </div>
        <div class="acts">
          <button class="mini" aria-label="Mover para cima" disabled={i === 0} onclick={() => moveAt(i, -1)}>
            <Icon name="up" size={20} />
          </button>
          <button class="mini" aria-label="Mover para baixo" disabled={i === $queue.length - 1} onclick={() => moveAt(i, 1)}>
            <Icon name="down" size={20} />
          </button>
          <button class="mini del" aria-label="Remover da fila" onclick={() => removeAt(i)}>
            <Icon name="x" size={18} />
          </button>
        </div>
      </article>
    {/each}
  </section>
{/if}

<style>
  .card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: var(--radius);
  }
  .now {
    display: flex;
    gap: 14px;
    padding: 14px;
  }
  .nowinfo {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 7px;
  }
  .t {
    font-size: 17px;
    font-weight: 700;
    line-height: 1.25;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .a {
    font-size: 14px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .prog {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .prog .bar {
    flex: 1;
  }
  .time {
    font-size: 12px;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
    min-width: 34px;
  }
  .time:last-child {
    text-align: right;
  }
  .row {
    display: flex;
    gap: 10px;
    margin-top: 2px;
  }
  .tbtn {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: 1px solid var(--line);
    background: var(--panel-2);
    color: var(--text);
    display: grid;
    place-items: center;
  }
  .tbtn.play {
    background: var(--accent);
    color: var(--accent-ink);
    border-color: var(--accent);
  }
  .idle {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 18px 14px;
    color: var(--dim);
    font-size: 14px;
    line-height: 1.4;
  }
  .idle p {
    margin: 0;
  }

  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 34px 16px;
    color: var(--dim);
    text-align: center;
  }
  .empty p {
    margin: 0 0 4px;
    font-size: 15px;
  }

  .qlist {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .qitem {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 8px 10px;
  }
  .qitem.own {
    box-shadow: inset 3px 0 0 var(--accent);
  }
  .pos {
    width: 20px;
    flex: none;
    text-align: center;
    font-size: 14px;
    font-weight: 700;
    color: var(--accent);
    font-variant-numeric: tabular-nums;
  }
  .meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .meta .t {
    font-size: 15px;
    -webkit-line-clamp: 1;
  }
  .meta .a {
    font-size: 13px;
  }
  .ownlbl {
    font-size: 12px;
    font-weight: 700;
    color: var(--accent);
  }
  .acts {
    display: flex;
    align-items: center;
    gap: 2px;
    flex: none;
  }
  .mini {
    width: 40px;
    height: 44px;
    display: grid;
    place-items: center;
    background: none;
    border: 0;
    color: var(--muted);
    border-radius: 8px;
  }
  .mini:active {
    background: var(--panel-2);
    color: var(--text);
  }
  .mini.del {
    color: var(--dim);
  }
  .mini.del:active {
    color: var(--err);
  }
</style>
