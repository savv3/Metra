# Example plugin

The smallest useful SmallCompanyRegister plugin, used by the app's tests and
as a starting point for your own. It adds:

- a menu item, **Example**, with a page listing the number of units;
- a panel on every unit page;
- an SMS provider called `example-log` that only writes to the log.

Install and enable it:

```sh
pip install ./plugins/example     # or uv pip install
export SCR_PLUGINS=example
python manage.py check
```

See [docs/plugins.md](../../docs/plugins.md) for how plugins work.
