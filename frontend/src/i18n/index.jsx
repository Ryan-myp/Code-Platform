import { useState } from 'react'
import { locales, t as translate, getLanguages } from './locales'

const DEFAULT_LANG = 'zh-CN'
const LANG_STORAGE_KEY = 'app_lang'

export function useI18n() {
  const [lang, setLangState] = useState(() => {
    const saved = localStorage.getItem(LANG_STORAGE_KEY)
    return saved || DEFAULT_LANG
  })

  const setLang = (newLang) => {
    setLangState(newLang)
    localStorage.setItem(LANG_STORAGE_KEY, newLang)
  }

  const t = (key) => translate(key, lang)

  return { t, lang, setLang, languages: getLanguages() }
}

export function LanguageSwitcher({ className = '' }) {
  const { lang, setLang, languages } = useI18n()
  return (
    <select value={lang} onChange={(e) => setLang(e.target.value)}
      className={`px-2 py-1 text-sm border border-gray-200 rounded-lg ${className}`}>
      {languages.map((l) => (<option key={l.code} value={l.code}>{l.name}</option>))}
    </select>
  )
}
