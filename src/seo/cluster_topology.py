"""
Internal-linking topic-cluster topology — the single source of truth for
which page belongs to which cluster, who the pillar is, and the exact
anchor text every backlink should use.

Five BTB clusters:
  1. ai-backlash      pillar: /ai-backlash/
  2. ai-incidents     pillar: /ai-incidents/
  3. ai-regulation    pillar: /explainers/eu-ai-act
  4. ai-labor         pillar: /explainers/ai-jobs
  5. ai-energy        pillar: /explainers/ai-water-use

Public API (kept tiny on purpose):
    cluster_for(path)     -> Cluster | None
    other_members(path)   -> list[ClusterLink]
    pillar_link_for(path) -> ClusterLink | None
    anchor_for(path)      -> str
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Canonical anchor-text phrases for high-traffic pages. Every inbound
# link from any cluster nav uses these exact strings so Google sees a
# consistent topical signal.
_ANCHOR: dict[str, str] = {
    # ai-backlash cluster
    "/ai-backlash/": "AI Backlash Explained: What Business Owners Need to Know",
    "/responsible-ai/healthcare/": "Responsible AI in Healthcare — risks, regulations, checklist",
    "/responsible-ai/finance/": "Responsible AI in Finance — CFPB, liability, compliance guide",
    "/responsible-ai/legal/": "Responsible AI in Legal — attorney ethics and AI liability",
    "/responsible-ai/retail/": "Responsible AI in Retail — bias, consumer protection, policy",
    "/responsible-ai/education/": "Responsible AI in Education — student data, equity, policy",
    "/responsible-ai/manufacturing/": "Responsible AI in Manufacturing — safety, labor, regulation",
    "/responsible-ai/real-estate/": "Responsible AI in Real Estate — fair housing and bias risk",
    "/responsible-ai/marketing/": "Responsible AI in Marketing — FTC, disclosure, AI slop risk",
    "/responsible-ai/": "Responsible AI by Industry — sector-specific risk guides",

    # ai-incidents cluster
    "/ai-incidents/": "AI Incident Tracker — real failures, harms, and near-misses",

    # ai-regulation cluster
    "/explainers/eu-ai-act": "EU AI Act Explained — what every business needs to know",
    "/briefing": "AI Risk & Responsible AI Daily Briefings",
    "/explainers/": "AI Explainers for Business Owners",

    # ai-labor cluster
    "/explainers/ai-jobs": "AI and Jobs: What the Research Actually Shows",

    # ai-energy cluster
    "/explainers/ai-water-use": "AI Water Use and Energy: The Data Center Impact Explained",

    # tool pages
    "/ai-risk-assessment/": "AI Risk Assessment — see where your business is exposed",
    "/no-ai-policy-template/": "No-AI Policy Template — ready to use for your business",
    "/human-made-policy-template/": "Human-Made Policy Template — certify your content is human",
}


@dataclass(frozen=True)
class ClusterLink:
    """One link in a cluster nav block."""
    path: str
    anchor: str
    description: str = ""


@dataclass(frozen=True)
class Cluster:
    """A topic cluster: one pillar + N cluster members.

    `members` does NOT include the pillar — templates render the pillar
    distinctly (sticky, top-of-block) and other members alongside.
    """
    key: str
    name: str
    pillar: ClusterLink
    members: tuple[ClusterLink, ...]
    summary: str = ""

    def all_paths(self) -> tuple[str, ...]:
        return (self.pillar.path,) + tuple(m.path for m in self.members)


def _ck(path: str, description: str = "") -> ClusterLink:
    """Construct a ClusterLink from a path using the canonical anchor."""
    return ClusterLink(
        path=path,
        anchor=_ANCHOR.get(path, path),
        description=description,
    )


# ──────────────────────────────────────────────────────────────────────
# The five BTB clusters
# ──────────────────────────────────────────────────────────────────────

CLUSTERS: dict[str, Cluster] = {
    "ai-backlash": Cluster(
        key="ai-backlash",
        name="AI Backlash & Responsible AI",
        summary=(
            "Everything a business owner needs to evaluate AI adoption risks — "
            "from the public backlash and regulatory landscape to sector-specific "
            "guidance for healthcare, finance, legal, retail, education, "
            "manufacturing, real estate, and marketing."
        ),
        pillar=_ck(
            "/ai-backlash/",
            "The definitive guide to AI backlash and what it means for your business.",
        ),
        members=(
            _ck("/responsible-ai/",          "Industry-specific AI risk guides for 8 sectors."),
            _ck("/responsible-ai/healthcare/", "HIPAA + AI, diagnostic liability, and patient safety."),
            _ck("/responsible-ai/finance/",    "CFPB, fair lending, algorithmic bias in financial AI."),
            _ck("/responsible-ai/legal/",      "Attorney ethics, malpractice risk, and AI-generated briefs."),
            _ck("/responsible-ai/retail/",     "Consumer protection, FTC scrutiny, and AI recommendation bias."),
            _ck("/responsible-ai/education/",  "FERPA, student data, equity concerns, and AI policy."),
            _ck("/responsible-ai/manufacturing/", "Workplace safety, labor displacement, and ISO standards."),
            _ck("/responsible-ai/real-estate/", "Fair Housing Act, appraisal bias, and automated valuations."),
            _ck("/responsible-ai/marketing/",  "FTC disclosure rules, AI slop risk, and brand reputation."),
            _ck("/ai-risk-assessment/",        "Self-assessment tool: quantify your AI exposure before deploying."),
            _ck("/no-ai-policy-template/",     "Ready-to-use template telling stakeholders where you draw the line."),
            _ck("/human-made-policy-template/", "Certify that your content and decisions are human-created."),
        ),
    ),

    "ai-incidents": Cluster(
        key="ai-incidents",
        name="AI Incident Tracker",
        summary=(
            "A live database of real-world AI failures, harms, and near-misses "
            "drawn from the AI Incident Database and AIAAIC. Updated daily. "
            "Filterable by sector and severity."
        ),
        pillar=_ck(
            "/ai-incidents/",
            "Live tracker of AI failures, harms, and near-misses — updated daily.",
        ),
        members=(
            _ck("/ai-backlash/",           "Context: why AI incidents are fuelling the backlash."),
            _ck("/responsible-ai/",        "Sector guides for reducing your own AI incident risk."),
            _ck("/briefing",               "Daily briefings covering new AI incidents as they break."),
            _ck("/ai-risk-assessment/",    "Assess your business exposure before an incident happens."),
        ),
    ),

    "ai-regulation": Cluster(
        key="ai-regulation",
        name="AI Regulation & Policy",
        summary=(
            "Plain-English coverage of the EU AI Act, FTC enforcement, NIST "
            "Risk Management Framework, and US Congressional AI legislation — "
            "what applies to your business and what to do about it."
        ),
        pillar=_ck(
            "/explainers/eu-ai-act",
            "The EU AI Act — compliance requirements, risk tiers, and US implications.",
        ),
        members=(
            _ck("/ai-backlash/",           "How regulation is responding to the broader AI backlash."),
            _ck("/responsible-ai/finance/", "CFPB and financial-AI regulatory exposure."),
            _ck("/responsible-ai/healthcare/", "HIPAA and FDA guidance on AI in healthcare."),
            _ck("/briefing",               "Daily briefings on new AI regulation and enforcement actions."),
            _ck("/ai-incidents/",          "Real incidents that prompted regulatory action."),
            _ck("/no-ai-policy-template/", "Template: communicate your AI limits to regulators and clients."),
        ),
    ),

    "ai-labor": Cluster(
        key="ai-labor",
        name="AI, Jobs & Workforce",
        summary=(
            "What the data actually shows about AI's impact on employment — "
            "sector-by-sector layoff trends, reskilling research, and what "
            "business owners can realistically expect over the next 3-5 years."
        ),
        pillar=_ck(
            "/explainers/ai-jobs",
            "AI and jobs: the evidence, the hype, and what business owners should plan for.",
        ),
        members=(
            _ck("/ai-backlash/",              "Labor anxiety is a major driver of the public AI backlash."),
            _ck("/responsible-ai/manufacturing/", "AI's biggest labor displacement impact is in manufacturing."),
            _ck("/responsible-ai/retail/",    "Retail automation and the AI workforce debate."),
            _ck("/briefing",                  "Daily coverage of AI layoff announcements and workforce research."),
            _ck("/ai-incidents/",             "AI workforce incidents — wrongful termination, bias in hiring."),
            _ck("/no-ai-policy-template/",    "Policy template for communicating AI's role in your workforce."),
        ),
    ),

    "ai-energy": Cluster(
        key="ai-energy",
        name="AI Energy & Water Use",
        summary=(
            "Data center energy consumption, water cooling demand, and the "
            "environmental footprint of AI — the numbers, the projections, "
            "and what they mean for corporate sustainability commitments."
        ),
        pillar=_ck(
            "/explainers/ai-water-use",
            "AI water and energy use: the real numbers behind data center demand.",
        ),
        members=(
            _ck("/ai-backlash/",             "Environmental concerns are a key pillar of the AI backlash."),
            _ck("/responsible-ai/manufacturing/", "Energy-intensive AI and manufacturing sustainability."),
            _ck("/briefing",                 "Daily coverage of AI energy and environmental reporting."),
            _ck("/ai-incidents/",            "Environmental harms flagged in the AI incident database."),
        ),
    ),
}


# Path-prefix → cluster key. Order matters — most-specific prefix first.
_PATH_TO_CLUSTER: tuple[tuple[str, str], ...] = (
    ("/ai-backlash/",                "ai-backlash"),
    ("/responsible-ai/healthcare/",  "ai-backlash"),
    ("/responsible-ai/finance/",     "ai-backlash"),
    ("/responsible-ai/legal/",       "ai-backlash"),
    ("/responsible-ai/retail/",      "ai-backlash"),
    ("/responsible-ai/education/",   "ai-backlash"),
    ("/responsible-ai/manufacturing/", "ai-backlash"),
    ("/responsible-ai/real-estate/", "ai-backlash"),
    ("/responsible-ai/marketing/",   "ai-backlash"),
    ("/responsible-ai/",             "ai-backlash"),
    ("/ai-risk-assessment/",         "ai-backlash"),
    ("/no-ai-policy-template/",      "ai-backlash"),
    ("/human-made-policy-template/", "ai-backlash"),

    ("/ai-incidents/",               "ai-incidents"),

    ("/explainers/eu-ai-act",        "ai-regulation"),

    ("/explainers/ai-jobs",          "ai-labor"),

    ("/explainers/ai-water-use",     "ai-energy"),
)


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────


def cluster_for(path: str) -> Optional[Cluster]:
    """Return the Cluster a given URL path belongs to, or None."""
    if not path:
        return None
    norm = "/" + path.lstrip("/")
    for prefix, key in _PATH_TO_CLUSTER:
        if norm == prefix.rstrip("/") or norm.startswith(prefix):
            return CLUSTERS.get(key)
    return None


def other_members(path: str, *, limit: int = 12) -> list[ClusterLink]:
    """Return the cluster's other members (excluding `path` itself)."""
    cluster = cluster_for(path)
    if cluster is None:
        return []
    norm = "/" + path.lstrip("/")
    out: list[ClusterLink] = []
    for m in cluster.members:
        if m.path == norm or m.path.rstrip("/") == norm.rstrip("/"):
            continue
        out.append(m)
        if len(out) >= limit:
            break
    return out


def pillar_link_for(path: str) -> Optional[ClusterLink]:
    """Return the pillar link for the given page's cluster, or None.

    If `path` IS the pillar, returns None.
    """
    cluster = cluster_for(path)
    if cluster is None:
        return None
    norm = "/" + path.lstrip("/")
    if cluster.pillar.path.rstrip("/") == norm.rstrip("/"):
        return None
    return cluster.pillar


def anchor_for(path: str) -> str:
    """Return the canonical anchor text for a path."""
    return _ANCHOR.get("/" + path.lstrip("/"), path)


def build_cluster_ctx(path: str, *, limit: int = 12) -> dict:
    """One-shot helper: returns the dict every template needs to render
    `_cluster_nav.html.j2`'s cluster_nav() macro.
    """
    cluster = cluster_for(path)
    if cluster is None:
        return {"cluster": None, "pillar": None, "others": [], "is_pillar": False}
    pillar = pillar_link_for(path)
    return {
        "cluster": cluster,
        "pillar": pillar,
        "others": other_members(path, limit=limit),
        "is_pillar": pillar is None,
    }
