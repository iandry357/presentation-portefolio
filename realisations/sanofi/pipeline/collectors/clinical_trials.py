"""
Collecteur ClinicalTrials.gov API v2.
Récupère les essais cliniques Sanofi avec données enrichies.
"""
import logging
import requests
from typing import List, Dict

from pipeline.config import (
    CLINICAL_TRIALS_BASE_URL,
    CLINICAL_TRIALS_QUERY,
    CLINICAL_TRIALS_MAX_RESULTS,
)

logger = logging.getLogger(__name__)


def _build_content(study: Dict) -> str:
    """Construit un contenu enrichi pour embedding."""
    proto = study.get("protocolSection", {})
    
    # Identification
    id_module = proto.get("identificationModule", {})
    title = id_module.get("briefTitle", "")
    official_title = id_module.get("officialTitle", "")

    # Description
    desc_module = proto.get("descriptionModule", {})
    brief_summary = desc_module.get("briefSummary", "")
    detailed_desc = desc_module.get("detailedDescription", "")

    # Conditions
    cond_module = proto.get("conditionsModule", {})
    conditions = ", ".join(cond_module.get("conditions", []))
    keywords = ", ".join(cond_module.get("keywords", []))

    # Interventions
    arms = proto.get("armsInterventionsModule", {})
    interventions = arms.get("interventions", [])
    interventions_text = "; ".join(
        f"{i.get('name', '')} ({i.get('type', '')})"
        for i in interventions
    )

    # Design
    design_module = proto.get("designModule", {})
    phase = ", ".join(design_module.get("phases", []))
    study_type = design_module.get("studyType", "")

    # Outcomes
    outcomes_module = proto.get("outcomesModule", {})
    primary_outcomes = outcomes_module.get("primaryOutcomes", [])
    outcomes_text = "; ".join(
        o.get("measure", "") for o in primary_outcomes[:3]
    )

    parts = [
        f"Titre: {title}",
        f"Titre officiel: {official_title}" if official_title else "",
        f"Phase: {phase}" if phase else "",
        f"Type: {study_type}" if study_type else "",
        f"Conditions: {conditions}" if conditions else "",
        f"Mots-clés: {keywords}" if keywords else "",
        f"Interventions: {interventions_text}" if interventions_text else "",
        f"Résumé: {brief_summary}" if brief_summary else "",
        f"Description: {detailed_desc[:500]}" if detailed_desc else "",
        f"Critères primaires: {outcomes_text}" if outcomes_text else "",
    ]

    return "\n".join(p for p in parts if p)


def _extract_metadata(study: Dict) -> Dict:
    """Extrait les métadonnées structurées."""
    proto = study.get("protocolSection", {})

    id_module = proto.get("identificationModule", {})
    status_module = proto.get("statusModule", {})
    design_module = proto.get("designModule", {})
    cond_module = proto.get("conditionsModule", {})
    sponsor_module = proto.get("sponsorCollaboratorsModule", {})

    return {
        "nct_id": id_module.get("nctId", ""),
        "phase": ", ".join(design_module.get("phases", [])),
        "status": status_module.get("overallStatus", ""),
        "conditions": cond_module.get("conditions", []),
        "study_type": design_module.get("studyType", ""),
        "sponsor": sponsor_module.get("leadSponsor", {}).get("name", ""),
        "start_date": status_module.get("startDateStruct", {}).get("date", ""),
        "completion_date": status_module.get("completionDateStruct", {}).get("date", ""),
        "url": f"https://clinicaltrials.gov/study/{id_module.get('nctId', '')}",
    }


def collect(max_results: int = CLINICAL_TRIALS_MAX_RESULTS) -> List[Dict]:
    """
    Collecte les essais cliniques Sanofi depuis ClinicalTrials.gov API v2.

    Returns:
        Liste de documents au format unifié pipeline.
    """
    logger.info(f"🔍 ClinicalTrials — collecte '{CLINICAL_TRIALS_QUERY}' (max {max_results})")

    params = {
        "query.term": CLINICAL_TRIALS_QUERY,
        "pageSize": min(max_results, 100),
        "format": "json",
        "fields": ",".join([
            "protocolSection.identificationModule",
            "protocolSection.statusModule",
            "protocolSection.descriptionModule",
            "protocolSection.conditionsModule",
            "protocolSection.designModule",
            "protocolSection.armsInterventionsModule",
            "protocolSection.outcomesModule",
            "protocolSection.sponsorCollaboratorsModule",
        ]),
    }

    docs = []
    next_page_token = None

    while len(docs) < max_results:
        if next_page_token:
            params["pageToken"] = next_page_token

        try:
            resp = requests.get(CLINICAL_TRIALS_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error(f"❌ ClinicalTrials API error: {e}")
            break

        studies = data.get("studies", [])
        if not studies:
            break

        for study in studies:
            proto = study.get("protocolSection", {})
            id_module = proto.get("identificationModule", {})
            status_module = proto.get("statusModule", {})

            nct_id = id_module.get("nctId", "")
            if not nct_id:
                continue

            # Date de mise à jour
            date = status_module.get("lastUpdatePostDateStruct", {}).get("date", "")

            doc = {
                "id": f"clinicaltrials_{nct_id}",
                "source": "clinicaltrials",
                "date": date,
                "title": id_module.get("briefTitle", ""),
                "content": _build_content(study),
                "metadata": _extract_metadata(study),
            }
            docs.append(doc)

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    logger.info(f"✅ ClinicalTrials — {len(docs)} essais collectés")
    return docs