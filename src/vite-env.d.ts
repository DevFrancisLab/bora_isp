/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_MAP_STREET_URL?: string;
  readonly VITE_MAP_SATELLITE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
