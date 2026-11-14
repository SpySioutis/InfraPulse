import { defineStore } from 'pinia'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    theme: (localStorage.getItem('infrapulse-theme') as 'dark' | 'light') || 'dark',
    pageSize: Number(localStorage.getItem('infrapulse-page-size')) || 25,
  }),
  actions: {
    setTheme(theme: 'dark' | 'light') {
      this.theme = theme
      localStorage.setItem('infrapulse-theme', theme)
      document.documentElement.setAttribute('data-theme', theme)
    },
    setPageSize(size: number) {
      this.pageSize = size
      localStorage.setItem('infrapulse-page-size', String(size))
    },
    applyTheme() {
      document.documentElement.setAttribute('data-theme', this.theme)
    },
  },
})
