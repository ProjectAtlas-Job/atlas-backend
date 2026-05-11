# Atlas Backend

FastAPI backend for Project Atlas.

## Gmail SMTP setup

Project Atlas sends verification, OTP, welcome, password reset, and support emails through Gmail SMTP.

### Required environment variables

Copy `.env.example` to `.env` and set:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-gmail-address@gmail.com
SMTP_PASS=your-16-character-app-password
SMTP_FROM=your-gmail-address@gmail.com
```

Do not commit `.env`. The backend `.gitignore` already excludes it.

### Gmail App Password requirements

Gmail SMTP for this project uses an App Password, not your normal Gmail password.

1. Sign in to your Google account.
2. Open `Security`.
3. Enable `2-Step Verification` if it is not already enabled.
4. Open `App passwords`.
5. Generate a new app password for Mail.
6. Copy the 16-character password into `SMTP_PASS`.

Notes:

- Google only shows `App passwords` after 2-Step Verification is enabled.
- Gmail may rewrite the sender address to match the authenticated Gmail account.
- Gmail is convenient for low-volume production use, but Google can still block suspicious server logins.

## Email-enabled flows

The backend sends email for:

- account verification links
- email verification OTP codes
- password reset links
- welcome emails after verification
- contact/support submissions

SMTP connectivity is verified on backend startup when `SMTP_*` variables are configured.

## Local development

1. Create `.env`.
2. Run database and Redis dependencies.
3. Apply migrations.
4. Start the API server.

Example:

```bash
alembic upgrade head
uvicorn app.main:app --reload
```

## Testing email functionality

1. Start the backend with valid `SMTP_*` variables.
2. Register a new account from the frontend.
3. Confirm the verification email arrives.
4. Request an OTP from `/verify-email` and confirm the code arrives.
5. Complete password reset from `/forgot-password`.
6. Submit the `/contact-support` form and confirm the support email arrives in the configured Gmail inbox.

If SMTP verification fails on startup, re-check:

- `SMTP_USER`
- `SMTP_PASS`
- Google 2-Step Verification status
- whether the App Password was revoked or regenerated
