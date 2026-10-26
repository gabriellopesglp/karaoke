<script>
  // Aba Buscar: biblioteca E YouTube juntos na mesma lista (o legado mostrava
  // um OU outro). Biblioteca filtra no cliente (já temos a lista); YouTube
  // vai ao servidor com debounce de 300 ms.
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import Cover from "./Cover.svelte";
  import Icon from "../shared/Icon.svelte";
  import { apiJson, postJson } from "../shared/api.js";
  import {
    enqueueSong,
    jobs,
    libById,
    library,
    queue,
    queueSet,
    refreshLibrary,
    toast,
  } from "./store.js";

  let q = $state("");
  let yt = $state(null); // null = ainda não buscou este termo
  let ytLoading = $state(false);
  let ytErr = $state(false);

  let timer = null;
  let seq = 0;

  // ids de vídeo cujo download ESTE aparelho pediu (para auto-enfileirar)
  let pending = $state(new Set());
  // ids/pastas já enfileiradas nesta tela (botão vira ✓)
  let added = $state(new Set());
  const handled = new Set(); // jobs já tratados (pronto/erro)

  const libResults = $derived(filterLib($library, q));
  const searching = $derived(!!q.trim());

  function filterLib(lib, query) {
    const s = query.trim().toLowerCase();
    if (!s) return lib.slice(0, 60);
    return lib
      .filter(
        (x) =>
          (x.track || "").toLowerCase().includes(s) ||
          (x.artist || "").toLowerCase().includes(s),
      )
      .slice(0, 30);
  }

  function onInput() {
    clearTimeout(timer);
    timer = setTimeout(runSearch, 300);
  }

  async function runSearch() {
    const query = q.trim();
    if (!query) {
      yt = null;
      ytLoading = false;
      ytErr = false;
      return;
    }
    const my = ++seq;
    ytLoading = true;
    ytErr = false;
    try {
      const res = await apiJson(`/api/search?q=${encodeURIComponent(query)}`);
      if (my === seq) yt = res;
    } catch (e) {
      if (my === seq) ytErr = true;
    } finally {
      if (my === seq) ytLoading = false;
    }
  }

  onDestroy(() => clearTimeout(timer));

  // -------------------------------------------------------- biblioteca

  function addFromLibrary(song) {
    added = new Set(added).add(song.folder);
    enqueueSong(song);
  }

  async function addDownloaded(videoId) {
    let song = get(libById).get(videoId);
    if (!song) {
      await refreshLibrary();
      song = get(libById).get(videoId);
    }
    if (song) {
      added = new Set(added).add(videoId);
      enqueueSong(song);
    } else {
      toast("música não encontrada na biblioteca", "err");
    }
  }

  // ----------------------------------------------------------- YouTube

  async function startJob(r) {
    handled.delete(r.id); // job anterior (erro/limpo) não pode bloquear o novo
    try {
      await postJson("/api/process", { id: r.id, title: r.title, mode: "2faixas" });
      pending = new Set(pending).add(r.id);
      checkJobs(get(jobs)); // o job pode já existir/estar pronto
    } catch (e) {
      toast(e.detail || "não foi possível baixar", "err");
    }
  }

  function retryJob(r) {
    handled.delete(r.id);
    startJob(r);
  }

  // Quando um job nosso termina, enfileira a música nova automaticamente
  function checkJobs(list) {
    for (const job of list) {
      if (!pending.has(job.id) || handled.has(job.id)) continue;
      if (job.status === "pronto") {
        handled.add(job.id);
        finishJob(job);
      } else if (job.status === "erro") {
        handled.add(job.id);
        toast(`erro ao baixar: ${job.title}`, "err");
      }
    }
  }

  $effect(() => checkJobs($jobs));

  async function finishJob(job) {
    await refreshLibrary();
    const lib = get(library);
    const song = lib.find((s) => s.id === job.id) || lib.find((s) => s.folder === job.folder);
    pending = new Set([...pending].filter((x) => x !== job.id));
    if (song) {
      added = new Set(added).add(job.id);
      enqueueSong(song);
    } else {
      toast("baixada, mas não apareceu na biblioteca", "err");
    }
  }

  const jobOf = $derived.by(() => {
    const map = new Map();
    for (const j of $jobs) map.set(j.id, j);
    return map;
  });
</script>

<div class="head">
  <div class="searchbar">
    <Icon name="search" size={20} />
    <input
      type="search"
      placeholder="Música ou artista…"
      autocomplete="off"
      autocapitalize="off"
      spellcheck="false"
      bind:value={q}
      oninput={onInput}
    />
    {#if q}
      <button class="clear" aria-label="Limpar busca" onclick={() => { q = ""; yt = null; }}>
        <Icon name="x" size={18} />
      </button>
    {/if}
  </div>
  <span class="qcount">{$queue.length} na fila</span>
</div>

{#if libResults.length}
  <h2 class="sect">{searching ? "Na biblioteca" : "Biblioteca"}</h2>
  <div class="results">
    {#each libResults as s (s.folder)}
      {@const inQueue = $queueSet.has(s.folder)}
      <article class="ritem">
        <Cover folder={s.folder} size={52} hasCover={s.cover} />
        <div class="meta">
          <div class="t">{s.track}</div>
          <div class="a">{s.artist}</div>
        </div>
        {#if inQueue}
          <span class="badge ok">na fila</span>
        {/if}
        <button
          class="add"
          class:done={added.has(s.folder) || inQueue}
          disabled={inQueue}
          aria-label="Adicionar à fila"
          onclick={() => addFromLibrary(s)}
        >
          {#if added.has(s.folder) || inQueue}
            <Icon name="check" size={20} />
          {:else}
            <Icon name="plus" size={18} /> fila
          {/if}
        </button>
      </article>
    {/each}
  </div>
{:else if !searching}
  <div class="hint">
    <Icon name="note" size={34} />
    <p>Sua biblioteca ainda está vazia.<br />Busque uma música para baixar e colocar na fila.</p>
  </div>
{/if}

{#if searching}
  <h2 class="sect">
    YouTube
    {#if ytLoading}<span class="spin"></span>{/if}
  </h2>
  {#if ytErr}
    <div class="emptyline">erro ao buscar no YouTube</div>
  {:else if yt && yt.length === 0 && !libResults.length}
    <div class="emptyline">nenhum resultado para “{q.trim()}”</div>
  {:else if yt && yt.length === 0}
    <div class="emptyline">nada no YouTube</div>
  {:else if yt}
    <div class="results">
      {#each yt as r (r.id)}
        {@const job = jobOf.get(r.id)}
        {@const running = job && (job.status === "na fila" || job.status === "processando")}
        {@const failed = job && job.status === "erro" && pending.has(r.id)}
        <article class="ritem yt" class:open={running || failed}>
          <div class="ytrow">
            <img
              class="thumb"
              src="https://i.ytimg.com/vi/{r.id}/mqdefault.jpg"
              alt=""
              loading="lazy"
              onerror={(e) => (e.currentTarget.style.visibility = "hidden")}
            />
            <div class="meta">
              <div class="t clamp2">{r.title}</div>
              <div class="a">{r.channel}</div>
              {#if r.downloaded}
                <span class="badge ok">baixada</span>
              {/if}
            </div>
            {#if added.has(r.id)}
              <button class="add done" disabled aria-label="Adicionada à fila">
                <Icon name="check" size={20} />
              </button>
            {:else if running}
              <span class="badge run">{job.pct}%</span>
            {:else if failed}
              <button class="btn danger retry" onclick={() => retryJob(r)}>
                <Icon name="refresh" size={16} /> tentar de novo
              </button>
            {:else if r.downloaded}
              <button class="add" onclick={() => addDownloaded(r.id)}>
                <Icon name="plus" size={18} /> fila
              </button>
            {:else}
              <button class="add ytadd" onclick={() => startJob(r)}>
                <Icon name="download" size={18} /> baixar
              </button>
            {/if}
          </div>
          {#if running}
            <div class="jobline">
              <div class="bar"><i style="--w:{job.pct}%"></i></div>
              <span class="step">{job.step || "na fila…"}</span>
            </div>
          {/if}
        </article>
      {/each}
    </div>
  {/if}
{/if}

<style>
  .head {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .searchbar {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--panel-2);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 0 12px;
    min-height: 48px;
    color: var(--dim);
  }
  .searchbar:focus-within {
    border-color: var(--accent);
  }
  .searchbar input {
    flex: 1;
    min-width: 0;
    background: none;
    border: 0;
    outline: none;
    color: var(--text);
    font-size: 16px; /* evita zoom automático no iOS */
    height: 46px;
  }
  .searchbar input::placeholder {
    color: var(--dim);
  }
  .searchbar input::-webkit-search-cancel-button {
    display: none;
  }
  .clear {
    background: none;
    border: 0;
    color: var(--dim);
    width: 40px;
    height: 44px;
    display: grid;
    place-items: center;
    margin-right: -8px;
  }
  .qcount {
    flex: none;
    font-size: 13px;
    font-weight: 700;
    color: var(--accent);
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
    padding: 7px 12px;
    border-radius: 18px;
    white-space: nowrap;
  }

  .hint {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 42px 20px;
    color: var(--dim);
    text-align: center;
    font-size: 15px;
    line-height: 1.5;
  }
  .hint p {
    margin: 0;
  }

  .sect {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 8px 2px 0;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--muted);
  }
  .results {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .ritem {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 8px 10px;
  }
  .ritem.yt {
    flex-direction: column;
    align-items: stretch;
    gap: 0;
  }
  .ritem.yt.open {
    padding-bottom: 12px;
  }
  .ytrow {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .thumb {
    width: 84px;
    height: 47px;
    object-fit: cover;
    border-radius: 6px;
    background: var(--panel-2);
    flex: none;
  }
  .meta {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 3px;
  }
  .t {
    font-size: 15px;
    font-weight: 600;
    line-height: 1.25;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }
  .t.clamp2 {
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .a {
    font-size: 13px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }
  .add {
    flex: none;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    min-height: 44px;
    padding: 0 14px;
    border: 0;
    border-radius: var(--radius);
    background: var(--accent);
    color: var(--accent-ink);
    font-size: 14px;
    font-weight: 700;
  }
  .add.done {
    background: color-mix(in srgb, var(--ok) 20%, transparent);
    color: var(--ok);
  }
  .add.ytadd {
    background: var(--panel-2);
    color: var(--text);
    border: 1px solid var(--line);
  }
  .retry {
    min-height: 44px;
    font-size: 13px;
    padding: 0 12px;
  }

  .jobline {
    margin-top: 10px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .jobline .bar {
    flex: 1;
  }
  .jobline .step {
    font-size: 12px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 55%;
  }
  .emptyline {
    color: var(--dim);
    font-size: 14px;
    text-align: center;
    padding: 16px;
  }
</style>
