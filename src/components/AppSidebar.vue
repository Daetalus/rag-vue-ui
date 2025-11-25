<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { MoreVertical, Pencil, Plus, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar'
import { useChatSessions } from '@/stores/chatSessions'
import { useAuthStore } from '@/stores/auth'
import { Skeleton } from '@/components/ui/skeleton'

const THEME_STORAGE_KEY = 'rag-ui-theme'

const router = useRouter()
const route = useRoute()

const isDarkMode = ref(false)
const sidebarError = ref<string | null>(null)

const { state } = useSidebar()
const isSidebarExpanded = computed(() => state.value === 'expanded')

const chatStore = useChatSessions()
const authStore = useAuthStore()
const orderedSessions = chatStore.orderedSessions
const isLoadingSessions = computed(() => chatStore.isLoadingSessions.value && !chatStore.sessionsLoaded.value)
const sessionsErrorMessage = computed(() => sidebarError.value ?? chatStore.sessionsError.value)

const activeSessionId = computed(() => route.params.sessionId as string | undefined)

function applyThemePreference(isDark: boolean) {
  if (typeof document === 'undefined') return

  const root = document.documentElement
  root.classList.toggle('dark', isDark)

  try {
    localStorage.setItem(THEME_STORAGE_KEY, isDark ? 'dark' : 'light')
  } catch {
    // Non-blocking: local storage may be unavailable.
  }
}

function initialiseTheme() {
  if (typeof window === 'undefined') return

  const storedTheme = (() => {
    try {
      return localStorage.getItem(THEME_STORAGE_KEY)
    } catch {
      return null
    }
  })()

  if (storedTheme === 'dark') {
    isDarkMode.value = true
  } else if (storedTheme === 'light') {
    isDarkMode.value = false
  } else {
    const prefersDark = window.matchMedia(
      '(prefers-color-scheme: dark)',
    ).matches
    isDarkMode.value = prefersDark
  }

  applyThemePreference(isDarkMode.value)
}

function handleCreateNewChat() {
  sidebarError.value = null
  router.push({ name: 'landing' })
}

async function renameSession(sessionId: string) {
  if (typeof window === 'undefined') return

  const session = chatStore.getSessionById(sessionId)
  if (!session) return

  const nextTitle = window.prompt('Rename chat', session.title) ?? ''
  const trimmed = nextTitle.trim()

  if (!trimmed || trimmed === session.title) return

  sidebarError.value = null

  try {
    await chatStore.renameSession(sessionId, trimmed)
  } catch (error) {
    sidebarError.value =
      error instanceof Error ? error.message : 'Unable to rename session.'
  }
}

async function deleteSession(sessionId: string) {
  sidebarError.value = null

  try {
    await chatStore.deleteSession(sessionId)
    if (activeSessionId.value === sessionId) {
      router.push({ name: 'landing' })
    }
  } catch (error) {
    sidebarError.value =
      error instanceof Error ? error.message : 'Unable to delete session.'
  }
}

function handleLogout() {
  sidebarError.value = null
  authStore.logout()
  router.push({ name: 'landing' })
}

onMounted(() => {
  initialiseTheme()

  if (!chatStore.sessionsLoaded.value && !chatStore.isLoadingSessions.value) {
    void chatStore.fetchSessions().catch((error) => {
      sidebarError.value =
        error instanceof Error ? error.message : 'Unable to load sessions.'
    })
  }
})

watch(isDarkMode, (value) => {
  applyThemePreference(value)
})
</script>

<template>
  <Sidebar>
    <SidebarHeader>
      <div class="flex flex-col gap-4 text-sidebar-foreground/80">
        <div class="flex items-center justify-between gap-3 pt-3">
          <h2 class="text-lg font-normal leading-tight text-sidebar-foreground">
            Nexedi RAG
          </h2>
          <SidebarTrigger
            v-if="isSidebarExpanded"
            class="h-10 w-10 text-sidebar-foreground/70 hover:text-sidebar-foreground focus-visible:text-sidebar-foreground [&>svg]:size-5"
          />
        </div>
        <SidebarMenu class="gap-2">
          <SidebarMenuItem>
            <SidebarMenuButton
              class="w-full justify-start gap-3 rounded-lg px-3 py-2 text-base font-medium text-sidebar-foreground transition-all hover:bg-sidebar-accent focus-visible:bg-sidebar-accent"
              as="button"
              type="button"
              @click="handleCreateNewChat"
            >
              <Plus class="size-4 shrink-0 text-primary" />
              <span>
                New chat
              </span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </div>
    </SidebarHeader>

    <SidebarContent>
      <SidebarGroup class="gap-4">
        <SidebarGroupLabel class="text-sm font-normal leading-tight tracking-tight text-sidebar-foreground">
          Recent chats
        </SidebarGroupLabel>
        <SidebarGroupContent class="space-y-3">
          <div
            v-if="sessionsErrorMessage"
            class="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
          >
            {{ sessionsErrorMessage }}
          </div>
          <div
            v-else-if="isLoadingSessions"
            class="space-y-2"
          >
            <Skeleton class="h-10 w-full rounded-lg" />
            <Skeleton class="h-10 w-full rounded-lg" />
            <Skeleton class="h-10 w-full rounded-lg" />
          </div>
          <SidebarMenu v-else-if="orderedSessions.length" class="gap-3">
            <SidebarMenuItem
              v-for="session in orderedSessions"
              :key="session.id"
            >
              <div class="relative">
                <RouterLink
                  :to="{ name: 'chat', params: { sessionId: session.id } }"
                  custom
                  v-slot="{ navigate, href, isActive: linkActive }"
                >
                  <SidebarMenuButton
                    :href="href"
                    as="a"
                    :is-active="linkActive"
                    class="w-full items-center justify-between gap-3 rounded-lg px-3 py-2 pr-12 text-base font-medium transition-all hover:bg-sidebar-accent focus-visible:bg-sidebar-accent"
                    :class="(linkActive ? 'bg-sidebar-accent text-sidebar-accent-foreground' : 'text-sidebar-foreground')"
                    @click="($event) => { sidebarError = null; navigate($event); }"
                  >
                    <span class="truncate">
                      {{ session.title }}
                    </span>
                  </SidebarMenuButton>
                </RouterLink>
                <DropdownMenu>
                  <DropdownMenuTrigger as-child>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      class="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus-visible:text-foreground"
                      @click.stop
                    >
                      <MoreVertical class="size-4" />
                      <span class="sr-only">
                        Open session actions
                      </span>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    class="w-44"
                    align="end"
                    :side-offset="6"
                  >
                    <DropdownMenuItem @select="renameSession(session.id)">
                      <Pencil class="mr-2 size-4" />
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      variant="destructive"
                      @select="deleteSession(session.id)"
                    >
                      <Trash2 class="mr-2 size-4" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </SidebarMenuItem>
          </SidebarMenu>
          <p
            v-else
            class="px-2 py-4 text-sm text-muted-foreground/80"
          >
            Your upcoming chats will appear here.
          </p>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>

    <SidebarFooter>
      <div class="flex flex-col gap-3 rounded-lg bg-sidebar-accent/40 px-3 py-3">
        <div class="flex items-center justify-between gap-3">
          <div class="flex flex-col gap-1">
            <span class="text-sm font-medium text-sidebar-foreground">
              Theme
            </span>
            <span class="text-xs text-muted-foreground/80">
              Toggle light/dark
            </span>
          </div>
          <Switch v-model:model-value="isDarkMode" />
        </div>
        <Button
          variant="ghost"
          size="sm"
          class="justify-start px-2 text-xs font-medium text-muted-foreground hover:text-destructive"
          @click="handleLogout"
        >
          Sign out
        </Button>
      </div>
    </SidebarFooter>
  </Sidebar>
</template>
