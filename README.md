# EngReads

A quiet, mobile-first reading list of company engineering, infrastructure, and AI blogs.

Posts stay on each company’s site. EngReads indexes public RSS/Atom feeds.

Live site (after Pages is enabled): [https://singhutsav5502.github.io/EnggReads/](https://singhutsav5502.github.io/EnggReads/)

## Local preview

```bash
python scripts/fetch-feeds.py
python -m http.server 8080
```

Open [http://localhost:8080](http://localhost:8080).

## GitHub Pages

This repo deploys with GitHub Actions (`Fetch and deploy`):

1. **Settings → Pages → Source:** GitHub Actions
2. Push to `main`, or run **Actions → Fetch and deploy → Run workflow**
3. The workflow refreshes feeds about every six hours and publishes the site

## Add a blog

Edit `data/sources.json`:

```json
{
  "id": "acme",
  "name": "Acme",
  "blog": "Acme Engineering",
  "url": "https://engineering.acme.com",
  "feed": "https://engineering.acme.com/rss.xml",
  "tags": ["engineering", "infrastructure"]
}
```

Genre ids: `recommended`, `engineering`, `internal`, `infrastructure`, `ai`, `security`, `data`, `databases`, `frontend`, `backend`, `devops`, `reliability`, `mobile`, `culture`.

Set `"recommended": true` on a source to include it in the Recommended lane.
