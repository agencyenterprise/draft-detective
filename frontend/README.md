The Draft Detective frontend: a [Next.js](https://nextjs.org) 16 app. The project-wide setup (backend, database, Docker) is in [`DEVELOPMENT.md`](../DEVELOPMENT.md).

## Getting Started

Use the Node version in `.nvmrc` (26.13.0 or newer) and pnpm, which `packageManager` in `package.json` pins. The versions are locked in `pnpm-lock.yaml`, which npm and yarn ignore.

```bash
pnpm install
cp .env.template .env   # then fill in AUTH_SECRET and a sign-in provider
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000). The app calls the backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), so start the backend too (`uv run dev.py` from the project root). `AUTH_SECRET` must match the backend's: `DEVELOPMENT.md` covers the environment variables.

`pnpm dev` runs Turbopack. `pnpm dev:webpack` runs webpack instead, and `pnpm dev:poll` adds file polling for file systems that don't report changes (some Docker and network mounts).

## API Types

`lib/generated-api/` is generated from the backend's OpenAPI schema by [Hey API](https://heyapi.dev): never edit it by hand. After a backend API change, regenerate it with the backend running on port 8000:

```bash
pnpm run openapi-generate
```

## Testing

Unit tests run on [Vitest](https://vitest.dev) in a jsdom environment. The
test dependencies need Node 26.13.0 or newer: `.nvmrc` selects a matching
version, the `engines` field in `package.json` enforces the floor, and CI and
the Docker image track the Node 26 line:

```bash
pnpm test        # run once
pnpm test:watch  # re-run on change
```

Tests live next to the module they cover, as `*.test.ts` (for example
`components/results/document-explorer/edit-highlight.test.ts`). They import
`describe`/`it`/`expect` from `vitest` explicitly rather than relying on
globals, and the `@/` path alias resolves as it does in the app.

Before opening a PR, run what CI runs: `pnpm run lint`, `pnpm test` and `pnpm run build`.

## Deployment

`Dockerfile` builds a standalone production image. `NEXT_PUBLIC_*` values are fixed when it is built, so pass them as build arguments. See [`docs/railway-deployment.md`](../docs/railway-deployment.md) for Railway and [`k8s/README.md`](../k8s/README.md) for Kubernetes.
