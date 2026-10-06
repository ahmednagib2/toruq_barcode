from markupsafe import Markup


def brt_notify(env, users, title, text):
    """Sticky pop-up (bus) + inbox message."""
    for user in users.sudo().filtered("active"):
        partner = user.partner_id
        env["bus.bus"].sudo()._sendone(
            partner,
            "simple_notification",
            {"title": title, "message": text, "type": "warning", "sticky": True},
        )
        partner.sudo().message_notify(
            partner_ids=[partner.id],
            author_id=env.user.partner_id.id,
            subject=title,
            body=Markup("<p>%s</p>") % text,
        )
