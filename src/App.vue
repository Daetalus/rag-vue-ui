<script setup lang="ts">
import { computed, defineComponent, h, watch } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import AuthScreen from '@/components/auth/AuthScreen.vue'
import { useAuthStore } from '@/stores/auth'
import { useChatSessions } from '@/stores/chatSessions'
import { SidebarProvider, SidebarTrigger, useSidebar } from '@/components/ui/sidebar'

const SidebarCollapsedTrigger = defineComponent({
  name: 'SidebarCollapsedTrigger',
  setup(_, { attrs }) {
    const { state } = useSidebar()
    return () => (state.value === 'collapsed' ? h(SidebarTrigger, attrs) : null)
  },
})

const authStore = useAuthStore()
const chatStore = useChatSessions()

const isAuthenticated = computed(() => authStore.isAuthenticated.value)

watch(
  () => authStore.isAuthenticated.value,
  (authed) => {
    if (authed) {
      if (!chatStore.sessionsLoaded.value && !chatStore.isLoadingSessions.value) {
        void chatStore.fetchSessions().catch(() => {
          // Errors surfaced in sidebar via store state.
        })
      }
    } else {
      chatStore.resetSessions()
    }
  },
  { immediate: true },
)
</script>

<template>
  <AuthScreen v-if="!isAuthenticated" />
  <SidebarProvider v-else>
    <AppSidebar />
    <main class="relative flex min-h-0 flex-1 flex-col overflow-hidden">
      <SidebarCollapsedTrigger class="absolute left-4 top-4 z-10 hidden md:inline-flex" />
      <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
        <RouterView />
      </div>
    </main>
  </SidebarProvider>
</template>

<style scoped>
</style>
