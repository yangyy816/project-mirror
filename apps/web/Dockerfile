FROM node:24.18.0-slim AS build

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@11.19.0 --activate
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json ./
COPY apps/web ./apps/web
COPY packages ./packages
RUN pnpm install --frozen-lockfile
ARG NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN pnpm --filter @mirror/web build
RUN mkdir -p apps/web/.next/standalone/apps/web/.next && \
    cp -r apps/web/.next/static apps/web/.next/standalone/apps/web/.next/static && \
    cp -r node_modules/.pnpm/node_modules/@swc/helpers/esm \
      apps/web/.next/standalone/node_modules/.pnpm/next@*/node_modules/@swc/helpers/

EXPOSE 3000
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
CMD ["node", "apps/web/.next/standalone/apps/web/server.js"]
