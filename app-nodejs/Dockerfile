# ──────────────────────────────────────────────────────────────────────────────
# DevOps Assessment — Node.js / Express
#
# This Dockerfile is intentionally NOT optimised.
# Candidates are encouraged to improve it as part of the assessment.
# Known issues to find:
#   - No multi-stage build (dev dependencies bloat the image)
#   - Running as root
#   - No .dockerignore awareness baked in
#   - node_modules copied wholesale (non-deterministic)
#   - Single-process Node.js — no cluster mode or PM2
# ──────────────────────────────────────────────────────────────────────────────

FROM node:20

WORKDIR /app

COPY package.json .
RUN npm install

COPY . .

EXPOSE 3000

# Single process — intentional bottleneck for candidates to discover and fix.
CMD ["node", "index.js"]
