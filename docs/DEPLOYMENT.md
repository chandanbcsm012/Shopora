# Deploying a free demo (Render)

This deploys the whole stack on Render's free tier: managed Postgres,
the FastAPI backend, and the React frontend as a static site. One
account, one dashboard.

Free-tier limits worth knowing before you start:

- **Backend sleeps** after 15 minutes of no traffic; the first request
  after that takes ~30-50s to wake up.
- **Free Postgres expires 30 days** after creation — fine for a demo,
  but you'll need to recreate it (or upgrade) if the demo runs longer.
- **Uploaded product images are not persistent.** `media_storage/` lives
  on the backend's local disk, which Render's free plan does not persist
  across deploys/restarts. Fine for a demo; don't rely on it for real data.
- **Mailpit won't work in production** (it's a local-only container from
  `docker-compose.yml`). If you want invitation/password-reset emails to
  actually work in the demo, point SMTP at a real inbox — the free
  options are covered in step 4.

## 1. Push the repo to GitHub

Render deploys from a GitHub repo. This project has no git history or
remote yet, so create a repo on github.com and push it however you
normally would (`git init`, `git add`, `git commit`, add the remote,
`git push`). Nothing else in this guide depends on how you do that part.

## 2. Create the Render Blueprint

A [render.yaml](../render.yaml) blueprint is already in the repo root —
it defines the database, backend, and frontend together.

1. Go to the [Render dashboard](https://dashboard.render.com) and sign
   up / log in (GitHub login is easiest).
2. **New > Blueprint**, connect your GitHub account, and pick this repo.
3. Render reads `render.yaml` and shows three resources to create:
   `shopora-db`, `shopora-backend`,
   `shopora-frontend`. Click **Apply**.

Render will provision the free Postgres instance, then build and deploy
both services. First deploy takes a few minutes.

## 3. Fix up the cross-service URLs

`render.yaml` hardcodes the expected service URLs
(`https://shopora-backend.onrender.com`, etc.), but Render only
gives you that exact hostname if the name is free — otherwise it appends
a random suffix. After the first deploy:

1. Open each service in the Render dashboard and note its actual URL.
2. On **shopora-backend > Environment**, make sure `CORS_ORIGINS`
   and `FRONTEND_URL` match the frontend's real URL.
3. On **shopora-frontend > Environment**, make sure
   `VITE_API_BASE_URL` is `<backend-real-url>/api/v1`.
4. If you changed either, trigger **Manual Deploy > Clear build cache &
   deploy** on the frontend (Vite bakes `VITE_API_BASE_URL` in at build
   time, so a plain restart won't pick up the change).

## 4. Set up SMTP (only needed for invites / password reset)

The blueprint leaves `SMTP_HOST`, `SMTP_USERNAME`, and `SMTP_PASSWORD`
unset (`sync: false`) so you fill them in yourself on
**shopora-backend > Environment**. For a pure demo, the easiest
free option is [Ethereal Email](https://ethereal.email) — it generates a
throwaway SMTP inbox instantly (no signup) and lets you view sent mail
in a browser, the same role Mailpit plays locally:

```
SMTP_HOST=smtp.ethereal.email
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=<generated on ethereal.email>
SMTP_PASSWORD=<generated on ethereal.email>
```

If you want emails to land in a real inbox instead, any provider with a
free SMTP tier works the same way (e.g. Brevo's free plan).

## 5. First-run setup

Once both services are live:

1. Visit `<frontend-url>/admin/setup` to create the first super_admin
   account (see [README.md](../README.md#first-time-setup)).
2. Optionally seed sample products — this needs to be run once against
   the deployed database, e.g. from the Render backend service's **Shell**
   tab: `python -m scripts.seed_products`.

## Redeploys

Render auto-deploys on every push to the connected branch. Alembic
migrations run automatically as part of the backend's start command
(`alembic upgrade head && uvicorn ...`), so new migrations apply on
every deploy without a manual step.

To trigger a redeploy without pushing (e.g. after changing an env var,
or to retry a failed build), use [scripts/deploy.sh](../scripts/deploy.sh):

1. On each Render service, go to **Settings > Deploy Hook** and copy the
   URL.
2. Put them in a `.env.deploy` file at the repo root (gitignored):
   ```
   RENDER_BACKEND_DEPLOY_HOOK=https://api.render.com/deploy/srv-xxxx?key=yyyy
   RENDER_FRONTEND_DEPLOY_HOOK=https://api.render.com/deploy/srv-zzzz?key=wwww
   ```
3. Run:
   ```
   ./scripts/deploy.sh            # both services
   ./scripts/deploy.sh backend    # backend only
   ./scripts/deploy.sh frontend   # frontend only
   ```
