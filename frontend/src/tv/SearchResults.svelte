<script>
  // Resultados do YouTube (Enter na busca): badges baixada/status do job;
  // clique toca se baixada, senão manda processar no modo escolhido.
  import { clickYt, jobs, query, ytLoading, ytResults } from "./store.js";

  function jobOf(id) {
    return $jobs.find((j) => j.id === id);
  }
</script>

<div id="ytBox">
  <h3>YouTube</h3>
  <div id="yt">
    {#if $ytLoading}
      <div class="empty" style="display:flex;gap:8px;align-items:center">
        <span class="spinner"></span>Buscando “{$query.trim()}”…
      </div>
    {:else if $ytResults.length === 0}
      <div class="empty">Nenhum resultado.</div>
    {:else}
      {#each $ytResults as r (r.id)}
        {@const job = jobOf(r.id)}
        <button class="item" title={r.downloaded ? "Tocar" : "Baixar e separar"} onclick={() => clickYt(r)}>
          <div class="t">{r.title}</div>
          <div class="s">
            {#if r.downloaded}
              <span class="badge ok">baixada</span>
            {:else if job && job.status !== "erro"}
              <span class="badge run">{job.status}</span>
            {/if}
            {r.channel}
          </div>
        </button>
      {/each}
    {/if}
  </div>
</div>
