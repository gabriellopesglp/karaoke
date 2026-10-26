<script>
  // Toasts leves de feedback, empilhados acima da navegação inferior.
  import { toasts } from "./store.js";
</script>

<div class="toasts" role="status" aria-live="polite">
  {#each $toasts as t (t.id)}
    <div class="toast" class:err={t.kind === "err"}>{t.text}</div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed;
    left: 0;
    right: 0;
    bottom: calc(76px + env(safe-area-inset-bottom));
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    pointer-events: none;
    z-index: 40;
  }
  .toast {
    background: var(--panel-2);
    border: 1px solid color-mix(in srgb, var(--accent) 45%, transparent);
    color: var(--text);
    font-size: 14px;
    font-weight: 600;
    padding: 10px 18px;
    border-radius: 22px;
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.5);
    animation: pop 0.18s ease-out;
    max-width: 86vw;
  }
  .toast.err {
    border-color: color-mix(in srgb, var(--err) 55%, transparent);
  }
  @keyframes pop {
    from {
      transform: translateY(8px);
      opacity: 0;
    }
  }
</style>
