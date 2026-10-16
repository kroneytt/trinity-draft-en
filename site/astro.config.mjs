// Static site, built from ../cards/*.json. Links between pages are relative,
// so the output works at any address (GitHub Pages sub-folder, a custom domain, a local folder).
import { defineConfig } from "astro/config";

export default defineConfig({
  site: process.env.SITE_URL || "https://kroneytt.github.io",
  base: process.env.SITE_BASE || "/trinity-draft-en",
  build: { format: "file", inlineStylesheets: "always" },
  devToolbar: { enabled: false },
});
