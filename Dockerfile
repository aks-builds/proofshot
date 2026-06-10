# cliproof — Alpine + Python 3.12 + freeze@0.2.2 + gifsicle
# Usage: docker run --rm -v $PWD:/repo ghcr.io/aks-builds/cliproof:latest \
#            capture --execute "mytool --help" -o /repo/.github/media/help.svg --json

FROM python:3.12-alpine

# Install build tools, Go (for freeze), and gifsicle
RUN apk add --no-cache \
    go \
    gcc \
    musl-dev \
    git \
    gifsicle \
    && go install github.com/charmbracelet/freeze@v0.2.2 \
    && apk del go gcc musl-dev git

# Go binaries live here
ENV PATH="/root/go/bin:${PATH}"

WORKDIR /app
COPY . .

RUN chmod +x /app/docker-entrypoint.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=2 \
    CMD python /app/skills/cliproof/scripts/health.py --json | \
        python -c "import sys,json; sys.exit(0 if json.load(sys.stdin).get('ok') else 1)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["health"]
