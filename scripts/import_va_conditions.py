#!/usr/bin/env python3
"""Seed VACondition table from landing_generator's CONDITION_RESEARCH dict."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from rich.console import Console
from rich.table import Table

console = Console()

ALL_CONDITIONS = [
    ("tinnitus", "Tinnitus", "38 CFR Part 4, DC 6260", 10, "Ringing or buzzing in the ears — the most commonly claimed VA disability."),
    ("ptsd", "PTSD", "38 CFR Part 4, DC 9411", 50, "Post-Traumatic Stress Disorder from in-service trauma, combat, or MST."),
    ("lumbar-spine-strain", "Lumbar Spine Strain", "38 CFR Part 4, DC 5237", 20, "Lower-back pain from in-service injury."),
    ("sleep-apnea", "Sleep Apnea", "38 CFR Part 4, DC 6847", 50, "Obstructive sleep apnea requiring CPAP often rated 50%."),
    ("knee-pain", "Knee Conditions", "38 CFR Part 4, DC 5257", 10, "Knee instability, limitation of motion, and surgical residuals."),
    ("migraines", "Migraines", "38 CFR Part 4, DC 8100", 30, "Migraine headaches with characteristic prostrating attacks."),
    ("depression", "Major Depressive Disorder", "38 CFR Part 4, DC 9434", 30, "Depression secondary to a service-connected condition or direct service connection."),
    ("anxiety", "Anxiety Disorders", "38 CFR Part 4, DC 9400", 30, "Generalized anxiety disorder and related conditions."),
    ("tbi", "Traumatic Brain Injury", "38 CFR Part 4, DC 8045", 40, "TBI from in-service blast exposure, combat, or accident."),
    ("hearing-loss", "Hearing Loss", "38 CFR Part 4, DC 6100", 0, "Sensorineural hearing loss from noise exposure — rated by puretone average."),
    ("shoulder-impingement", "Shoulder Impingement", "38 CFR Part 4, DC 5201", 20, "Limitation of arm motion from in-service shoulder injury."),
    ("hypertension", "Hypertension", "38 CFR Part 4, DC 7101", 10, "High blood pressure — often secondary to other service-connected conditions."),
    ("diabetes-mellitus-type-2", "Diabetes Mellitus Type 2", "38 CFR Part 4, DC 7913", 20, "Agent Orange presumptive for veterans who served in qualifying locations."),
    ("burn-pit-exposure", "Burn Pit Exposure", "PACT Act presumptives", 0, "Airborne hazards exposure presumptives under the 2022 PACT Act."),
    ("agent-orange-exposure", "Agent Orange Exposure", "38 CFR 3.307/3.309", 0, "Presumptive conditions for Vietnam-era veterans exposed to herbicides."),
    ("mst-military-sexual-trauma", "Military Sexual Trauma (MST)", "38 CFR 3.304(f)", 50, "PTSD from military sexual trauma — liberal nexus standard applies."),
    ("chronic-fatigue-syndrome", "Chronic Fatigue Syndrome", "38 CFR Part 4, DC 6354", 20, "Debilitating fatigue with cognitive symptoms."),
    ("fibromyalgia", "Fibromyalgia", "38 CFR Part 4, DC 5025", 20, "Widespread musculoskeletal pain."),
    ("cervical-spine-strain", "Cervical Spine Strain", "38 CFR Part 4, DC 5237", 10, "Neck pain from in-service injury."),
    ("plantar-fasciitis", "Plantar Fasciitis", "38 CFR Part 4, DC 5284", 10, "Heel pain — often secondary to pes planus."),
    ("pes-planus-flat-feet", "Pes Planus (Flat Feet)", "38 CFR Part 4, DC 5276", 10, "Flat feet from prolonged standing in military service."),
    ("bilateral-knee", "Bilateral Knee Conditions", "38 CFR Part 4, DC 5257", 20, "Both knees claimed — bilateral factor may apply."),
    ("bilateral-hearing-loss", "Bilateral Hearing Loss", "38 CFR Part 4, DC 6100", 0, "Both ears claimed with bilateral factor."),
    ("gulf-war-illness", "Gulf War Illness", "38 CFR 3.317", 40, "Undiagnosed illness presumptive for Gulf War veterans."),
    ("radiculopathy-lower", "Radiculopathy (Lower Extremity)", "38 CFR Part 4, DC 8520", 20, "Nerve pain radiating down the leg — often secondary to lumbar spine."),
    ("radiculopathy-upper", "Radiculopathy (Upper Extremity)", "38 CFR Part 4, DC 8510", 20, "Nerve pain radiating down the arm — often secondary to cervical spine."),
    ("degenerative-disc-disease", "Degenerative Disc Disease", "38 CFR Part 4, DC 5243", 20, "Spinal disc degeneration from service wear and injury."),
    ("hemorrhoids", "Hemorrhoids", "38 CFR Part 4, DC 7336", 10, "Internal or external hemorrhoids from prolonged standing or poor diet in service."),
    ("irritable-bowel-syndrome", "Irritable Bowel Syndrome", "38 CFR Part 4, DC 7319", 10, "IBS secondary to PTSD or Gulf War illness."),
    ("gerd", "GERD", "38 CFR Part 4, DC 7346", 10, "Gastroesophageal reflux disease — often secondary to hiatal hernia."),
    ("rhinitis", "Rhinitis", "38 CFR Part 4, DC 6522", 10, "Allergic or non-allergic rhinitis from burn pit or other exposure."),
    ("sinusitis", "Sinusitis", "38 CFR Part 4, DC 6510", 10, "Chronic sinusitis from environmental exposure or rhinitis."),
    ("skin-conditions-dermatitis", "Skin Conditions (Dermatitis)", "38 CFR Part 4, DC 7806", 10, "Contact or atopic dermatitis from service exposure."),
]


def main():
    from src.models import init_db, VACondition, engine
    from sqlalchemy.orm import Session

    init_db()

    inserted = 0
    updated = 0

    with Session(engine) as session:
        for slug, display, cfr, typical_pct, short_desc in ALL_CONDITIONS:
            existing = session.query(VACondition).filter_by(slug=slug).first()
            if existing:
                existing.display_name = display
                existing.cfr_citation = cfr
                existing.typical_rating_pct = typical_pct
                existing.short_description = short_desc
                session.add(existing)
                updated += 1
            else:
                cond = VACondition(
                    slug=slug,
                    display_name=display,
                    cfr_citation=cfr,
                    typical_rating_pct=typical_pct,
                    short_description=short_desc,
                )
                session.add(cond)
                inserted += 1

        session.commit()

    table = Table(title="VACondition Import")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Inserted", str(inserted))
    table.add_row("Updated", str(updated))
    console.print(table)


if __name__ == "__main__":
    main()
