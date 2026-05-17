import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import dayjs from 'dayjs'
import 'dayjs/locale/en'
import 'dayjs/locale/fr'

import enTranslations from './locales/en.json'
import frTranslations from './locales/fr.json'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        translation: enTranslations,
      },
      fr: {
        translation: frTranslations,
      },
    },
    fallbackLng: 'en',
    debug: false,
    interpolation: {
      escapeValue: false,
    },
  })

// Set initial dayjs locale
const initialLang = localStorage.getItem('i18nextLng') || 'en'
dayjs.locale(initialLang)

// Update dayjs locale when i18n language changes
i18n.on('languageChanged', (lng) => {
  dayjs.locale(lng)
})

export default i18n

