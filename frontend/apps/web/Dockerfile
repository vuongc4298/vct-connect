FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/apps/web/package.json apps/web/package.json
COPY frontend/apps/extension/package.json apps/extension/package.json
COPY frontend/packages/contracts/package.json packages/contracts/package.json
COPY frontend/packages/api-client/package.json packages/api-client/package.json
RUN npm ci
COPY frontend/ ./
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ARG VCT_EXTENSION_WEB_ORIGIN
ENV NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV VCT_EXTENSION_WEB_ORIGIN=$VCT_EXTENSION_WEB_ORIGIN
RUN npm run build -w @vct/web

FROM node:22-alpine AS runtime
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /app/apps/web/public ./apps/web/public
COPY --from=build --chown=node:node /app/apps/web/private/vct-connect-extension.zip ./apps/web/private/vct-connect-extension.zip
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
