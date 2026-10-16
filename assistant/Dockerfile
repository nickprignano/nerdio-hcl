# The setup chatbot. Build from the repo root:  docker build -f assistant/Dockerfile .
FROM python:3.13-slim

# Terraform checks rendered tfvars against the kit's variables (no providers or credentials needed).
ARG TERRAFORM_VERSION=1.16.6
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates \
 && cd /tmp \
 && curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
 && curl -fsSLO "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_SHA256SUMS" \
 && grep "linux_amd64.zip" "terraform_${TERRAFORM_VERSION}_SHA256SUMS" | sha256sum -c - \
 && unzip -q "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -d /usr/local/bin \
 && rm -f /tmp/terraform_* && apt-get purge -y curl unzip && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /kit
COPY assistant/requirements.txt assistant/requirements.txt
RUN pip install --no-cache-dir -r assistant/requirements.txt

# Only what the bot reads: the engine, the schema, the stage variables and the knowledge base.
COPY scripts/nerdio scripts/nerdio
COPY schema schema
COPY environments/example environments/example
COPY modules/nerdio-config/variables.tf modules/nerdio-config/variables.tf
COPY docs docs
COPY assistant assistant

RUN useradd --uid 10001 --no-create-home bot && chown -R bot /kit
USER bot
ENV NERDIO_KIT_ROOT=/kit PYTHONUNBUFFERED=1 TF_IN_AUTOMATION=1 HOME=/tmp
EXPOSE 8000
CMD ["uvicorn", "app:app", "--app-dir", "assistant", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
