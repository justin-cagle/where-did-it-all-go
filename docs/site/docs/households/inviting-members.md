# Inviting Members

## How to send an invitation

1. Go to **Settings → Household**.
2. In the "Invite Member" section, enter the person's email address.
3. Choose their role: **Member** or **Owner**.
4. Click **Send invitation**.

Invitations are locked to the email address you enter. The person must use that email address to accept.

## What the invitee sees

### If SMTP is configured

The invitee receives an email from WDIAG:

> "[Your name] has invited you to join their household "[household name]" on WDIAG — Where Did It All Go.
>
> Accept this invitation: [link]
>
> This link expires in 72 hours and can only be used once."

### If SMTP is not configured

Email delivery is disabled. Instead, you'll get a **copyable invite link** to share manually — copy it and send it via any method (text message, Signal, email, etc.). The link works exactly the same as the emailed link.

After sending the invitation, a result card shows:

- Whether email was sent successfully
- A "Show link" toggle to get the copyable link (useful even if email was sent, in case it goes to spam)

## Accepting an invitation

When the invitee opens the link, they see the invitation details (household name, your name, their invited email, and the expiry time).

If they don't have a WDIAG account yet, they'll be prompted to create one. Their email is pre-filled and locked to the invited address — they can change it in Settings after joining.

If they already have an account, they log in and click Accept. They're immediately added to the household and redirected to the dashboard — no waiting period.

## Invite expiry

Invitations expire after **72 hours**. If the invitee doesn't accept in time, you can resend the invitation (which resets the 72-hour clock) from the pending invitations list.

## Revoking an invite

In the pending invitations list, click **Revoke** next to an invitation. The invite link immediately stops working. The invitee will see "This invitation has been cancelled" if they try to use it.

## Why invites are locked to an email address

The email address lock ensures the person joining is the person you intended to invite. If someone else intercepts the link, they can't use it — it only works for the email address it was sent to.

This also means: if the invitee wants to use a different email address, you'll need to revoke the original invitation and send a new one to their preferred address.

## Pending invitations list

You can see all pending invitations in **Settings → Household**. For each one:

- Invited email and role
- Whether email was sent or link-only
- Time until expiry (warning color if under 24 hours)
- Actions: Resend, Revoke, Copy Link
