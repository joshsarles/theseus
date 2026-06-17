/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_THESEUS_API?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
