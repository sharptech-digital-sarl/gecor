/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  /** Fichier logo sous public/logo/ (ex. default.svg, organisation.png) */
  readonly VITE_LOGO_FILE?: string
  /** Initiales si l’image logo est absente (optionnel) */
  readonly VITE_LOGO_MONOGRAM?: string
  /** Version affichée (ex. 1.0, 1.2.3) */
  readonly VITE_APP_VERSION?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

