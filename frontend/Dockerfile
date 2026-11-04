FROM node:26-alpine AS base

# Install pnpm, pinned to the version package.json declares in
# `packageManager`. Unpinned, this picks up whatever is latest at build time:
# pnpm 11 verifies the package-manager identity against a `@pnpm/exe.<platform>`
# entry that a pnpm-10 lockfile does not carry, so `--frozen-lockfile` fails.
RUN npm install -g pnpm@10.33.0

# Install dependencies only when needed
FROM base AS deps
WORKDIR /app

# Copy package.json, lock files, and patches (referenced by the lockfile)
COPY package.json pnpm-lock.yaml ./
COPY patches ./patches

# Install dependencies
RUN pnpm install --frozen-lockfile

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Accept build arguments for environment variables
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_POSTHOG_KEY
ARG NEXT_PUBLIC_POSTHOG_HOST
ARG NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG
ARG NODE_ENV=production

ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_POSTHOG_KEY=$NEXT_PUBLIC_POSTHOG_KEY
ENV NEXT_PUBLIC_POSTHOG_HOST=$NEXT_PUBLIC_POSTHOG_HOST
ENV NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG=$NEXT_PUBLIC_REQUIRE_OPENAI_API_KEY_CONFIG
ENV NODE_ENV=$NODE_ENV

# Build the application
RUN pnpm build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy the public folder
COPY --from=builder /app/public ./public

# Automatically leverage output traces to reduce image size
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000 || exit 1

CMD ["node", "server.js"]
