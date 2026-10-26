<script>
  // Casca do controle remoto: abas, navegação inferior, conexão e a tela
  // de "TV não encontrada".
  import { onMount } from "svelte";
  import Icon from "../shared/Icon.svelte";
  import Toasts from "./Toasts.svelte";
  import QueueTab from "./QueueTab.svelte";
  import SearchTab from "./SearchTab.svelte";
  import ControlTab from "./ControlTab.svelte";
  import { conn, initRemote, queue, refreshSessionState, sessionFound } from "./store.js";

  let tab = $state("fila");

  onMount(initRemote);

  const tabs = [
    { id: "fila", label: "Fila", icon: "queue" },
    { id: "buscar", label: "Buscar", icon: "search" },
    { id: "controle", label: "Controle", icon: "tune" },
  ];
</script>

{#if !$sessionFound}
  <div class="notfound">
    <Icon name="mic" size={52} />
    <h1>TV não encontrada</h1>
    <p>
      Escaneie o QR code exibido na TV para conectar este aparelho.
      {#if $conn === "offline"}Sem contato com o servidor — verifique o Wi-Fi.{/if}
    </p>
    <button class="btn accent" onclick={() => refreshSessionState()}>
      <Icon name="refresh" size={18} /> Tentar de novo
    </button>
  </div>
{:else}
  {#if $conn === "offline"}
    <div class="connpill">reconectando…</div>
  {/if}

  <main class="page">
    {#if tab === "fila"}
      <QueueTab goSearch={() => (tab = "buscar")} />
    {:else if tab === "buscar"}
      <SearchTab />
    {:else}
      <ControlTab />
    {/if}
  </main>

  <nav class="bottomnav" aria-label="Abas">
    {#each tabs as t (t.id)}
      <button
        class="navbtn"
        class:active={tab === t.id}
        aria-current={tab === t.id ? "page" : undefined}
        onclick={() => (tab = t.id)}
      >
        <span class="nic">
          <Icon name={t.icon} size={24} />
          {#if t.id === "fila" && $queue.length}
            <span class="nbadge">{$queue.length}</span>
          {/if}
        </span>
        <span class="nlbl">{t.label}</span>
      </button>
    {/each}
  </nav>
{/if}

<Toasts />

<style>
  .page {
    max-width: 560px;
    margin: 0 auto;
    padding: 14px 14px calc(96px + env(safe-area-inset-bottom));
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  /* pílula de conexão: fixa, não desloca o layout */
  .connpill {
    position: fixed;
    top: calc(8px + env(safe-area-inset-top));
    left: 50%;
    transform: translateX(-50%);
    z-index: 30;
    background: var(--panel-2);
    border: 1px solid color-mix(in srgb, var(--err) 50%, transparent);
    color: var(--muted);
    font-size: 13px;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 18px;
    box-shadow: 0 3px 12px rgba(0, 0, 0, 0.4);
  }

  .bottomnav {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    display: flex;
    background: color-mix(in srgb, var(--panel) 88%, transparent);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-top: 1px solid var(--line);
    padding-bottom: env(safe-area-inset-bottom);
  }
  .navbtn {
    flex: 1;
    min-height: 60px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    background: none;
    border: 0;
    color: var(--dim);
    font-size: 12px;
    font-weight: 600;
    padding: 6px 0;
  }
  .navbtn.active {
    color: var(--accent);
  }
  .nic {
    position: relative;
    display: inline-flex;
  }
  .nbadge {
    position: absolute;
    top: -6px;
    right: -13px;
    background: var(--accent);
    color: var(--accent-ink);
    font-size: 11px;
    font-weight: 800;
    min-width: 17px;
    height: 17px;
    border-radius: 9px;
    display: grid;
    place-items: center;
    padding: 0 4px;
  }

  .notfound {
    min-height: 100vh;
    max-width: 560px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    text-align: center;
    padding: 32px 28px;
    color: var(--muted);
  }
  .notfound :global(.ico) {
    color: var(--accent);
  }
  .notfound h1 {
    margin: 0;
    font-size: 22px;
    color: var(--text);
  }
  .notfound p {
    margin: 0 0 8px;
    font-size: 15px;
    line-height: 1.5;
  }
</style>
