# deps
FROM node:24-bookworm-slim AS deps

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./

RUN npm ci

# builder
FROM deps AS builder

WORKDIR /app/frontend

COPY frontend/ ./

ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# runner
FROM node:24-bookworm-slim AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

RUN groupadd --system --gid 1001 nodejs \
  && useradd --system --uid 1001 --gid nodejs nextjs

COPY --from=builder --chown=nextjs:nodejs /app/frontend/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
