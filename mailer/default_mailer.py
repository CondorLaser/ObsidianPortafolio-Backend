# using SendGrid's Python Library
# https://github.com/sendgrid/sendgrid-python
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv

# active_alerts es una lista [[tipo alerta, trigger_value, threshold_value], [tipo alerta, trigger_value, threshold_value]]
def inmmediate_mail(to_email, active_alerts):
    load_dotenv()
    
    # Colores según tipo de alerta
    alert_colors = {
        "stop_loss":  {"bg": "#fcebeb", "border": "#f7c1c1", "title": "#a32d2d", "text": "#501313", "value": "#a32d2d", "threshold": "#791f1f"},
        "volatilidad":{"bg": "#faeeda", "border": "#fac775", "title": "#854f0b", "text": "#412402", "value": "#854f0b", "threshold": "#633806"},
        "drawdown":   {"bg": "#e6f1fb", "border": "#b5d4f4", "title": "#185fa5", "text": "#042c53", "value": "#185fa5", "threshold": "#0c447c"},
    }
    default_color = {"bg": "#f1efe8", "border": "#d3d1c7", "title": "#5f5e5a", "text": "#2c2c2a", "value": "#5f5e5a", "threshold": "#444441"}

    alert_cards = ""
    for alert in active_alerts:
        alert_type, trigger_value, threshold_value = alert[0], alert[1], alert[2]
        c = alert_colors.get(alert_type.lower(), default_color)

        alert_cards += f"""
        <div style="border: 0.5px solid {c['border']}; border-radius: 8px; padding: 14px 16px; background: {c['bg']}; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <span style="font-size: 11px; font-weight: 600; color: {c['title']}; text-transform: uppercase; letter-spacing: 0.06em;">{alert_type}</span>
                </div>
                <div style="text-align: right; margin-left: 16px;">
                    <p style="margin: 0; font-size: 15px; font-weight: 600; color: {c['value']};">{trigger_value}</p>
                    <p style="margin: 2px 0 0; font-size: 12px; color: {c['threshold']};">Umbral: {threshold_value}</p>
                </div>
            </div>
        </div>
        """

    from datetime import date
    today = date.today().strftime("%-d %b %Y")
    n = len(active_alerts)

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 560px; margin: 0 auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden;">
        
        <div style="background: #1a1a2e; padding: 28px 32px 24px;">
            <p style="margin: 0; font-size: 18px; font-weight: 600; color: #fff;">Obsidian Portfolio</p>
            <p style="margin: 6px 0 0; font-size: 13px; color: rgba(255,255,255,0.5);">Reporte de alertas activas</p>
        </div>

        <div style="padding: 24px 32px 8px;">
            <p style="margin: 0; font-size: 13px; color: #555;">
                Se detectaron <strong style="color: #111;">{n} alerta{'s' if n != 1 else ''}</strong> que requieren tu atención.
            </p>
        </div>

        <div style="padding: 12px 32px 28px;">
            {alert_cards}
        </div>

        <div style="border-top: 1px solid #eee; padding: 16px 32px; display: flex; justify-content: space-between;">
            <span style="font-size: 12px; color: #999;">Obsidian Portfolio · Alertas automáticas</span>
        </div>

    </div>
    """

    message = Mail(
        from_email='condorlaser8@gmail.com',
        to_emails=to_email,
        subject='Alertas Obsidian Portfolio',
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)
    except Exception as e:
        print(e.message)


inmmediate_mail("fschiappacasse@uc.cl",  [["alerta1", "4", "5"], ["alerta2", "8.9", "77"]])