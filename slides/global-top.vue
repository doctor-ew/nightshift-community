<script setup>
import { computed } from 'vue'
import { useNav } from '@slidev/client'
const nav = useNav()
const sections = [
  {label:'Overview',start:1},{label:'Skills',start:4},
  {label:'Harness',start:6},{label:'Routing',start:8},
  {label:'Demonstration',start:13},{label:'Evidence',start:16},
  {label:'Architecture',start:21},{label:'Safety',start:23},{label:'Memory',start:25},
  {label:'Walkthrough',start:29},{label:'Discussion',start:42},{label:'Appendix',start:43},
]
const active = computed(() => sections.reduce((found,s,i) => nav.currentPage.value >= s.start ? i : found, 0))
</script>
<template>
  <nav class="module-nav" aria-label="Workshop sections">
    <div class="nav-caption">OUR PATH</div>
    <button v-for="(section,i) in sections" :key="section.start"
      :class="{past:i<active,current:i===active,future:i>active}"
      :aria-current="i===active ? 'step' : undefined" @click="nav.go(section.start)">
      <span class="nav-dot" aria-hidden="true">{{i<active ? '✓' : i===active ? '●' : '○'}}</span>
      <span>{{section.label}}</span>
    </button>
  </nav>
</template>
<style>
.module-nav{position:absolute;left:24px;top:140px;width:150px;font-family:'Source Code Pro',monospace;z-index:30;}
.module-nav .nav-caption{font-size:10px;letter-spacing:2px;color:#c2b5a7;margin-bottom:22px;}
.module-nav button{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:transparent;border:0;border-left:2px solid transparent;padding:13px 7px;font:inherit;font-size:13px;line-height:1.4;cursor:pointer;}
.module-nav button.past{color:#a8a39b;}.module-nav button.future{color:#747b80;}
.module-nav button.current{color:#f2b29a;background:#362821;border-left-color:#d97757;}
.module-nav button:hover,.module-nav button:focus-visible{color:#fff;outline:1px solid #d97757;}
.module-nav .nav-dot{flex-shrink:0;font-size:11px;}
</style>
