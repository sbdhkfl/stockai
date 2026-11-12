# Deploying the remote MCP endpoint (HTTPS)

`python -m fairvalue.mcp_http` serves the MCP Streamable HTTP endpoint on
**loopback only by default** (`127.0.0.1:8001`). Production deployments put a
TLS-terminating reverse proxy in front; never expose uvicorn directly to the
internet.

## 1. Generate a token (env only — never commit)

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Store it in the environment of the MCP server process (systemd `Environment=`,
container secret, shell export). **Never** put it in git, in shell history you
share, in screenshots, or in client config files — clients should reference it
via their env-var substitution (`{env:...}`, `${env:...}`).

## 2. Run the server bound to loopback

```bash
export FAIRVALUE_MCP_TOKEN="<generated>"       # or reuse FAIRVALUE_API_KEY
export FAIRVALUE_MCP_HOST=127.0.0.1            # default
export FAIRVALUE_MCP_PORT=8001                 # default
python -m fairvalue.mcp_http
```

The process **refuses to start** without a token (except
`FAIRVALUE_MCP_ALLOW_ANON=1`, which is loopback-development only and never
allows a non-loopback bind).

## 3. Reverse proxy with HTTPS

**Caddy** (automatic Let's Encrypt certificates) — `Caddyfile`:

```
mcp.example.com {
    reverse_proxy 127.0.0.1:8001
}
```

**nginx** (certbot-issued certificate):

```nginx
server {
    listen 443 ssl;
    server_name mcp.example.com;
    ssl_certificate     /etc/letsencrypt/live/mcp.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mcp.example.com/privkey.pem;

    location /mcp {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;   # SSE streaming
        proxy_set_header Connection "upgrade";
        proxy_buffering off;                      # required for SSE
        proxy_read_timeout 3600s;
    }
    location = /health { proxy_pass http://127.0.0.1:8001; }
}
```

## 4. Host-header allow-list (DNS-rebinding protection)

For non-loopback deployments the server validates the `Host` header against
`FAIRVALUE_MCP_ALLOWED_HOSTS` (comma-separated), otherwise requests are
rejected:

```bash
export FAIRVALUE_MCP_ALLOWED_HOSTS="mcp.example.com"
```

## 5. Checklist

- [ ] TLS terminated at the proxy; HTTP never serves MCP traffic.
- [ ] Token lives only in process environment; rotated if ever exposed.
- [ ] `FAIRVALUE_MCP_ALLOWED_HOSTS` set to your real hostname.
- [ ] `FAIRVALUE_CORS_ORIGINS` (REST API) restricted if the API is also public.
- [ ] Uvicorn stays on loopback; the proxy is the only public listener.
- [ ] `GET /health` reveals nothing but liveness (`{"status":"ok",
      "transport":"streamable-http"}`).
- [ ] MCP traffic requires `Authorization: Bearer <token>` (401 otherwise).

See [SECURITY.md](../SECURITY.md) for the general security posture and
[MCP_CLIENTS.md](MCP_CLIENTS.md) for connecting assistants.
