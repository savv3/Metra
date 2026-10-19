# Metra REST API

The `api` plugin: a JSON API for other systems, with a token per API client,
the client's role as its permissions, rate limits, an OpenAPI description
and audit logging of every change. It comes with Metra but is off by
default:

```sh
export METRA_PLUGINS=api
python manage.py migrate
```

Admins then make clients under Settings → API clients. See
[docs/api.md](../../docs/api.md) for the endpoints and examples, and
[docs/plugins.md](../../docs/plugins.md) for how plugins work.
