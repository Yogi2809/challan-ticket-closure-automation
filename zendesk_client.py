import logging
import urllib3

import requests

import config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_TICKET_PAYLOAD = {
    "ticket": {
        "status": "solved",
        "comment": {
            "body": (
                "Dear Channel Partner,\n\n"
                "All pre-delivery challan has been cleared against this vehicle, "
                "same will be reflected on site within 24 hours.\n\n"
                "Thanks & Regards\nCars24"
            ),
            "public": True,
        },
        "custom_fields": [
            {"id": 9759821503503, "value": "sent_for_clearance"},
            {"id": 11876293100303, "value": "query_"},
        ],
    }
}


def close_ticket(ticket_id: str) -> bool:
    url = f"{config.ZENDESK_BASE_URL}/api/v2/tickets/{ticket_id}.json"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {config.ZENDESK_AUTH_TOKEN}",
    }

    try:
        response = requests.put(url, json=_TICKET_PAYLOAD, headers=headers, verify=False, timeout=20)
    except requests.exceptions.RequestException as exc:
        logger.error("Zendesk request failed for ticket %s: %s", ticket_id, exc)
        return False

    logger.info("Zendesk ticket %s → HTTP %s", ticket_id, response.status_code)

    if response.status_code != 200:
        logger.error("Zendesk error for ticket %s: %s", ticket_id, response.text)
        return False

    return True
