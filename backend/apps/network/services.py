from apps.network.models import NetworkSite, ServiceArea


def apply_area_status(area, status):
    area.status = status
    area.save(update_fields=["status", "updated_at"])
    site_status = {
        ServiceArea.Status.OUTAGE: NetworkSite.Status.OFFLINE,
        ServiceArea.Status.INVESTIGATING: NetworkSite.Status.DEGRADED,
        ServiceArea.Status.DEGRADED: NetworkSite.Status.DEGRADED,
        ServiceArea.Status.OPERATIONAL: NetworkSite.Status.ONLINE,
    }[status]
    area.sites.exclude(status=NetworkSite.Status.MAINTENANCE).update(status=site_status)


def restore_area_if_clear(area):
    active = area.incidents.exclude(status="RESOLVED").exists()
    if not active:
        apply_area_status(area, ServiceArea.Status.OPERATIONAL)
