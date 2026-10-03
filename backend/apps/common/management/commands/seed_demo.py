from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.common.models import Activity, Technician
from apps.incidents.models import Incident, IncidentReport
from apps.incidents.services import open_incident
from apps.messaging.models import Message, Notification
from apps.network.models import NetworkSite, ServiceArea
from apps.subscribers.models import Subscriber
from apps.support.models import SupportCase
from apps.support.services import create_support_case

NAIROBI = ZoneInfo("Africa/Nairobi")

AREAS = [
    ("Kilimani", [[-1.2852, 36.778], [-1.286, 36.7968], [-1.2935, 36.7992], [-1.3004, 36.794], [-1.2996, 36.7772], [-1.292, 36.7748]], "Kilimani residential and business pocket."),
    ("South B", [[-1.3055, 36.8225], [-1.3048, 36.8455], [-1.3135, 36.8488], [-1.3218, 36.841], [-1.3205, 36.824], [-1.312, 36.8208]], "South B estate coverage."),
    ("Lavington", [[-1.2708, 36.7605], [-1.2715, 36.7795], [-1.2802, 36.7822], [-1.2884, 36.7768], [-1.2872, 36.759], [-1.278, 36.7568]], "Lavington residential node."),
    ("Kilimani West", [[-1.2888, 36.7555], [-1.2895, 36.7738], [-1.2978, 36.7755], [-1.3052, 36.7702], [-1.304, 36.7548], [-1.296, 36.7526]], "Kilimani West extension."),
    ("CBD", [[-1.2772, 36.8135], [-1.2766, 36.8318], [-1.2848, 36.8346], [-1.2922, 36.8288], [-1.291, 36.8142], [-1.2835, 36.811]], "Nairobi CBD core."),
]

SITES = [
    ("Kilimani POP", NetworkSite.SiteType.POP, "Kilimani", -1.2916, 36.7868),
    ("South B Tower", NetworkSite.SiteType.TOWER, "South B", -1.3132, 36.8338),
    ("Lavington Node", NetworkSite.SiteType.NODE, "Lavington", -1.2794, 36.7698),
    ("CBD Core", NetworkSite.SiteType.CORE, "CBD", -1.2846, 36.8234),
]

TECHNICIANS = [
    ("Brian Kamau", "+254711640228", "brian.kamau@kijaninetworks.co.ke", "Kilimani"),
    ("Kevin Mwangi", "+254722318904", "kevin.mwangi@kijaninetworks.co.ke", "South B"),
    ("Peter Otieno", "+254701992145", "peter.otieno@kijaninetworks.co.ke", "Lavington"),
]

EXTRA_NAMES = [
    "Faith Wanjiru", "Brian Otieno", "Caroline Mwangi", "Stephen Kamau", "Naomi Achieng",
    "Eric Mutiso", "Joyce Wambua", "Patrick Maina", "Lydia Cheruiyot", "George Omondi",
    "Alice Njoki", "Victor Kiptoo", "Ruth Atieno", "Simon Kariuki", "Hannah Wairimu",
    "Dennis Onyango", "Irene Chebet", "Collins Njuguna", "Beatrice Moraa", "Felix Barasa",
    "Cynthia Akinyi", "Martin Were", "Purity Nyambura", "Allan Kiprop", "Sharon Adhiambo",
    "Timothy Langat", "Winnie Muthoni", "Oscar Juma", "Diana Chepkemoi", "Kenneth Otieno",
    "Agnes Wanjala", "Paul Mwenda",
]


def at_nairobi(hour, minute):
    today = datetime.now(NAIROBI)
    return today.replace(hour=hour, minute=minute, second=0, microsecond=0)


class Command(BaseCommand):
    help = "Load ISPBora demo areas, sites, subscribers, cases, and incidents."

    @transaction.atomic
    def handle(self, *args, **options):
        self._clear()
        areas = self._areas()
        self._sites(areas)
        technicians = self._technicians(areas)
        people = self._subscribers(areas)
        kilimani_incident = open_incident(
            service_area=areas["Kilimani"],
            title="Kilimani Service Disruption",
            description="Customers in Kilimani report a loss of service from the Kilimani POP.",
            incident_type=Incident.IncidentType.CONNECTIVITY,
            severity=Incident.Severity.CRITICAL,
            affected_subscriber_ids=[person.id for person in people["kilimani_affected"]],
            incident_number="INC-104",
            started_at=at_nairobi(8, 42),
            status=Incident.Status.INVESTIGATING,
        )
        south_b_incident = open_incident(
            service_area=areas["South B"],
            title="South B Connectivity Issue",
            description="Degraded connectivity reported around South B Tower.",
            incident_type=Incident.IncidentType.CONNECTIVITY,
            severity=Incident.Severity.MAJOR,
            affected_subscriber_ids=[person.id for person in people["south_b_affected"]],
            incident_number="INC-102",
            started_at=at_nairobi(7, 28),
            status=Incident.Status.MONITORING,
        )
        self._cases(people)
        self._messages(people)
        Activity.objects.create(text="First customer report received for INC-104")
        Activity.objects.create(text="INC-102 placed under monitoring")
        kilimani_incident.refresh_from_db()
        south_b_incident.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(
            "seed_demo complete: "
            f"{ServiceArea.objects.count()} areas, "
            f"{NetworkSite.objects.count()} sites, "
            f"{Technician.objects.count()} technicians, "
            f"{Subscriber.objects.count()} subscribers, "
            f"{SupportCase.objects.count()} cases, "
            f"{Incident.objects.count()} incidents, "
            f"INC-104 affected={kilimani_incident.affected_subscribers} reports={kilimani_incident.report_count}, "
            f"INC-102 affected={south_b_incident.affected_subscribers} reports={south_b_incident.report_count}, "
            f"technicians={', '.join(tech.name for tech in technicians)}"
        ))

    def _clear(self):
        Notification.objects.all().delete()
        Message.objects.all().delete()
        from apps.ai.models import AgentRun

        AgentRun.objects.all().delete()
        IncidentReport.objects.all().delete()
        Incident.objects.all().delete()
        SupportCase.objects.all().delete()
        Subscriber.objects.all().delete()
        Technician.objects.all().delete()
        NetworkSite.objects.all().delete()
        Activity.objects.all().delete()
        ServiceArea.objects.all().delete()

    def _areas(self):
        created = {}
        for name, geometry, description in AREAS:
            created[name] = ServiceArea.objects.create(
                name=name,
                description=description,
                geometry=geometry,
                status=ServiceArea.Status.OPERATIONAL,
            )
        return created

    def _sites(self, areas):
        for name, site_type, area_name, latitude, longitude in SITES:
            NetworkSite.objects.create(
                name=name,
                site_type=site_type,
                service_area=areas[area_name],
                latitude=latitude,
                longitude=longitude,
                description=f"{name} serves {area_name}.",
            )

    def _technicians(self, areas):
        return [
            Technician.objects.create(
                name=name,
                phone_number=phone,
                email=email,
                service_area=areas[area_name],
                status=Technician.Status.AVAILABLE,
            )
            for name, phone, email, area_name in TECHNICIANS
        ]

    def _subscribers(self, areas):
        cursor = {"n": 0}

        def add(area_name, full_name, phone, plan, status, connection, account=None):
            cursor["n"] += 1
            subscriber = Subscriber.objects.create(
                account_number=account or f"SUB-{1000 + cursor['n']:05d}",
                full_name=full_name,
                phone_number=phone,
                email=f"{full_name.lower().replace(' ', '.')}@example.com",
                address=f"{area_name}, Nairobi",
                service_area=areas[area_name],
                plan=plan,
                status=status,
                connection_status=connection,
                installation_date=date(2024, 1, 8) + timedelta(days=cursor["n"] * 7),
            )
            return subscriber

        kilimani_named = [
            ("Mary Wanjiku", "+254712438221", "Home 20 Mbps", "SUB-00124"),
            ("James Ochieng", "+254722615904", "Home 10 Mbps", "SUB-00188"),
            ("Grace Njeri", "+254733890112", "Home 20 Mbps", "SUB-00211"),
        ]
        kilimani_affected = [
            add("Kilimani", name, phone, plan, Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.OFFLINE, account)
            for name, phone, plan, account in kilimani_named
        ]
        for offset, name in enumerate(EXTRA_NAMES[:21]):
            kilimani_affected.append(add(
                "Kilimani",
                name,
                f"+254710{offset:06d}",
                "Home 10 Mbps" if offset % 2 == 0 else "Home 20 Mbps",
                Subscriber.Status.ACTIVE,
                Subscriber.ConnectionStatus.OFFLINE,
            ))
        add("Kilimani", "Peter Njoroge", "+254711203884", "Business 50 Mbps", Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.ONLINE, "SUB-00156")

        south_named = [
            ("David Kipchoge", "+254720667331", "Home 10 Mbps", "SUB-00415"),
            ("Fatuma Ali", "+254711908221", "Home 20 Mbps", "SUB-00440"),
            ("Mercy Chebet", "+254708334512", "Home 10 Mbps", "SUB-00488"),
        ]
        south_b_affected = [
            add("South B", name, phone, plan, Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.OFFLINE, account)
            for name, phone, plan, account in south_named
        ]
        for offset, name in enumerate(EXTRA_NAMES[21:31]):
            south_b_affected.append(add(
                "South B",
                name,
                f"+254711{offset:06d}",
                "Home 20 Mbps",
                Subscriber.Status.ACTIVE,
                Subscriber.ConnectionStatus.OFFLINE,
            ))

        add("Kilimani West", "Aisha Mohammed", "+254701554873", "Home 10 Mbps", Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.ONLINE, "SUB-00302")
        add("Kilimani West", "Hassan Abdi", "+254745221098", "Home 20 Mbps", Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.ONLINE, "SUB-00276")
        add("Lavington", "Samuel Kariuki", "+254707274525", "Business 50 Mbps", Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.ONLINE, "SUB-00512")
        add("Lavington", "Ann Wairimu", "+254733221760", "Home 20 Mbps", Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.ONLINE, "SUB-00540")
        add("Lavington", "Daniel Kiptoo", "+254701882345", "Business 100 Mbps", Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.ONLINE, "SUB-00571")
        add("Lavington", "Catherine Wambui", "+254715440218", "Home 10 Mbps", Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.ONLINE, "SUB-00590")
        add("CBD", "Lucy Akinyi", "+254715662190", "Business 50 Mbps", Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.DEGRADED, "SUB-00603")
        add("CBD", "Joseph Mutua", "+254724908331", "Home 10 Mbps", Subscriber.Status.SUSPENDED, Subscriber.ConnectionStatus.OFFLINE, "SUB-00620")
        add("CBD", "Esther Nyambura", "+254700214587", "Home 20 Mbps", Subscriber.Status.ACTIVE, Subscriber.ConnectionStatus.ONLINE, "SUB-00655")
        add("CBD", "Michael Odhiambo", "+254798331204", "Business 100 Mbps", Subscriber.Status.INACTIVE, Subscriber.ConnectionStatus.OFFLINE, "SUB-00680")

        for area in areas.values():
            area.refresh_subscriber_count()

        return {
            "kilimani_affected": kilimani_affected,
            "south_b_affected": south_b_affected,
            "by_name": {item.full_name: item for item in Subscriber.objects.all()},
        }

    def _cases(self, people):
        kilimani_reports = people["kilimani_affected"][:11]
        south_reports = people["south_b_affected"][:6]
        for index, subscriber in enumerate(kilimani_reports):
            category = SupportCase.Category.INTERNET_DOWN
            source = [SupportCase.Source.WHATSAPP, SupportCase.Source.VOICE, SupportCase.Source.SMS][index % 3]
            create_support_case({
                "subscriber": subscriber,
                "service_area": subscriber.service_area,
                "category": category,
                "subject": "Internet Down",
                "description": "Customer reported a Kilimani service problem.",
                "priority": SupportCase.Priority.HIGH,
                "source": source,
                "status": SupportCase.Status.INVESTIGATING if index == 1 else SupportCase.Status.OPEN,
            })
        for index, subscriber in enumerate(south_reports):
            category = SupportCase.Category.INTERNET_DOWN
            create_support_case({
                "subscriber": subscriber,
                "service_area": subscriber.service_area,
                "category": category,
                "subject": "Internet Down",
                "description": "Customer reported a South B connectivity problem.",
                "priority": SupportCase.Priority.HIGH,
                "source": SupportCase.Source.SMS if index == 0 else SupportCase.Source.WHATSAPP,
            })
        by_name = people["by_name"]
        create_support_case({
            "subscriber": by_name["Samuel Kariuki"],
            "service_area": by_name["Samuel Kariuki"].service_area,
            "category": SupportCase.Category.SLOW_INTERNET,
            "subject": "Slow Internet",
            "description": "Office link is slower than usual. No total outage.",
            "priority": SupportCase.Priority.LOW,
            "source": SupportCase.Source.WHATSAPP,
        })
        lucy = create_support_case({
            "subscriber": by_name["Lucy Akinyi"],
            "service_area": by_name["Lucy Akinyi"].service_area,
            "category": SupportCase.Category.TECHNICAL,
            "subject": "Connection Unstable",
            "description": "Shop connection drops during card payments.",
            "priority": SupportCase.Priority.MEDIUM,
            "source": SupportCase.Source.VOICE,
        })
        lucy.assigned_to = "Nelly Chebet"
        lucy.status = SupportCase.Status.ACKNOWLEDGED
        lucy.save(update_fields=["assigned_to", "status", "updated_at"])
        create_support_case({
            "subscriber": by_name["Joseph Mutua"],
            "service_area": by_name["Joseph Mutua"].service_area,
            "category": SupportCase.Category.ACCOUNT,
            "subject": "Suspended account",
            "description": "Service was unstable before the account was suspended.",
            "priority": SupportCase.Priority.LOW,
            "source": SupportCase.Source.SMS,
        })
        hassan = create_support_case({
            "subscriber": by_name["Hassan Abdi"],
            "service_area": by_name["Hassan Abdi"].service_area,
            "category": SupportCase.Category.INTERNET_DOWN,
            "subject": "Internet Down",
            "description": "No internet last night. Service was later restored.",
            "priority": SupportCase.Priority.LOW,
            "source": SupportCase.Source.WHATSAPP,
        })
        hassan.status = SupportCase.Status.RESOLVED
        hassan.resolved_at = timezone.now() - timedelta(hours=18)
        hassan.save(update_fields=["status", "resolved_at", "updated_at"])

    def _messages(self, people):
        mary = people["by_name"]["Mary Wanjiku"]
        Message.objects.create(
            subscriber=mary,
            channel=Message.Channel.WHATSAPP,
            direction=Message.Direction.INBOUND,
            message_type="SUPPORT",
            body="My internet has been down since morning.",
            status=Message.Status.DELIVERED,
        )
        Message.objects.create(
            subscriber=mary,
            channel=Message.Channel.WHATSAPP,
            direction=Message.Direction.OUTBOUND,
            message_type="OUTAGE",
            body="There is currently an active service issue affecting your area. Our team is investigating.",
            status=Message.Status.DELIVERED,
        )
