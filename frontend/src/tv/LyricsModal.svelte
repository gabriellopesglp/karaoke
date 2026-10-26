<script>
  // Modal "Escolher": abas Letra (versões do LRCLIB, com duração ±diff,
  // badges sincronizada/atual e preview itálico) e Capa (grade iTunes com
  // badge match). Escolha de letra zera o offset e recarrega; capa aplica
  // com cache-bust.
  import Icon from "../shared/Icon.svelte";
  import { apiJson, postJson } from "../shared/api.js";
  import { fmtTime } from "../shared/fmt.js";
  import { applyCoverBg, currentSong, loadLyrics, lyricsOpen, lyrOffset, showMsg } from "./store.js";
  import { store } from "./util.js";

  let tab = $state("lyrics");
  let lq = $state("");
  let cq = $state("");
  let lopts = $state(null); // null = carregando
  let copts = $state(null);
  let duration = $state(0);
  let chosenCover = $state(""); // url aplicada (borda .current)

  const song = $currentSong;
  let searchId = 0;
  let coverId = 0;

  function close() {
    lyricsOpen.set(false);
  }

  async function searchLyrics(q = "") {
    const my = ++searchId;
    lopts = null;
    const d = await apiJson(
      `/api/lyrics/options?folder=${encodeURIComponent(song.folder)}&q=${encodeURIComponent(q)}`,
    ).catch(() => ({ options: [] }));
    if (my !== searchId) return;
    duration = d.duration || 0;
    lopts = d.options || [];
  }

  async function searchCovers(q = "") {
    const my = ++coverId;
    copts = null;
    const d = await apiJson(
      `/api/cover/options?folder=${encodeURIComponent(song.folder)}&q=${encodeURIComponent(q)}`,
    ).catch(() => ({ options: [] }));
    if (my !== coverId) return;
    copts = d.options || [];
  }

  // Abertura: busca inicial com "artista música"
  lq = `${song?.artist || ""} ${song?.track || ""}`.trim();
  searchLyrics();

  function showTab(t) {
    tab = t;
    if (t === "cover" && copts === null) {
      cq = `${song?.artist || ""} ${song?.track || ""}`.trim();
      searchCovers();
    }
  }

  function diffTxt(o) {
    const diff = duration && o.duration ? Math.round(o.duration - duration) : null;
    if (diff === null) return "";
    if (Math.abs(diff) <= 2) return "mesma duração";
    return `${diff > 0 ? "+" : "−"}${Math.abs(diff)} s`;
  }

  async function chooseLyrics(o) {
    close();
    if (o.current) return;
    showMsg(null);
    await postJson("/api/lyrics/choose", { folder: song.folder, id: o.id }).catch(() => {});
    if ($currentSong === song) {
      store.set(`offset:${song.folder}`, 0);
      lyrOffset.set(0);
      loadLyrics(song);
    }
  }

  async function chooseCover(o) {
    chosenCover = o.url;
    close();
    showMsg(null);
    await postJson("/api/cover", { folder: song.folder, url: o.url }).catch(() => {});
    if ($currentSong === song) applyCoverBg(song.folder, true); // cache-bust
  }

  function onKeydown(e) {
    if (e.key === "Escape") close();
  }
</script>

<svelte:document onkeydown={onKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events (clique fora fecha) -->
<div class="modal" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.target === e.currentTarget && close()}>
  <div class="box wide">
    <div class="pick-tabs">
      <button class="pick-tab" class:active={tab === "lyrics"} type="button" onclick={() => showTab("lyrics")}>
        <Icon name="lyrics" size={16} /> Letra
      </button>
      <button class="pick-tab" class:active={tab === "cover"} type="button" onclick={() => showTab("cover")}>
        <Icon name="disc" size={16} /> Capa
      </button>
    </div>

    {#if tab === "lyrics"}
      <div class="pick-pane">
        <h4><Icon name="lyrics" size={18} /> Escolher a letra</h4>
        <form class="lsearch" onsubmit={(e) => { e.preventDefault(); searchLyrics(lq); }}>
          <Icon name="search" size={18} />
          <input type="search" placeholder="Artista e música" autocomplete="off" bind:value={lq} />
        </form>
        <div class="lopts">
          {#if lopts === null}
            <div class="empty" style="display:flex;gap:8px;align-items:center;padding:12px">
              <span class="spinner"></span>Buscando letras…
            </div>
          {:else if lopts.length === 0}
            <div class="empty" style="padding:12px">Nenhuma letra encontrada. Tente outros termos na busca acima.</div>
          {:else}
            {#each lopts as o (o.id)}
              <button class="lopt" class:current={o.current} onclick={() => chooseLyrics(o)}>
                <div class="t">
                  {#if o.current}<Icon name="check" size={16} />{/if}
                  {o.track} <span style="color:var(--muted);font-weight:400">· {o.artist}</span>
                </div>
                <div class="meta">
                  {#if o.album}<span>{o.album}</span><span>·</span>{/if}
                  <span>{fmtTime(o.duration)}{#if diffTxt(o)} ({diffTxt(o)}){/if}</span>
                  <span>·</span>
                  <span class="badge" class:ok={o.synced}>{o.synced ? "sincronizada" : "sem sincronia"}</span>
                  {#if o.current}<span class="badge run">atual</span>{/if}
                </div>
                {#if o.preview?.length}
                  <div class="prev">
                    {#each o.preview as line}
                      <div>{line}</div>
                    {/each}
                  </div>
                {/if}
              </button>
            {/each}
          {/if}
        </div>
      </div>
    {:else}
      <div class="pick-pane">
        <h4><Icon name="disc" size={18} /> Escolher a capa</h4>
        <form class="lsearch" onsubmit={(e) => { e.preventDefault(); searchCovers(cq); }}>
          <Icon name="search" size={18} />
          <input type="search" placeholder="Artista e música" autocomplete="off" bind:value={cq} />
        </form>
        <div class="copts">
          {#if copts === null}
            <div class="empty" style="display:flex;gap:8px;align-items:center;padding:12px;grid-column:1/-1">
              <span class="spinner"></span>Buscando capas…
            </div>
          {:else if copts.length === 0}
            <div class="empty" style="padding:12px;grid-column:1/-1">Nenhuma capa encontrada. Tente outros termos na busca acima.</div>
          {:else}
            {#each copts as o (o.url)}
              <button
                class="copt"
                class:current={chosenCover === o.url}
                title="{o.artist} — {o.track}{o.album ? ` · ${o.album}` : ''}"
                onclick={() => chooseCover(o)}
              >
                {#if o.match}<span class="badge ok">match</span>{/if}
                <img class="art" src={o.thumb} alt="" loading="lazy" />
                <div class="meta">
                  <div class="t">{o.track}</div>
                  <div class="s">{o.artist}</div>
                </div>
              </button>
            {/each}
          {/if}
        </div>
      </div>
    {/if}

    <div class="btns">
      <button class="ghost" onclick={close}>Fechar</button>
    </div>
  </div>
</div>
