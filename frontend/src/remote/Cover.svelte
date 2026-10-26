<script>
  import Icon from "../shared/Icon.svelte";

  // Capa da música (/media/<pasta>/cover.jpg) com fallback para nota musical.
  let { folder = "", size = 56, hasCover = true, radius = 8 } = $props();
  let failed = $state(false);

  const src = $derived(folder ? `/media/${encodeURIComponent(folder)}/cover.jpg` : "");
</script>

{#if src && hasCover && !failed}
  <img
    class="cover"
    {src}
    alt=""
    loading="lazy"
    width={size}
    height={size}
    style:border-radius="{radius}px"
    onerror={() => (failed = true)}
  />
{:else}
  <div
    class="cover fallback"
    style="width:{size}px;height:{size}px;border-radius:{radius}px"
  >
    <Icon name="note" size={Math.round(size * 0.45)} />
  </div>
{/if}

<style>
  .cover {
    flex: none;
    object-fit: cover;
    background: var(--panel-2);
  }
  .fallback {
    display: grid;
    place-items: center;
    color: var(--dim);
    border: 1px solid var(--line);
  }
</style>
