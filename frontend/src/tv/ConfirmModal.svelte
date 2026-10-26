<script>
  // Confirmação genérica (promise via confirmBox da store). Clique fora
  // cancela; Enter confirma; Esc cancela. O corpo é uma lista de parágrafos,
  // cada um com trechos {t, b} — nada de HTML injetado.
  import { confirm, closeConfirm } from "./store.js";

  let yesBtn = $state(null);
  $effect(() => {
    if ($confirm) yesBtn?.focus();
  });

  function onKeydown(e) {
    if (!$confirm) return;
    if (e.key === "Escape") {
      e.preventDefault();
      closeConfirm(false);
    }
    if (e.key === "Enter") {
      e.preventDefault();
      closeConfirm(true);
    }
  }
</script>

<svelte:document onkeydowncapture={onKeydown} />

{#if $confirm}
  <!-- svelte-ignore a11y_click_events_have_key_events (clique fora cancela) -->
  <div class="modal" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.target === e.currentTarget && closeConfirm(false)}>
    <div class="box">
      <h4>{$confirm.title}</h4>
      <p>
        {#each $confirm.body as para, pi}
          {#each para as run}{#if run.b}<b>{run.t}</b>{:else}{run.t}{/if}{/each}
          {#if pi < $confirm.body.length - 1}<br /><br />{/if}
        {/each}
      </p>
      <div class="btns">
        <button class="ghost" onclick={() => closeConfirm(false)}>Cancelar</button>
        <button class="primary" class:danger={$confirm.danger} bind:this={yesBtn} onclick={() => closeConfirm(true)}>
          {$confirm.ok}
        </button>
      </div>
    </div>
  </div>
{/if}
