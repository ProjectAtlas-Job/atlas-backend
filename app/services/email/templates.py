from __future__ import annotations

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class EmailContent:
    subject: str
    html: str
    text: str


def _base_template(*, preheader: str, title: str, eyebrow: str, intro: str, body_html: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{escape(title)}</title>
    <style>
      body {{
        margin: 0;
        padding: 0;
        background: #f4f7fb;
        color: #0f172a;
        font-family: Arial, Helvetica, sans-serif;
      }}
      .preheader {{
        display: none !important;
        visibility: hidden;
        opacity: 0;
        color: transparent;
        height: 0;
        width: 0;
        overflow: hidden;
      }}
      .shell {{
        width: 100%;
        padding: 24px 12px;
      }}
      .card {{
        max-width: 620px;
        margin: 0 auto;
        background: #ffffff;
        border-radius: 24px;
        overflow: hidden;
        box-shadow: 0 24px 64px rgba(15, 23, 42, 0.12);
      }}
      .hero {{
        padding: 32px 32px 24px;
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        color: #ffffff;
      }}
      .eyebrow {{
        margin: 0 0 10px;
        font-size: 12px;
        line-height: 1.5;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        opacity: 0.82;
      }}
      .title {{
        margin: 0;
        font-size: 30px;
        line-height: 1.2;
        font-weight: 700;
      }}
      .intro {{
        margin: 14px 0 0;
        font-size: 16px;
        line-height: 1.65;
        color: rgba(255, 255, 255, 0.88);
      }}
      .content {{
        padding: 32px;
        font-size: 16px;
        line-height: 1.7;
        color: #334155;
      }}
      .content p {{
        margin: 0 0 16px;
      }}
      .cta {{
        display: inline-block;
        margin: 8px 0 20px;
        padding: 14px 22px;
        border-radius: 999px;
        background: #2563eb;
        color: #ffffff !important;
        font-weight: 700;
        text-decoration: none;
      }}
      .panel {{
        margin: 20px 0;
        padding: 18px;
        border-radius: 18px;
        background: #eff6ff;
        color: #1e3a8a;
      }}
      .otp {{
        margin: 10px 0 18px;
        font-size: 34px;
        line-height: 1.1;
        font-weight: 700;
        letter-spacing: 0.28em;
        color: #0f172a;
        text-align: center;
      }}
      .footer {{
        padding: 0 32px 32px;
        font-size: 13px;
        line-height: 1.7;
        color: #64748b;
      }}
      @media only screen and (max-width: 640px) {{
        .hero,
        .content,
        .footer {{
          padding-left: 22px !important;
          padding-right: 22px !important;
        }}
        .title {{
          font-size: 25px !important;
        }}
        .otp {{
          font-size: 28px !important;
          letter-spacing: 0.18em !important;
        }}
        .cta {{
          display: block !important;
          text-align: center !important;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="preheader">{escape(preheader)}</div>
    <div class="shell">
      <div class="card">
        <div class="hero">
          <p class="eyebrow">{escape(eyebrow)}</p>
          <h1 class="title">{escape(title)}</h1>
          <p class="intro">{escape(intro)}</p>
        </div>
        <div class="content">{body_html}</div>
        <div class="footer">
          <p>Project Atlas</p>
          <p>This mailbox is monitored for account and support delivery only.</p>
        </div>
      </div>
    </div>
  </body>
</html>
"""


def verification_email(*, full_name: str | None, verification_link: str) -> EmailContent:
    name = escape(full_name or "there")
    body_html = (
        f"<p>Hi {name},</p>"
        "<p>Thanks for joining Project Atlas. Confirm your email address to activate your account and keep your security settings in sync.</p>"
        f'<p><a class="cta" href="{escape(verification_link, quote=True)}">Verify email address</a></p>'
        f'<div class="panel"><p>If the button does not open, use this link:</p><p>{escape(verification_link)}</p></div>'
        "<p>If you did not create this account, you can ignore this email.</p>"
    )
    return EmailContent(
        subject="Verify your Project Atlas email",
        html=_base_template(
            preheader="Verify your Project Atlas email address.",
            title="Verify your email",
            eyebrow="Account Security",
            intro="One quick confirmation keeps your sign-in secure and unlocks your account.",
            body_html=body_html,
        ),
        text=(
            "Verify your Project Atlas email.\n\n"
            f"Open this link to verify your account: {verification_link}\n\n"
            "If you did not create this account, you can ignore this email."
        ),
    )


def otp_email(*, full_name: str | None, otp_code: str) -> EmailContent:
    name = escape(full_name or "there")
    body_html = (
        f"<p>Hi {name},</p>"
        "<p>Use the one-time code below to verify your Project Atlas email address. The code expires in 10 minutes.</p>"
        f'<div class="panel"><p class="otp">{escape(otp_code)}</p><p>Enter this code on the verification screen to continue.</p></div>'
        "<p>If you did not request this code, you can safely ignore this email.</p>"
    )
    return EmailContent(
        subject="Your Project Atlas verification code",
        html=_base_template(
            preheader="Your Project Atlas verification code.",
            title="Verification code",
            eyebrow="Secure Access",
            intro="Use this short-lived code to confirm your email address.",
            body_html=body_html,
        ),
        text=(
            "Your Project Atlas verification code\n\n"
            f"Code: {otp_code}\n"
            "This code expires in 10 minutes.\n\n"
            "If you did not request this code, you can ignore this email."
        ),
    )


def password_reset_email(*, full_name: str | None, reset_link: str) -> EmailContent:
    name = escape(full_name or "there")
    body_html = (
        f"<p>Hi {name},</p>"
        "<p>We received a request to reset your Project Atlas password. If this was you, continue with the secure link below. The link expires in 60 minutes.</p>"
        f'<p><a class="cta" href="{escape(reset_link, quote=True)}">Reset password</a></p>'
        f'<div class="panel"><p>If the button does not open, use this link:</p><p>{escape(reset_link)}</p></div>'
        "<p>If you did not request a reset, no changes have been made.</p>"
    )
    return EmailContent(
        subject="Reset your Project Atlas password",
        html=_base_template(
            preheader="Reset your Project Atlas password.",
            title="Reset your password",
            eyebrow="Account Recovery",
            intro="Use the secure link below to choose a new password for your account.",
            body_html=body_html,
        ),
        text=(
            "Reset your Project Atlas password.\n\n"
            f"Open this link to reset your password: {reset_link}\n"
            "The link expires in 60 minutes.\n\n"
            "If you did not request a reset, you can ignore this email."
        ),
    )


def welcome_email(*, full_name: str | None, dashboard_link: str) -> EmailContent:
    name = escape(full_name or "there")
    body_html = (
        f"<p>Hi {name},</p>"
        "<p>Your Project Atlas account is verified and ready. You can now sign in, complete your profile, and start using the dashboard.</p>"
        f'<p><a class="cta" href="{escape(dashboard_link, quote=True)}">Open Project Atlas</a></p>'
        "<p>Welcome aboard. We are glad you are here.</p>"
    )
    return EmailContent(
        subject="Welcome to Project Atlas",
        html=_base_template(
            preheader="Welcome to Project Atlas.",
            title="Welcome to Project Atlas",
            eyebrow="Account Ready",
            intro="Your email is verified and your workspace is ready to go.",
            body_html=body_html,
        ),
        text=(
            "Welcome to Project Atlas.\n\n"
            f"Your account is verified. Open your dashboard here: {dashboard_link}"
        ),
    )

