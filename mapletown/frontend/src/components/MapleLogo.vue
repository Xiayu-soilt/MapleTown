<script setup>
defineProps({
  size: { type: Number, default: 40 },
});
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 64 64"
    xmlns="http://www.w3.org/2000/svg"
    class="maple-logo"
    aria-label="枫叶镇 Logo"
  >
    <defs>
      <linearGradient id="maple-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#E8402A" />
        <stop offset="55%" stop-color="#F0703A" />
        <stop offset="100%" stop-color="#F5A623" />
      </linearGradient>
    </defs>
    <g transform="rotate(15 32 32)">
      <path
        fill="url(#maple-gradient)"
        d="M32 4c2.2 3.4 4.9 6 8.3 7.8-.9 2.3-1.2 4.5-.9 6.7 3.4-2.6 7.1-3.7 11.2-3.4-.6 3.8.2 7.2 2.4 10.3-3.5 1.7-6 4.2-7.4 7.6 3.8.4 7 2 9.6 4.9-3 2.7-4.7 5.7-5.1 9.1-3.6-.7-6.9-.2-9.8 1.6 2 3.2 2.7 6.6 2 10.3-3.7-1.3-7.2-1.1-10.4.6L32 60l-1.6-6.5c-3.2-1.7-6.7-1.9-10.4-.6-.7-3.7 0-7.1 2-10.3-2.9-1.8-6.2-2.3-9.8-1.6-.4-3.4-2.1-6.4-5.1-9.1 2.6-2.9 5.8-4.5 9.6-4.9-1.4-3.4-3.9-5.9-7.4-7.6 2.2-3.1 3-6.5 2.4-10.3 4.1-.3 7.8.8 11.2 3.4.3-2.2 0-4.4-.9-6.7C27.1 10 29.8 7.4 32 4z"
      />
    </g>
  </svg>
</template>

<style scoped>
.maple-logo {
  filter: drop-shadow(0 2px 4px rgba(232, 64, 42, 0.35));
}
</style>
