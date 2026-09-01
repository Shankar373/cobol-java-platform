# ── Stage 1: Python + JDK 17 + Maven 3.9 ─────────────────────────────────────
# Uses eclipse-temurin JDK 17 (LTS) as base — includes javac + java.
# Base image upgraded to 'noble' (Ubuntu 24.04) to provide Python 3.12 (PEP 701 support).
# Maven is installed on top. Python is installed via apt.
# No local JDK, Maven, or Python versions needed on the host.
FROM eclipse-temurin:17-jdk-noble AS runtime

# Install Python 3 + pip + curl (for health checks) with minimal layer
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip curl \
        maven \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
# Install static Docker CLI binary to allow containerized docker executions
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-26.1.4.tgz | tar -xz -C /tmp \
 && mv /tmp/docker/docker /usr/local/bin/ \
 && rm -rf /tmp/docker

# Make 'python' resolve to python3
RUN ln -sf /usr/bin/python3 /usr/bin/python

# ── App ────────────────────────────────────────────────────────────────────────
WORKDIR /app

# Copy only source — generated dirs (target/, workspace/, scratch/) stay out via .dockerignore
COPY modernize/        ./modernize/
COPY execution/        ./execution/
COPY third_party/      ./third_party/
COPY tests/            ./tests/
COPY docs/             ./docs/
COPY legacy/           ./legacy/
COPY *.py              ./
COPY ui.html           ./
COPY requirements.txt  ./

# Pre-warm the Maven local repo with common dependencies so first pipeline run
# doesn't hit network. Uses offline-capable seed poms.
# AGENTS.md §10: resolution must be deterministic and verified per artifact.
# A successful Maven exit code alone is NOT treated as evidence.
COPY docker/maven-seed-pom.xml /tmp/seed-pom.xml
COPY docker/maven-proleap-seed-pom.xml /tmp/proleap-seed-pom.xml
RUN mvn -B -f /tmp/seed-pom.xml dependency:resolve \
 && mvn -B -f /tmp/proleap-seed-pom.xml dependency:resolve

# Verify every required artifact exists individually in the local repository.
# Versions are pinned by the seed POMs; keep this list in sync with them.
RUN set -e; \
    M2=/root/.m2/repository; \
    REQUIRED="\
      com/fasterxml/jackson/core/jackson-databind/2.15.2/jackson-databind-2.15.2.jar \
      com/fasterxml/jackson/core/jackson-annotations/2.15.2/jackson-annotations-2.15.2.jar \
      com/fasterxml/jackson/core/jackson-core/2.15.2/jackson-core-2.15.2.jar \
      org/antlr/antlr4-runtime/4.7.2/antlr4-runtime-4.7.2.jar \
      org/slf4j/slf4j-api/2.0.9/slf4j-api-2.0.9.jar \
      org/springframework/boot/spring-boot/3.2.5/spring-boot-3.2.5.jar \
      org/springframework/boot/spring-boot-starter-web/3.2.5/spring-boot-starter-web-3.2.5.pom \
      com/h2database/h2/2.2.224/h2-2.2.224.jar \
    "; \
    MISSING=0; \
    for rel in $REQUIRED; do \
      if [ ! -s "$M2/$rel" ]; then echo "MISSING ARTIFACT: $rel" >&2; MISSING=1; fi; \
    done; \
    if [ "$MISSING" != "0" ]; then echo "dependency verification FAILED" >&2; exit 1; fi; \
    echo "Maven dependency artifact verification: OK (8/8 present)"

# ── Runtime ───────────────────────────────────────────────────────────────────
EXPOSE 8787

# Workspace volume — pipeline writes generated Java, compiled classes, reports here.
# Mount this as a named volume so data survives container restarts.
VOLUME ["/app/workspace", "/root/.m2"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8787/ || exit 1

CMD ["python", "ui.py", "--host", "0.0.0.0", "--port", "8787"]
